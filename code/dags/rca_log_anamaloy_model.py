from transformers import BertTokenizer, TFBertModel
import tensorflow as tf
import pandas as pd
import mlflow
import mlflow.tensorflow
from sklearn.model_selection import train_test_split
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import os
import configuration
import numpy as np
from huggingface_hub import HfApi, HfFolder, upload_folder

# Configuration
MODEL_NAME = "bert-base-uncased"
EPOCHS = 5
BATCH_SIZE = 16
MAX_LEN = 128
LEARNING_RATE = 2e-5
DATA_PATH = f"s3://{configuration.DEST_BUCKET}/{configuration.LOG_SEQUENCE__FILE_KEY}"
HUGGINGFACE_MODEL_DIR = "rca_logbert_model"
HF_REPO_ID = "sujit6779/rca_log"
HF_TOKEN = os.getenv("HF_TOKEN")  # Set this in Airflow env

# Define training function
def train_logbert():
    mlflow.set_tracking_uri("http://mlflow.mlflow.svc.cluster.local:5000")
    mlflow.tensorflow.autolog()

    # Load tokenizer and model
    tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)
    bert_model = TFBertModel.from_pretrained(MODEL_NAME)

    # Load session sequences (no labels needed)
    df = pd.read_csv(DATA_PATH)
    sequences = df["sequence"].tolist()

    # Tokenize all sequences
    tokens = tokenizer(
        sequences,
        max_length=MAX_LEN,
        padding="max_length",
        truncation=True,
        return_tensors="tf"
    )

    input_ids = tokens["input_ids"]
    attention_mask = tokens["attention_mask"]

    input_ids_np = input_ids.numpy()
    attention_mask_np = attention_mask.numpy()

    # Split into train/val sets
    train_ids, val_ids, train_mask, val_mask = train_test_split(
        input_ids_np, attention_mask_np, test_size=0.2, random_state=42
    )

    # Convert to tensors
    train_ids = tf.convert_to_tensor(train_ids)
    train_mask = tf.convert_to_tensor(train_mask)
    val_ids = tf.convert_to_tensor(val_ids)
    val_mask = tf.convert_to_tensor(val_mask)

    # Define autoencoder using Functional API
    input_ids_in = tf.keras.Input(shape=(MAX_LEN,), dtype=tf.int32, name="input_ids")
    attention_mask_in = tf.keras.Input(shape=(MAX_LEN,), dtype=tf.int32, name="attention_mask")
    bert_output = bert_model(input_ids=input_ids_in, attention_mask=attention_mask_in)
    cls_token = bert_output.last_hidden_state[:, 0, :]
    encoded = tf.keras.layers.Dense(768, activation="relu")(cls_token)
    reconstructed = tf.keras.layers.Dense(768)(encoded)

    model = tf.keras.Model(inputs=[input_ids_in, attention_mask_in], outputs=reconstructed)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
                  loss=tf.keras.losses.MeanSquaredError())

    # Define checkpoint callback
    checkpoint_cb = tf.keras.callbacks.ModelCheckpoint(
        filepath="rca_logbert_model",
        save_best_only=True,
        monitor="val_loss",
        mode="min",
        verbose=1,
        save_format="tf"
    )

    # Start MLflow run
    with mlflow.start_run():
        history = model.fit(
            x={"input_ids": train_ids, "attention_mask": train_mask},
            y=model({"input_ids": train_ids, "attention_mask": train_mask}),
            validation_data=(
                {"input_ids": val_ids, "attention_mask": val_mask},
                model({"input_ids": val_ids, "attention_mask": val_mask})
            ),
            batch_size=BATCH_SIZE,
            epochs=EPOCHS,
            callbacks=[checkpoint_cb]
        )
        train_loss = history.history['loss'][-1]
        val_loss = history.history['val_loss'][-1]

        mlflow.log_metric("final_train_loss", train_loss)
        mlflow.log_metric("final_val_loss", val_loss)
        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("epochs", EPOCHS)
        mlflow.log_param("batch_size", BATCH_SIZE)
        mlflow.log_param("max_len", MAX_LEN)
        mlflow.log_param("learning_rate", LEARNING_RATE)
        mlflow.tensorflow.log_model(tf_saved_model_dir="logbert_autoencoder_best", artifact_path="logbert_model")

    # Save full model for Hugging Face
    model.save(HUGGINGFACE_MODEL_DIR, save_format="tf")

    # Upload to Hugging Face
    if HF_TOKEN:
        HfFolder.save_token(HF_TOKEN)
        upload_folder(
            folder_path=HUGGINGFACE_MODEL_DIR,
            repo_id=HF_REPO_ID,
            repo_type="model",
            commit_message="Upload full trained LogBERT autoencoder"
        )
        print(f"✅ Model uploaded to https://huggingface.co/{HF_REPO_ID}")
    else:
        print("⚠️ HF_TOKEN not set. Skipping upload to Hugging Face.")

# DAG Start Time (rounded down to nearest 30 mins minus 5 mins)
now_utc = datetime.now(timezone.utc)
start_date_utc = now_utc.replace(minute=(now_utc.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)

with DAG(
    dag_id='rca_anamoly_logbert_model_train',
    start_date=start_date_utc,
    schedule_interval="@daily",
    catchup=False,
    tags=['logbert', 'mlflow', 'tensorflow']
) as dag:
    training_task = PythonOperator(
        task_id="train_logbert",
        python_callable=train_logbert
    )
