import pandas as pd
import boto3
from io import StringIO
import configuration
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone

def generate_log_sequence():
    s3 = boto3.client('s3')
    structured_key = configuration.STRUCTURED_WITH_LOG_KEY
    bucket = configuration.DEST_BUCKET

    response = s3.get_object(Bucket=bucket, Key=structured_key)
    df = pd.read_csv(response['Body'])

    template_key = configuration.TEMPLATE_FILE_KEY
    response = s3.get_object(Bucket=bucket, Key=template_key)
    template_df = pd.read_csv(response['Body'])
    logkey_to_template = dict(zip(template_df['LogKey'], template_df['Template']))
    
    df["template_text"] = df["LogKey"].map(logkey_to_template)
    
    session_df = df.groupby("request_id")["template_text"].apply(lambda x: " ".join(x)).reset_index()
    session_df.columns = ["session_id", "sequence"]

    csv_buffer = StringIO()
    session_df.to_csv(csv_buffer, index=False)
    s3.put_object(Bucket=bucket, Key=configuration.LOG_SEQUENCE__FILE_KEY, Body=csv_buffer.getvalue())
    print("✅ LogBERT input saved to S3: gold/logbert_template_text_input.csv")

# DAG Start Time (rounded down to nearest 30 mins minus 5 mins)
now_utc = datetime.now(timezone.utc)
start_date_utc = now_utc.replace(minute=(now_utc.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)
with DAG(
    dag_id='dag_log_sequence',
    start_date=start_date_utc,
    schedule_interval="*/30 * * * *",
    catchup=False,
    tags=['s3', 'log_template', 'log_sequence'],
) as dag:
    generate_log_sequence = PythonOperator(
        task_id='generate_log_sequence',
        python_callable=generate_log_sequence
    )
    generate_log_sequence