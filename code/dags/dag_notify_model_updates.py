from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import boto3
import json
from otel import tracer, meter, logger

def send_to_sqs(**context):
    with tracer.start_as_current_span("send_to_sqs") as span:
        span.set_attribute("function", "send_to_sqs")
        logger.info("Sending message to SQS queue")
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
        logger.info(f"Message sent: {response['MessageId']}")

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
