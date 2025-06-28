from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import boto3
import json

def send_to_sqs(**context):
    # SQS setup
    sqs = boto3.client('sqs', region_name='us-east-1')  # Set your region
    queue_url = 'https://sqs.us-east-1.amazonaws.com/141134438799/rca-queue'  # Replace with your queue URL

    # Optional: pass dynamic values using context or config
    message_body = {
        'task': 'airflow_trigger',
        'timestamp': str(datetime.utcnow()),
        'extra': context.get('dag_run').conf if context.get('dag_run') else {},
        'message': 'model_updated'
    }

    # Send message
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )
    print(f"Message sent: {response['MessageId']}")

# Define the DAG
with DAG(
    dag_id='send_sqs_message_dag',
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,  # Trigger manually or externally
    catchup=False,
    is_paused_upon_creation=False,
    tags=["sqs", "aws"],
) as dag:

    send_message = PythonOperator(
        task_id='send_message_to_sqs',
        python_callable=send_to_sqs,
        provide_context=True,
    )
