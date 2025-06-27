from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
from io import StringIO
import pandas as pd
import boto3
import re
import configuration  

def convert_raw_log_to_csv(**kwargs):
    print(f"Reading file from S3: {configuration.SOURCE_BUCKET}/{configuration.RAW_FILE_KEY}")
    s3 = boto3.client('s3', region_name=configuration.AWS_REGION)
    obj = s3.get_object(Bucket=configuration.SOURCE_BUCKET, Key=configuration.RAW_FILE_KEY)
    
    raw_log = obj['Body'].read().decode('utf-8')
    print("Successfully read log file from S3")   
    
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
    print("CSV conversion complete.")
    upload_csv_to_silver_datalake(csv_string)

def upload_csv_to_silver_datalake(csv_data):    
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
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    is_paused_upon_creation=False,
    tags=['s3', 'validation', 'etl'],
) as dag:

    task = PythonOperator(
        task_id='parse_convert_raw_log_to_structured',
        python_callable=convert_raw_log_to_csv
    )

