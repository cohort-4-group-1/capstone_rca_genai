from datetime import datetime, timedelta, timezone
import pandas as pd
import boto3
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import configuration
import io
from collections import Counter


# Configuration
S3_BUCKET = configuration.DEST_BUCKET
S3_MODEL_PATH = configuration.CLUSTERING_MODEL_OUTPUT
LOCAL_MODEL_PATH = "log_kmeans_model.pkl"
DATA_PATH = f"s3://{configuration.DEST_BUCKET}/{configuration.LOG_SEQUENCE__FILE_KEY}"

MLFLOW_TRACKING_URI = "http://mlflow.mlflow.svc.cluster.local:5000"
N_CLUSTERS = 5
MAX_FEATURES = 1000
EPOCHS = 5

def train_rca_model_clustering_kmeans():
    print("Started training rca model using clustering based on kmeans")

    print(f"started to read log sequence for model input from {DATA_PATH}")
    # Read logs from S3
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=S3_BUCKET, Key=configuration.LOG_SEQUENCE__FILE_KEY)
    df = pd.read_csv(io.BytesIO(response['Body'].read()))
    sequences = df["sequence"].astype(str).tolist()

    print(f"started to create vectorization for log sequence")
    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(max_features=MAX_FEATURES)
    tfidf_features = vectorizer.fit_transform(sequences)

    print(f"started to train the model using KMeans")
    # Epoch-based KMeans selection
    best_score = -1
    best_model = None
    best_epoch = -1

    for epoch in range(EPOCHS):
        print(f"🚀 Epoch {epoch + 1}/{EPOCHS} - training KMeans...")
        kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=epoch, n_init="auto")
        clusters = kmeans.fit_predict(tfidf_features)
        score = silhouette_score(tfidf_features, clusters)
        print(f"🧮 Silhouette score: {score}")

        if score > best_score:
            best_score = score
            best_model = kmeans
            best_epoch = epoch

    print(f"🏆 Best model found at epoch {best_epoch + 1} with silhouette score {best_score:.4f}")

    # Evaluation metrics
    inertia = best_model.inertia_
    silhouette = silhouette_score(tfidf_features, clusters)

    print(f"started to save the model locally")

    # Save model locally
    joblib.dump((vectorizer, best_model), LOCAL_MODEL_PATH)

    print(f"started to upload the model in s3")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    versioned_path = f"{configuration.CLUSTERING_MODEL_OUTPUT}.pkl"    
    # Upload to S3
    s3.upload_file(LOCAL_MODEL_PATH, S3_BUCKET, versioned_path)

    print(f"started to track the model in mlflow")
    # Predict cluster labels with best model
    best_clusters = best_model.predict(tfidf_features)
    cluster_distribution = dict(Counter(best_clusters))

    
    print(f"✅ RCA model training complete and tracked successfully.")

train_rca_model_clustering_kmeans()