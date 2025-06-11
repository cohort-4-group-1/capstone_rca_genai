import pandas as pd
import boto3
from io import StringIO
import configuration

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
