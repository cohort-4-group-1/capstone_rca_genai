import os
import boto3
import json

sqs = boto3.client('sqs')
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/141134438799/rca-queue'

def lambda_handler(event, context):
    message_body = {
        "message": "retrain_model",
    }

    response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message_body)
    )

    return {
        'statusCode': 200,
        'body': json.dumps('Message sent to SQS!'),
        'sqsMessageId': response['MessageId']
    }
