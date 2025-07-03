import boto3
import json
import subprocess
import requests
import os

# --- Configuration ---
SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/141134438799/rca-queue"
AWS_REGION = "us-east-1"
DAG_ID = "dag_log_rca_orchestrator"
AIRFLOW_POD_LABEL = "component=webserver"  # or scheduler
NAMESPACE = "airflow"

# --- Get Airflow Pod name ---
def get_airflow_pod_name():
    cmd = [
        "kubectl", "get", "pods",
        "-n", NAMESPACE,
        "-l", AIRFLOW_POD_LABEL,
        "-o", "jsonpath={.items[0].metadata.name}"
    ]
    return subprocess.check_output(cmd).decode("utf-8").strip()

# --- Trigger Airflow DAG ---
def trigger_dag(pod_name, dag_id, conf=None):
    try:
        base_cmd = ["kubectl", "exec", "-n", NAMESPACE, pod_name, "--", "airflow", "dags", "trigger", dag_id]
        if conf:
            conf_json = json.dumps(conf)
            base_cmd += ["--conf", conf_json]
        subprocess.run(base_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error triggering DAG {dag_id} in pod {pod_name}: {e}")


def trigger_dag_by_api(conf=None):
    AIRFLOW_API_BASE = "http://airflow-webserver.airflow.svc.cluster.local:8080/api/v1"
    url = f"{AIRFLOW_API_BASE}/dags/{DAG_ID}/dagRuns"
    payload = {
        "conf": conf or {},
    }
    print (f"Started to invoke based on Rest API: URL: {url} and payload: {conf}")
    response = requests.post(url, json=payload, auth=("admin", "admin"))  # if using basic auth
    print("Status:", response.status_code)
    print("Response:", response.text)
    response.raise_for_status()

# --- Main logic ---
def main():
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    print(f"Consuming message from Queue : {SQS_QUEUE_URL}")
    response = sqs.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=10
    )

    messages = response.get("Messages", [])
   
    if not messages:
        print("No messages found.")
        return

    for msg in messages:
        receipt_handle = msg["ReceiptHandle"]
        body = json.loads(msg["Body"])
        print("Received SQS message:", body)
        
        if 'retrain_model' in msg['Body']:
            print('Triggering retrain...')
            pod_name = get_airflow_pod_name()
            print("Triggering DAG in pod:", pod_name)

            try:
                trigger_dag()
                print(f"DAG {DAG_ID} triggered successfully.")
                sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
            except subprocess.CalledProcessError as e:
                print("Error triggering DAG:", e)
                

        else:
            print('No retrain command found.')

if __name__ == "__main__":
    main()
