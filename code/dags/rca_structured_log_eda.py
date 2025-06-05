from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
#from dask.distributed import Client
#import dask.dataframe as dd
import boto3
import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO
import configuration

def perform_dask_eda_and_save_to_s3(**kwargs):
    #client = Client("tcp://dask-scheduler.dask.svc.cluster.local:8786")

    s3_path = f"s3://{configuration.DEST_BUCKET}/{configuration.SILVER_FILE_KEY}"
    df = pd.read_csv(s3_path)

    print("✅ Columns:", df.columns)
    
    # Summary EDA
    summary = {
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "missing_values": df.isnull().sum().compute().to_dict(),
        "row_count": df.shape[0].compute(),
    }

    # Save EDA summary to CSV
    summary_df = pd.DataFrame.from_dict(summary, orient='index').transpose()
    summary_buffer = BytesIO()
    summary_df.to_csv(summary_buffer, index=False)

    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    plot_bucket = configuration.DEST_BUCKET
    eda_dir = "logs/eda_output"

    for col in numeric_cols:
        plt.figure()
        df[col].compute().hist(bins=30)
        plt.title(f"Histogram of {col}")
        plt.xlabel(col)
        plt.ylabel("Frequency")

        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png')
        img_buffer.seek(0)

        file_key = f"{eda_dir}/histogram_{col}.png"
        boto3.client("s3").put_object(
            Bucket=plot_bucket,
            Key=file_key,
            Body=img_buffer,
            ContentType='image/png'
        )
        plt.close()
        print(f"📊 Histogram saved to s3://{plot_bucket}/{file_key}")

    # Upload summary
    boto3.client("s3").put_object(
        Bucket=plot_bucket,
        Key=f"{eda_dir}/eda_summary.csv",
        Body=summary_buffer.getvalue()
    )

    print("✅ EDA summary and plots saved to S3.")
    #client.close()


# DAG Start Time (rounded down to nearest 30 mins minus 5 mins)
now_utc = datetime.now(timezone.utc)
start_date_utc = now_utc.replace(minute=(now_utc.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)

with DAG(
    dag_id='rca_structured_log_eda',
    start_date=start_date_utc,
    schedule_interval="*/10 * * * *",
    catchup=False,
    tags=['s3', 'validation', 'etl'],
) as dag:
    eda_task = PythonOperator(
        task_id="perform_dask_eda_and_save_to_s3",
        python_callable=perform_dask_eda_and_save_to_s3
    )
