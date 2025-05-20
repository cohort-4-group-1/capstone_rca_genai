import boto3
import pandas as pd

SOURCE_BUCKET = 'datasets.mlops'
DEST_BUCKET = 'datasets.mlops'
FILE_KEY = 'Raw (Bronze)/OpenStack_2k.log'
OUTPUT_KEY = 'Cleansed (Silver)/OpenStack_cleaned.csv'
AWS_REGION = 'us-east-1'

def read_raw_log_from_s3():
    print(f"Started to read file from S3 bucket: {SOURCE_BUCKET}")
    s3 = boto3.client('s3', region_name=AWS_REGION)
    print("Create S3 object")
    obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=FILE_KEY)
    print(f"Successfully read file from S3 bucket: {SOURCE_BUCKET} , File Key {FILE_KEY}")
    print("Started to read raw file in Dataframe")
    df = pd.read_csv(obj['Body'], sep=',', header=None)
    print("Genared Dataframe")
    print(df.head(10))

if __name__ == "__main__":
        read_raw_log_from_s3()
