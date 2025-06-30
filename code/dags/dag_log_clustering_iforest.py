# dag_log_clustering_iforest.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import IsolationForest
import boto3
import tempfile
import configuration
import os
import numpy as np
import mlflow
import optuna
import io


S3_BUCKET = configuration.DEST_BUCKET
S3_MODEL_PATH = configuration.CLUSTERING_MODEL_OUTPUT
LOCAL_MODEL_PATH = "/tmp/log_kmeans_model.pkl"
DATA_PATH = f"s3://{configuration.DEST_BUCKET}/{configuration.LOG_SEQUENCE__FILE_KEY}"

MLFLOW_TRACKING_URI = "http://mlflow.mlflow.svc.cluster.local:5000"

N_ESTIMATOR_RANGE = (100, 300)
CONTAMINATION_RANGE = (0.01, 0.1)
MAX_SAMPLES_CHOICES = ["auto", 0.8, 1.0]
N_JOBS = -1
N_TRIALS=10
LOCAL_MODEL_PATH = "/tmp/log_isolation_model.pkl"

def train_isolation_forest():
    s3 = boto3.client("s3")
    print("Started training rca model using clustering based on isolation forest")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("openstack-log-anomaly-isolation-forest")

    print(f"started to read log sequence for model input from {DATA_PATH}")
    # Read logs from S3
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=S3_BUCKET, Key=configuration.LOG_SEQUENCE__FILE_KEY)
    df = pd.read_csv(io.BytesIO(response['Body'].read()))
    sequences = df["sequence"].astype(str).tolist()

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(sequences)

    def objective(trial):
        n_estimators = trial.suggest_int("n_estimators", *N_ESTIMATOR_RANGE)
        contamination = trial.suggest_float("contamination", *CONTAMINATION_RANGE)
        max_samples = trial.suggest_categorical("max_samples", MAX_SAMPLES_CHOICES)

        model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            max_samples=max_samples,
            random_state=42,
            n_jobs=N_JOBS
        )
        model.fit(X)
        scores = -model.decision_function(X)
        avg_score = float(np.mean(scores))

        mlflow.log_params({
            "n_estimators": n_estimators,
            "contamination": contamination,
            "max_samples": max_samples
        })
        mlflow.log_metric("avg_anomaly_score", avg_score)

        return avg_score

    study = optuna.create_study(direction="maximize")
    with mlflow.start_run():
        study.optimize(objective, n_trials=N_TRIALS)

    best_params = study.best_params
    iforest = IsolationForest(
        **best_params,
        random_state=42,
        n_jobs=N_JOBS
    )
    iforest.fit(X)

    joblib.dump((vectorizer, iforest), LOCAL_MODEL_PATH)
    print(f"started to upload the model in s3")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    versioned_path = f"{configuration.ISOLATION_FOREST_MODEL_OUTPUT}.pkl" 
    s3.upload_file(
        LOCAL_MODEL_PATH,
        configuration.DEST_BUCKET,versioned_path
    )

    os.remove(LOCAL_MODEL_PATH)

    print(f"✅ Best IsolationForest model uploaded. Best score: {study.best_value:.4f}, Params: {best_params}")

# DAG Schedule
now = datetime.now(timezone.utc)
start_time = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)
with DAG(
    dag_id="dag_log_clustering_iforest",
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    is_paused_upon_creation=False,
    tags=["model", "iforest", "optuna"]
) as dag:

    train_model_task = PythonOperator(
        task_id="train_isolation_forest_model",
        python_callable=train_isolation_forest
    )
