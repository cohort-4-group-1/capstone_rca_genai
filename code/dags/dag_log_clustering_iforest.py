from datetime import datetime
import os
import joblib
import mlflow
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import numpy as np
import pandas as pd
import boto3
from io import BytesIO
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago
from botocore.exceptions import NoCredentialsError
import configuration
import tempfile
import optuna

S3_BUCKET = configuration.DEST_BUCKET
DRAIN3_TEMPLATES_KEY = configuration.TEMPLATE_DRAIN_FILE_KEY
LOG_VECTOR_KEY = configuration.ISOLATION_FOREST_TRAIN_VECTOR_KEY
MODEL_OUTPUT_NAME = configuration.ISOLATION_FOREST_MODEL_OUTPUT

mlflow.set_tracking_uri(configuration.MLFLOW_TRACKING_URI)
mlflow.set_experiment("log_clustering_iforest")

def load_training_data():
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=S3_BUCKET, Key=LOG_VECTOR_KEY)
    X = joblib.load(BytesIO(obj["Body"].read()))
    return X

def save_model_to_s3(vectorizer, model):
    s3 = boto3.client("s3")
    with tempfile.NamedTemporaryFile(suffix=".pkl") as temp_file:
        joblib.dump((vectorizer, model), temp_file)
        temp_file.flush()
        s3.upload_file(temp_file.name, S3_BUCKET, f"{MODEL_OUTPUT_NAME}.pkl")

def objective(trial):
    X = load_training_data()
    contamination = trial.suggest_float("contamination", 0.001, 0.2)
    n_estimators = trial.suggest_int("n_estimators", 50, 300)
    max_samples = trial.suggest_float("max_samples", 0.1, 1.0)

    iforest = IsolationForest(
        contamination=contamination,
        n_estimators=n_estimators,
        max_samples=max_samples,
        random_state=42
    )

    with mlflow.start_run(nested=True):
        iforest.fit(X)
        scores = -iforest.decision_function(X)
        avg_score = float(np.mean(scores))
        std_score = float(np.std(scores))
        iqr_score = float(np.percentile(scores, 75) - np.percentile(scores, 25))

        preds = iforest.predict(X)
        anomaly_count = int((preds == -1).sum())
        normal_count = int((preds == 1).sum())
        anomaly_ratio = anomaly_count / len(preds)

        kmeans_labels = KMeans(n_clusters=5, random_state=42).fit_predict(X)
        sil_score = silhouette_score(X, kmeans_labels)
        _, counts = np.unique(kmeans_labels, return_counts=True)
        entropy = -np.sum((counts / len(X)) * np.log2(counts / len(X)))

        mlflow.log_metrics({
            "avg_anomaly_score": avg_score,
            "std_anomaly_score": std_score,
            "iqr_anomaly_score": iqr_score,
            "anomaly_ratio": anomaly_ratio,
            "n_anomalies": anomaly_count,
            "n_normals": normal_count,
            "silhouette_score": sil_score,
            "cluster_entropy": entropy
        })
        for i, count in enumerate(counts):
            mlflow.log_metric(f"cluster_{i}_count", count)

        mlflow.log_params({
            "contamination": contamination,
            "n_estimators": n_estimators,
            "max_samples": max_samples
        })

        return avg_score

def train_and_log_iforest():
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=20)

    best_params = study.best_params
    X = load_training_data()
    iforest = IsolationForest(**best_params, random_state=42)
    iforest.fit(X)

    with mlflow.start_run():
        mlflow.log_params(best_params)
        mlflow.log_metric("best_avg_anomaly_score", study.best_value)

        # Evaluate best model again for logging final metrics to main run
        scores = -iforest.decision_function(X)
        avg_score = float(np.mean(scores))
        std_score = float(np.std(scores))
        iqr_score = float(np.percentile(scores, 75) - np.percentile(scores, 25))

        preds = iforest.predict(X)
        anomaly_count = int((preds == -1).sum())
        normal_count = int((preds == 1).sum())
        anomaly_ratio = anomaly_count / len(preds)

        kmeans_labels = KMeans(n_clusters=5, random_state=42).fit_predict(X)
        sil_score = silhouette_score(X, kmeans_labels)
        _, counts = np.unique(kmeans_labels, return_counts=True)
        entropy = -np.sum((counts / len(X)) * np.log2(counts / len(X)))

        mlflow.log_metrics({
            "final_avg_anomaly_score": avg_score,
            "final_std_anomaly_score": std_score,
            "final_iqr_anomaly_score": iqr_score,
            "final_anomaly_ratio": anomaly_ratio,
            "final_n_anomalies": anomaly_count,
            "final_n_normals": normal_count,
            "final_silhouette_score": sil_score,
            "final_cluster_entropy": entropy
        })
        for i, count in enumerate(counts):
            mlflow.log_metric(f"final_cluster_{i}_count", count)

        save_model_to_s3(vectorizer=None, model=iforest)

with DAG(
    dag_id="dag_log_clustering_iforest",
    schedule_interval=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["unsupervised", "isolation_forest", "logs"]
) as dag:

    train_and_log_task = PythonOperator(
        task_id="train_and_log_iforest",
        python_callable=train_and_log_iforest
    )

    train_and_log_task
