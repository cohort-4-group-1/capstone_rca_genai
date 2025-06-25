from transformers import BertTokenizer, TFBertModel
import tensorflow as tf
import pandas as pd
import mlflow
import mlflow.tensorflow
from sklearn.model_selection import train_test_split
import os
import configuration
from tensorflow.keras import mixed_precision
import boto3
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import shutil
import time

DATA_PATH = f"s3://{configuration.DEST_BUCKET}/{configuration.LOG_SEQUENCE__FILE_KEY}"
S3_BUCKET = configuration.DEST_BUCKET
S3_KEY = configuration.MODEL_OUTPUT


# Constants
MODEL_NAME = "bert-base-uncased"
EPOCHS = 1
BATCH_SIZE = 16
MAX_LEN = 64
LEARNING_RATE = 2e-5
DATA_PATH = f"s3://{configuration.DEST_BUCKET}/{configuration.LOG_SEQUENCE__FILE_KEY}"
CHECKPOINT_DIR = "rca_logbert_model"

def train_and_upload_to_s3_rca_model():
    print ("set XLA and floating point")
    tf.config.optimizer.set_jit(True)  # Enable XLA
    tf.keras.mixed_precision.set_global_policy("float32")


    print ("set mlflow tracking")
    mlflow.set_tracking_uri("http://mlflow.mlflow.svc.cluster.local:5000")
    mlflow.tensorflow.autolog(log_models=True)

    print ("Download token and model")
    tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)
    bert_model = TFBertModel.from_pretrained(MODEL_NAME)

    print ("Read dataset")
    df = pd.read_csv(DATA_PATH)
    sequences = df["sequence"].tolist()

    tokens = tokenizer(
        sequences,
        max_length=MAX_LEN,
        padding="max_length",
        truncation=True,
        return_tensors="tf"
    )

    input_ids = tokens["input_ids"].numpy()
    attention_mask = tokens["attention_mask"].numpy()

    print ("split the dataset for training and test")
    # Split
    train_ids, val_ids, train_mask, val_mask = train_test_split(
        input_ids, attention_mask, test_size=0.2, random_state=42
    )

    # Define model
    print ("Define model")
    input_ids_in = tf.keras.Input(shape=(MAX_LEN,), dtype=tf.int32, name="input_ids")
    attention_mask_in = tf.keras.Input(shape=(MAX_LEN,), dtype=tf.int32, name="attention_mask")
    bert_output = bert_model(input_ids=input_ids_in, attention_mask=attention_mask_in)
    cls_token = bert_output.last_hidden_state[:, 0, :]
    encoded = tf.keras.layers.Dense(768, activation="relu")(cls_token)
    reconstructed = tf.keras.layers.Dense(768)(encoded)  
    model = tf.keras.Model(inputs=[input_ids_in, attention_mask_in], outputs=reconstructed)
    
    print ("compile model")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss=tf.keras.losses.MeanSquaredError()
    )

    # Build datasets
    print ("Build datasets")
    model.build(input_shape={"input_ids": (None, MAX_LEN), "attention_mask": (None, MAX_LEN)})

    def create_dataset(input_ids, attention_mask):
        input_ids_tensor = tf.convert_to_tensor(input_ids, dtype=tf.int32)
        attention_mask_tensor = tf.convert_to_tensor(attention_mask, dtype=tf.int32)

        ds = tf.data.Dataset.from_tensor_slices({
            "input_ids": input_ids_tensor,
            "attention_mask": attention_mask_tensor
        })

        def add_dummy_target(inputs):
            return inputs, tf.zeros((768,), dtype=tf.float32)  # each sample's target

        ds = ds.map(add_dummy_target, num_parallel_calls=tf.data.AUTOTUNE)
        return ds.shuffle(1000).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)



    train_ds = create_dataset(train_ids, train_mask)
    val_ds = create_dataset(val_ids, val_mask)
    print ("checkpoint_cb set")
    checkpoint_cb = tf.keras.callbacks.ModelCheckpoint(
        filepath=CHECKPOINT_DIR,
        save_best_only=True,
        monitor="val_loss",
        mode="min",
        verbose=0,
        save_format="tf"
    )
    early_stop = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=2, restore_best_weights=True)

    print ("strat training for  model")
    with mlflow.start_run():  
        start = time.time()         
        model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=EPOCHS,
            callbacks=[checkpoint_cb,early_stop],
             verbose=2
        )
        print("⏱ Training time:", time.time() - start, "seconds")
        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("epochs", EPOCHS)
        mlflow.log_param("batch_size", BATCH_SIZE)
        mlflow.log_param("max_len", MAX_LEN)
        mlflow.log_param("learning_rate", LEARNING_RATE)
        mlflow.tensorflow.log_model(tf_saved_model_dir=CHECKPOINT_DIR, artifact_path="logbert_model")

    print("✅ Optimized training complete. Model saved and tracked.")


    # Save full model for Hugging Face
    print("Model will be saved")

    # Upload to Hugging Face
    print("Model will be uploaded")       
    model.save(CHECKPOINT_DIR)
    print(f'model is saved in {CHECKPOINT_DIR}')        


    # AWS S3 upload
    print(f'started to upoad {CHECKPOINT_DIR} in {S3_BUCKET} with file key {S3_KEY}')
    s3 = boto3.client("s3")
    for root, dirs, files in os.walk(CHECKPOINT_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            rel_path = os.path.relpath(local_path, CHECKPOINT_DIR)
            s3.upload_file(local_path, S3_BUCKET, f"{S3_KEY}/{rel_path}")
            print(f"✅ Uploaded {local_path} to s3://{S3_BUCKET}/{S3_KEY}/{rel_path}")

    # Cleanup
    shutil.rmtree(CHECKPOINT_DIR)
    print(f"🧹 Deleted local checkpoint dir: {CHECKPOINT_DIR}")
    hf_cache = os.path.expanduser("~/.cache/huggingface")
    if os.path.exists(hf_cache):
        shutil.rmtree(hf_cache)        
        print("🧹 Deleted huggingface cache directory")

    if os.path.exists(os.path.expanduser("~/.cache")):
        shutil.rmtree(os.path.expanduser("~/.cache"))
        print("🧹 Deleted cache directory ~/.cache")

    print("✅ Training complete and checkpoint saved to S3.")
    

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
        task_id="train_and_upload_to_s3_rca_model",
        python_callable=train_and_upload_to_s3_rca_model
    )
