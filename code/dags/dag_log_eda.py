from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import boto3
import pandas as pd
import dask.dataframe as dd
import matplotlib.pyplot as plt
from io import BytesIO
import configuration
from dask.distributed import Client
from otel import tracer, meter, logger, OTEL_ENABLED

def safe_int(val):
    try:
        return int(val.compute())
    except AttributeError:
        return int(val)

def analyse_request_id_feature(df):
    analysis_results = {}

    value_counts = df["request_id"].value_counts(dropna=False).head(50)
    analysis_results["request_id_top_50_value_counts"] = value_counts.to_dict()

    num_nulls = df["request_id"].isna().sum()
    analysis_results["request_id_null_count"] = safe_int(num_nulls)

    num_dash = (df["request_id"] == "-").sum()
    analysis_results["request_id_dash_count"] = safe_int(num_dash)

    has_duplicates = bool(df["request_id"].compute().duplicated().any())
    analysis_results["request_id_has_duplicates"] = has_duplicates

    logger.info("\nAnalysis for 'request_id' column:")
    logger.info(f"Top 50 value counts: {analysis_results['request_id_top_50_value_counts']}")
    logger.info(f"Null count: {analysis_results['request_id_null_count']}")
    logger.info(f"Dash count: {analysis_results['request_id_dash_count']}")
    logger.info(f"Has duplicates: {analysis_results['request_id_has_duplicates']}")

    buffer = BytesIO()
    pd.DataFrame([analysis_results]).to_csv(buffer, index=False)
    boto3.client("s3").put_object(
        Bucket=configuration.DEST_BUCKET,
        Key=f"{configuration.EDA_OUTPUT}/eda_analyse_request_id_feature.csv",
        Body=buffer.getvalue()
    )

def analyse_feature_datatype_missing_value(df):
    logger.info("Columns: %s", df.columns)

    summary_dict = {
        "columns": ", ".join(df.columns),
        "row_count": safe_int(df.shape[0])
    }

    dtypes = df.dtypes.astype(str).to_dict()
    missing = df.isnull().sum().compute().to_dict()

    for col in df.columns:
        summary_dict[f"dtype_{col}"] = dtypes.get(col)
        summary_dict[f"missing_{col}"] = missing.get(col)

    buffer = BytesIO()
    pd.DataFrame([summary_dict]).to_csv(buffer, index=False)
    boto3.client("s3").put_object(
        Bucket=configuration.DEST_BUCKET,
        Key=f"{configuration.EDA_OUTPUT}/eda_summary.csv",
        Body=buffer.getvalue()
    )

def analyse_feature_histogram(df):
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    for col in numeric_cols:
        plt.figure()
        df[col].compute().hist(bins=30)
        plt.title(f"Histogram of {col}")
        plt.xlabel(col)
        plt.ylabel("Frequency")

        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png')
        img_buffer.seek(0)

        file_key = f"{configuration.EDA_OUTPUT}/histogram_{col}.png"
        boto3.client("s3").put_object(
            Bucket=configuration.DEST_BUCKET,
            Key=file_key,
            Body=img_buffer,
            ContentType='image/png'
        )
        plt.close()
        logger.info(f"Histogram saved to s3://{configuration.DEST_BUCKET}/{file_key}")

def impute_request_id(df):
    logger.info("\nPerforming imputation for '-' values in 'request_id' with 'rca-system'...")
    df_copy = df.copy()
    updated = df_copy['request_id'].replace('-', "rca-system").compute()
    df_copy['request_id'] = dd.from_pandas(updated, npartitions=df_copy.npartitions)
    logger.info("Imputation complete.")
    return df_copy

def perform_dask_eda_and_save_to_s3(**kwargs):
    try:
        with tracer.start_as_current_span("perform_dask_eda_and_save_to_s3") as span:
            span.set_attribute("function", "perform_dask_eda_and_save_to_s3")
            logger.info("Starting perform_dask_eda_and_save_to_s3:")
            client = Client("tcp://dask-scheduler.dask.svc.cluster.local:8786")

            s3_path = f"s3://{configuration.DEST_BUCKET}/{configuration.SILVER_FILE_KEY}"
            df = dd.read_csv(s3_path)
            logger.info("CSV file read from S3.")

            # Ensure divisions are known before any partition-based operations
            if not df.known_divisions:
                df = df.set_index(df.columns[0], sorted=False, drop=False)

            analyse_feature_datatype_missing_value(df)
            analyse_feature_histogram(df)

            if 'request_id' in df.columns:
                analyse_request_id_feature(df)
                df = impute_request_id(df)

                imputed_output_path = f"s3://{configuration.DEST_BUCKET}/{configuration.SILVER_FILE_KEY}"
                logger.info(f"Writing imputed DataFrame back to {imputed_output_path}...")
                df.to_csv(imputed_output_path, single_file=True, index=False)
                logger.info("Imputed structured log saved successfully.")
            else:
                logger.info("Column 'request_id' not found in the dataset. Skipping request_id analysis.")

            logger.info("EDA summary and plots saved to S3.")
            client.close()
    except Exception as e:
        logger.error(f"Error during EDA processing: {e}")

# DAG Start Time (rounded down to nearest 30 mins minus 5 mins)
now_utc = datetime.now(timezone.utc)
start_date_utc = now_utc.replace(minute=(now_utc.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)
with DAG(
    dag_id='dag_log_eda',
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    is_paused_upon_creation=False,
    tags=['s3', 'validation', 'etl'],
) as dag:
    task = PythonOperator(
        task_id="perform_dask_eda_and_save_to_s3",
        python_callable=perform_dask_eda_and_save_to_s3
    )
