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
import optuna
import io


S3_BUCKET = configuration.DEST_BUCKET
S3_MODEL_PATH = configuration.CLUSTERING_MODEL_OUTPUT
LOCAL_MODEL_PATH = "/tmp/log_kmeans_model.pkl"
DATA_PATH = f"s3://{configuration.DEST_BUCKET}/{configuration.LOG_SEQUENCE__FILE_KEY}"


N_ESTIMATOR_RANGE = (100, 300)
CONTAMINATION_RANGE = (0.01, 0.1)
MAX_SAMPLES_CHOICES = ["auto", 0.8, 1.0]
N_JOBS = -1
N_TRIALS=10
LOCAL_MODEL_PATH = "log_isolation_model.pkl"

def train_isolation_forest():
    s3 = boto3.client("s3")
    print("Started training rca model using clustering based on isolation forest")

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
        return avg_score

    study = optuna.create_study(direction="maximize")
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

train_isolation_forest()
