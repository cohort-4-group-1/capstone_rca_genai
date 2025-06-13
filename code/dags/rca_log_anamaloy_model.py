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
import boto3

# Configuration
MODEL_NAME = "bert-base-uncased"
EPOCHS = 1
BATCH_SIZE = 32
MAX_LEN = 128
LEARNING_RATE = 2e-5
DATA_PATH = f"s3://{configuration.DEST_BUCKET}/{configuration.LOG_SEQUENCE__FILE_KEY}"

# Define decoder model
class LogBERTAutoencoder(tf.keras.Model):
    def __init__(self, bert_model):
        super(LogBERTAutoencoder, self).__init__()
        self.bert = bert_model
        self.dense1 = tf.keras.layers.Dense(768, activation="relu")
        self.dense2 = tf.keras.layers.Dense(768)

    def call(self, inputs):
        input_ids, attention_mask = inputs
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_embed = outputs.last_hidden_state[:, 0, :]  # CLS token
        encoded = self.dense1(cls_embed)
        reconstructed = self.dense2(encoded)
        return reconstructed

# Define training function
def train_logbert_autoencoder():
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

    # Instantiate and compile
    model = LogBERTAutoencoder(bert_model)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss=tf.keras.losses.MeanSquaredError()
    )

    # Define checkpoint callback
    checkpoint_cb = tf.keras.callbacks.ModelCheckpoint(
        filepath = "/opt/airflow/logbert_autoencoder_best.keras",
        save_best_only=True,
        monitor="val_loss",
        mode="min",
        verbose=1
    )
    train_ids = tf.convert_to_tensor(train_ids)
    train_mask = tf.convert_to_tensor(train_mask)
    val_ids = tf.convert_to_tensor(val_ids)
    val_mask = tf.convert_to_tensor(val_mask)
    # Start MLflow run
    with mlflow.start_run():
        history = model.fit(
            x=(train_ids, train_mask),
            y=model((train_ids, train_mask)),
            validation_data=((val_ids, val_mask), model((val_ids, val_mask))),
            batch_size=BATCH_SIZE,
            epochs=EPOCHS,
            callbacks=[checkpoint_cb]
        )

        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("epochs", EPOCHS)
        mlflow.log_param("batch_size", BATCH_SIZE)
        mlflow.log_param("max_len", MAX_LEN)
        mlflow.log_param("learning_rate", LEARNING_RATE)
        mlflow.keras.log_model(model, "logbert_autoencoder_model")
        mlflow.log_metric("final_train_loss", history.history["loss"][-1])

    print("✅ Unsupervised training complete. Best model saved and tracked in MLflow.")

# DAG Start Time (rounded down to nearest 30 mins minus 5 mins)
now_utc = datetime.now(timezone.utc)
start_date_utc = now_utc.replace(minute=(now_utc.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)


def upload_trained_model_to_s3():
    s3 = boto3.client('s3')
    model_path = "/opt/airflow/logbert_autoencoder_best.keras"
    s3.upload_file(model_path, configuration.DEST_BUCKET, configuration.LOGBERT_AUTOENCODER_MODEL_KEY)
    print("✅ Trained model uploaded to S3.")

with DAG(
    dag_id='logbert_unsupervised_train_dag',
    start_date=start_date_utc,
    schedule_interval="@daily",
    catchup=False,
    tags=['logbert', 'mlflow', 'tensorflow']
) as dag:
    training_task = PythonOperator(
        task_id="train_logbert_autoencoder",
        python_callable=train_logbert_autoencoder
    )
    
    upload_trained_model_to_s3_task = PythonOperator(
        task_id="upload_trained_model_to_s3",
        python_callable=upload_trained_model_to_s3
    )
    training_task >> upload_trained_model_to_s3_task

    


