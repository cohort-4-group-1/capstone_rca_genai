from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import boto3
import pandas as pd
import io
import great_expectations as ge
from sklearn.impute import SimpleImputer
import seaborn as sns
import matplotlib.pyplot as plt
import os

# DAG default args
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
}

# S3 setup
source_bucket = 'Raw (Bronze)'
source_key = 'OpenStack_2k.log'
dest_bucket = 'Cleansed (Silver)'
dest_key = 'processed/OpenStack_cleaned.csv'

def process_s3_file(**kwargs):
    s3 = boto3.client('s3')

    # Step 1: Read file
    obj = s3.get_object(Bucket=source_bucket, Key=source_key)
    raw_data = obj['Body'].read().decode('utf-8')

    # Step 2: Parse log to dataframe (adjust as needed)
    try:
        df = pd.read_csv(io.StringIO(raw_data), sep=r'\s+', engine='python')
    except Exception as e:
        raise ValueError("Parsing failed: check file format") from e

    # Step 3: Validate with Great Expectations
    df_ge = ge.from_pandas(df)
    validation_result = df_ge.expect_table_row_count_to_be_between(min_value=1, max_value=100000)
    if not validation_result.success:
        raise ValueError("Validation failed.")

    # Step 4: Impute missing values
    if df.isnull().sum().sum() > 0:
        imputer = SimpleImputer(strategy='mean')
        df[df.columns] = imputer.fit_transform(df)

    # Step 5: EDA plots
    eda_dir = "/tmp/eda_plots"
    os.makedirs(eda_dir, exist_ok=True)
    for col in df.select_dtypes(include='number').columns:
        plt.figure(figsize=(8, 4))
        sns.histplot(df[col], kde=True)
        plt.title(f"Distribution of {col}")
        plt.savefig(f"{eda_dir}/{col}_dist.png")
        plt.close()

    # Step 6: Upload cleaned data
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.put_object(Bucket=dest_bucket, Key=dest_key, Body=csv_buffer.getvalue())

    print(f"✅ Data uploaded to s3://{dest_bucket}/{dest_key}")

# Define DAG
with DAG(
    dag_id='s3_data_cleaning_pipeline',
    default_args=default_args,
    schedule_interval=None,  # Manual trigger
    catchup=False,
    tags=['s3', 'great_expectations', 'eda']
) as dag:

    run_pipeline = PythonOperator(
        task_id='process_and_clean_file',
        python_callable=process_s3_file,
        provide_context=True
    )

    run_pipeline
