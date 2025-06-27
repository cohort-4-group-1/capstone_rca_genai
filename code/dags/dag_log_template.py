from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
import boto3
import configuration
from io import StringIO
import pandas as pd
import os



def read_structured_log_from_datalake():
    print(" Started read_structured_log_from_datalake:")
    s3_path = f"s3://{configuration.DEST_BUCKET}/{configuration.SILVER_FILE_KEY}"
    df = pd.read_csv(s3_path)
    print(" End read_structured_log_from_datalake: csv is read")
    print(" Columns:", df.columns)  
    print(" Sample messages:\n", df['message'].dropna().head(10))
    return df 


def upload_templates_to_s3(df):
    print("Uploading templates to S3...")
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)

    s3_client = boto3.client("s3")    
    s3_client.put_object(
        Bucket=configuration.DEST_BUCKET,
        Key=configuration.TEMPLATE_FILE_KEY,
        Body=csv_buffer.getvalue()      
    )

    s3_client.upload_file(
        configuration.TEMPLATE_DRAIN_FILE,
        configuration.DEST_BUCKET,
        configuration.TEMPLATE_DRAIN_FILE_KEY        
    )


def convert_template_from_structured_log():
    df = read_structured_log_from_datalake()
    if 'message' not in df.columns:
        print("Column 'message' not found.")
        return

    log_messages = df['message'].dropna().tolist()
    if not log_messages:
        print("No log messages to process.")
        return

    persistence = FilePersistence(configuration.TEMPLATE_DRAIN_FILE)
    template_miner = TemplateMiner(persistence, config=None)

    templates_set = set()
    for log_line in log_messages:
        result = template_miner.add_log_message(log_line)
        if result["change_type"] != "none":
            templates_set.add(result["template_mined"])
    
    templates_list = [str(template) for template in templates_set]

    templates_df = pd.DataFrame({
         "LogKey": [f"LG_KEY_{i}" for i in range(1, len(templates_list)+1)],
        "Template": list(templates_set)
    })

    templates_df.to_csv("log_templates.csv", index=False)
    print("Generated templates:")
    print(templates_df.head())
    if not templates_df.empty:
      upload_templates_to_s3(templates_df)
      append_log_key_to_structured_log()

   # After s3 upload
    if os.path.exists(configuration.TEMPLATE_DRAIN_FILE):
        os.remove(configuration.TEMPLATE_DRAIN_FILE)
        print(f"Deleted local template file: {configuration.TEMPLATE_DRAIN_FILE}")
    else:
        print(f"File not found for deletion: {configuration.TEMPLATE_DRAIN_FILE}")

       # After s3 upload
    if os.path.exists(configuration.TEMPLATE_DRAIN_FILE):
        os.remove(configuration.TEMPLATE_DRAIN_FILE)
        print(f"Deleted local drain template file: {configuration.TEMPLATE_DRAIN_FILE}")
    else:
        print(f"File not found for deletion: {configuration.TEMPLATE_DRAIN_FILE}")    

# After s3 upload
if os.path.exists(configuration.TEMPLATE_FILE_KEY):
    os.remove(configuration.TEMPLATE_FILE_KEY)
    print(f"Deleted local template file: {configuration.TEMPLATE_FILE_KEY}")
else:
    print(f"File not found for deletion: {configuration.TEMPLATE_FILE_KEY}")


# After s3 upload
if os.path.exists(configuration.TEMPLATE_DRAIN_FILE):
    os.remove(configuration.TEMPLATE_DRAIN_FILE)
    print(f"✅ Deleted local template file: {configuration.TEMPLATE_DRAIN_FILE}")
else:
    print(f"⚠️ File not found for deletion: {configuration.TEMPLATE_DRAIN_FILE}")
  

def append_log_key_to_structured_log():
    print("📥 Reading structured logs and templates from S3...")

    # Read structured logs
    structured_log_path = f"s3://{configuration.DEST_BUCKET}/{configuration.SILVER_FILE_KEY}"
    structured_df = pd.read_csv(structured_log_path)

    # Read templates from S3
    s3_client = boto3.client("s3")
    template_obj = s3_client.get_object(Bucket=configuration.DEST_BUCKET, Key=configuration.TEMPLATE_FILE_KEY)
    templates_df = pd.read_csv(template_obj["Body"])

    print("✅ Structured log and templates loaded.")
    
    # Create template dictionary: template text -> log key
    template_dict = dict(zip(templates_df["Template"], templates_df["LogKey"]))

    # Setup Drain3 miner with existing state (no new learning)
    persistence = FilePersistence("log_template_state.json")  # must be consistent with training
    template_miner = TemplateMiner(persistence, config=None)

     
    def match_log_key(message):
        result = template_miner.match(message)
        if result:
            template_str = result.get_template()
            print(f"🔍 Message: {message}\n↪ Matched Template: {template_str}")
            if template_str in template_dict:
                return template_dict[template_str]
        return "UNMAPPED"
    

    print("🔎 Matching logs with templates...")
    structured_df["LogKey"] = structured_df["message"].dropna().apply(match_log_key)

    # Save enriched structured logs to S3
    print("☁️ Uploading enriched structured log with LogKey to S3...")
    csv_buffer = StringIO()
    structured_df.to_csv(csv_buffer, index=False)
    enriched_key = configuration.STRUCTURED_WITH_LOG_KEY  

    s3_client.put_object(
        Bucket=configuration.DEST_BUCKET,
        Key=enriched_key,
        Body=csv_buffer.getvalue()
    )

    print(f"✅ Enriched structured log uploaded to s3://{configuration.DEST_BUCKET}/{enriched_key}")

default_args = {
    'start_date': datetime(2024, 1, 1),
    'retries': 0
}

with DAG(
    dag_id="dag_log_template",
    schedule_interval=None,
    default_args=default_args,
    catchup=False,
    tags=["drain3", "log-parsing", "rca"],
    description="Extracts templates from structured logs and appends log key references"
) as dag:

    task = PythonOperator(
        task_id="generate_template",
        python_callable=convert_template_from_structured_log
    ) 