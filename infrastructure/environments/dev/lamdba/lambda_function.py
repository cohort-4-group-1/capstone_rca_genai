import os
import boto3
import json

sqs = boto3.client('sqs')
QUEUE_URL = os.environ['SQS_URL']

def lambda_handler(event, context):
    message_body = {
        "custom_key": "custom_value",
        "another_key": 123
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
