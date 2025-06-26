from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import boto3
import pandas as pd
import io
import joblib
import mlflow
import tensorflow as tf
from tensorflow.keras import layers, models
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from collections import Counter
from datetime import datetime
import configuration
import matplotlib.pyplot as plt

print(f"Tensor flow version: {tf.__version__}")
# --- Configuration ---
S3_BUCKET = configuration.DEST_BUCKET
S3_KEY = configuration.LOG_SEQUENCE__FILE_KEY
S3_MODEL_KEY = configuration.DEEP_KMEANS_MODEL_OUTPUT
LOCAL_MODEL_PATH = "/tmp/autoencoder_kmeans_model.pkl"
MLFLOW_TRACKING_URI = "http://mlflow.mlflow.svc.cluster.local:5000"
LATENT_DIM = 32
MAX_FEATURES = 1000
N_CLUSTERS = 5
EPOCHS = 30
BATCH_SIZE = 64


# --- Autoencoder Architecture ---
def build_autoencoder(input_dim, latent_dim):
    input_layer = layers.Input(shape=(input_dim,))
    x = layers.Dense(512, activation='relu')(input_layer)
    x = layers.Dense(128, activation='relu')(x)
    latent = layers.Dense(latent_dim, activation='relu', name='latent_space')(x)
    x = layers.Dense(128, activation='relu')(latent)
    x = layers.Dense(512, activation='relu')(x)
    output_layer = layers.Dense(input_dim, activation='sigmoid')(x)

    autoencoder = models.Model(input_layer, output_layer)
    encoder = models.Model(input_layer, latent)
    autoencoder.compile(optimizer='adam', loss='mse')
    return autoencoder, encoder


def plot_training_curves(history, output_path):
    plt.figure(figsize=(8, 5))
    plt.plot(history.history['loss'], label='Train Loss')
    if 'val_loss' in history.history:
        plt.plot(history.history['val_loss'], label='Validation Loss')
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Training Curve")
    plt.legend()
    plt.grid(True)
    plt.savefig(output_path)
    plt.close()

def train_autoencoder_kmeans_pipeline():
    print("🚀 Starting autoencoder + KMeans pipeline")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("openstack-log-anomaly-deep")

    # Read log sequences from S3
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
    df = pd.read_csv(io.BytesIO(response['Body'].read()))
    sequences = df["sequence"].astype(str).tolist()

    print("Converting logs to TF-IDF vectors")
    vectorizer = TfidfVectorizer(max_features=MAX_FEATURES)
    X = vectorizer.fit_transform(sequences).toarray()

    print("Building and training autoencoder")
    autoencoder, encoder = build_autoencoder(input_dim=X.shape[1], latent_dim=LATENT_DIM)
    history = autoencoder.fit(
        X, X,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_split=0.1,
        shuffle=True,
        verbose=1,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True),
        ]
    )

    print("🔎 Extracting latent features and applying KMeans")
    latent_vectors = encoder.predict(X)
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init="auto")
    cluster_labels = kmeans.fit_predict(latent_vectors)
    silhouette = silhouette_score(latent_vectors, cluster_labels)
    print(f"Silhouette score: {silhouette:.4f}")

    encoder_path = "/tmp/encoder_model.keras"
    encoder.save(encoder_path, save_format="keras")
    joblib.dump((vectorizer,kmeans), LOCAL_MODEL_PATH)

    s3.upload_file(encoder_path, S3_BUCKET, f"{S3_MODEL_KEY}.encoder.keras")
    s3.upload_file(LOCAL_MODEL_PATH, S3_BUCKET, f"{S3_MODEL_KEY}.pkl")

    print(f"☁️ Model uploaded to s3://{S3_BUCKET}/{S3_MODEL_KEY}")
    curve_path = "/tmp/loss_curve.png"
    plot_training_curves(history, curve_path)
    print("📦 Logging model and metrics to MLflow")
    with mlflow.start_run():
        mlflow.log_param("latent_dim", LATENT_DIM)
        mlflow.log_param("max_features", MAX_FEATURES)
        mlflow.log_param("n_clusters", N_CLUSTERS)
        mlflow.log_param("epochs", EPOCHS)
        mlflow.log_param("batch_size", BATCH_SIZE)
        mlflow.log_metric("silhouette_score", silhouette)
        for i, loss in enumerate(history.history['loss']):
            mlflow.log_metric("train_loss", loss, step=i)

        if 'val_loss' in history.history:
            for i, val_loss in enumerate(history.history['val_loss']):
                mlflow.log_metric("val_loss", val_loss, step=i)

        for cluster_id, count in Counter(cluster_labels).items():
            mlflow.log_metric(f"cluster_{cluster_id}_count", count)

        mlflow.log_artifact(LOCAL_MODEL_PATH)
        mlflow.log_artifact(curve_path)
        mlflow.set_tag("s3_model_path", f"s3://{S3_BUCKET}/{S3_MODEL_KEY}")

    print("✅ Training complete")

# DAG Schedule
now = datetime.now(timezone.utc)
start_time = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)

with DAG(
    dag_id="dag_log_deep_network_clustering_kmeans",
    start_date=start_time,
    schedule_interval="@daily",
    catchup=False,
    tags=["log-anomaly", "deep-neural", "kmeans", "mlflow"],
) as dag:
    train_task = PythonOperator(
        task_id="train_rca_model_deep_network_clustering_kmeans",
        python_callable=train_autoencoder_kmeans_pipeline
    )

