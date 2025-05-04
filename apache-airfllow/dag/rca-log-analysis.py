from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
import boto3
import great_expectations as ge
from io import BytesIO
from sklearn.impute import SimpleImputer

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

def validate_data(**kwargs):
    df_json = kwargs['ti'].xcom_pull(task_ids='read_raw_log_from_s3', key='raw_df')
    df = pd.read_json(df_json)

    ge_df = ge.from_pandas(df)
    result = ge_df.expect_table_row_count_to_be_between(min_value=1, max_value=1e6)

    if not result.success:
        raise ValueError("Validation failed: Row count out of range")

    kwargs['ti'].xcom_push(key='validated_df', value=df.to_json())

def impute_missing(**kwargs):
    df_json = kwargs['ti'].xcom_pull(task_ids='read_raw_log_from_s3', key='raw_df')
    df = pd.read_json(df_json)
    numeric_df = df.select_dtypes(include=['float64', 'int64'])
    if not numeric_df.empty:
        imputer = SimpleImputer(strategy='mean')
        imputed_data = imputer.fit_transform(numeric_df)
        df[numeric_df] = imputed_data
    
    kwargs['ti'].xcom_push(key='cleaned_df', value=df.to_csv(index=False))

def upload_to_s3(**kwargs):
    cleaned_csv = kwargs['ti'].xcom_pull(task_ids='impute_data', key='cleaned_df')
    s3 = boto3.client('s3', region_name=AWS_REGION)
    s3.put_object(Bucket=DEST_BUCKET, Key=OUTPUT_KEY, Body=cleaned_csv.encode())

with DAG(
    dag_id='rca-log-preprocess',
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=['s3', 'validation', 'etl'],
) as dag:

    t1 = PythonOperator(
        task_id='read_raw_log_from_s3',
        python_callable=read_raw_log_from_s3,
        provide_context=True
    )
    
    t3 = PythonOperator(
        task_id='impute_data',
        python_callable=impute_missing,
        provide_context=True
    )

    t4 = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_to_s3,
        provide_context=True
    )

    t1 >>  t3 >> t4
