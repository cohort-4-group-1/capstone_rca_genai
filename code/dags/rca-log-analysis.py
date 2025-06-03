from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
import boto3

from io import BytesIO


# S3 config
SOURCE_BUCKET = 'datasets.mlops'
DEST_BUCKET = 'datasets.mlops'
FILE_KEY = 'Raw (Bronze)/OpenStack_2k.log_structured.csv'
OUTPUT_KEY = 'Cleansed (Silver)/OpenStack_cleaned.csv'
AWS_REGION = 'us-east-1'

def read_raw_log_from_s3(**kwargs):
    print(f"Started to read file from S3 bucket: {SOURCE_BUCKET}")
    s3 = boto3.client('s3', region_name=AWS_REGION)
    print("Create S3 object")
    obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=FILE_KEY)
    print(f"Successfully read file from S3 bucket: {SOURCE_BUCKET} , File Key {FILE_KEY}")
    print("Started to read CSV file in Dataframe")
    df = pd.read_csv(obj['Body'], sep=',', header=None)
    print("Genared Dataframe")

    print(df.head(10))
    kwargs['ti'].xcom_push(key='raw_df', value=df.to_json())

def upload_to_s3(**kwargs):
    cleaned_csv = kwargs['ti'].xcom_pull(task_ids='read_raw_log_from_s3', key='raw_df')
    s3 = boto3.client('s3', region_name=AWS_REGION)
    s3.put_object(Bucket=DEST_BUCKET, Key=OUTPUT_KEY, Body=cleaned_csv.encode())

with DAG(
    dag_id='rca-log-preprocess-pipeline',
    start_date=datetime(2025, 6, 3),
    schedule_interval="*/30 * * * *",  # Runs every 2 minutes
    catchup=False,
    tags=['s3', 'validation', 'etl'],
) as dag:

    t1 = PythonOperator(
        task_id='read_raw_log_from_s3',
        python_callable=read_raw_log_from_s3,
        provide_context=True
    )
    

    t2 = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_to_s3,
        provide_context=True
    )

    t1 >> t2 
