from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
from io import StringIO
import pandas as pd
import boto3
import re
import configuration  

def read_raw_log_from_datalake(**kwargs):
    print(f"Reading file from S3: {configuration.SOURCE_BUCKET}/{configuration.RAW_FILE_KEY}")
    s3 = boto3.client('s3', region_name=configuration.AWS_REGION)
    obj = s3.get_object(Bucket=configuration.SOURCE_BUCKET, Key=configuration.RAW_FILE_KEY)
    
    log_text = obj['Body'].read().decode('utf-8')
    print("Successfully read log file from S3")
    
    # Push raw log text via XCom
    kwargs['ti'].xcom_push(key='raw_log_text', value=log_text)

def convert_raw_log_to_csv(**kwargs):
    read_raw_log_from_datalake(**kwargs)
    raw_log = kwargs['ti'].xcom_pull(task_ids='read_log_from_raw_datalake', key='raw_log_text')
    
    pattern = re.compile(
        r'(?P<source>[^\s]+)\s+'
        r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\s+'
        r'(?P<pid>\d+)\s+'
        r'(?P<level>[A-Z]+)\s+'
        r'(?P<component>[^\[]+)\s*'
        r'(?:\[(?P<request_id>[^\]]+)\])?\s*'
        r'(?P<message>.*)'
    )

    rows = []
    for line in raw_log.splitlines():
        match = pattern.match(line)
        if match:
            rows.append(match.groupdict())

    df = pd.DataFrame(rows)
    
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_string = csv_buffer.getvalue()

    kwargs['ti'].xcom_push(key='parsed_log_csv', value=csv_string)
    print("CSV conversion complete.")
    upload_csv_to_silver_datalake()

def upload_csv_to_silver_datalake(kwargs):
    csv_data = kwargs['ti'].xcom_pull(task_ids='convert_raw_log_to_csv', key='parsed_log_csv')
    
    s3 = boto3.client('s3', region_name=configuration.AWS_REGION)
    s3.put_object(
        Bucket=configuration.DEST_BUCKET,
        Key=configuration.SILVER_FILE_KEY,
        Body=csv_data.encode('utf-8')
    )
    print(f"CSV uploaded to S3: {configuration.DEST_BUCKET}/{configuration.SILVER_FILE_KEY}")

# DAG Start Time (rounded down to nearest 30 mins minus 5 mins)
now_utc = datetime.now(timezone.utc)
start_date_utc = now_utc.replace(minute=(now_utc.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)

with DAG(
    dag_id='dag_log_parse',
    start_date=start_date_utc,
    schedule_interval="*/30 * * * *",
    catchup=False,
    tags=['s3', 'validation', 'etl'],
) as dag:

    parse_raw_log = PythonOperator(
        task_id='parse_convert_raw_log_to_structured',
        python_callable=convert_raw_log_to_csv
    )
    parse_raw_log
