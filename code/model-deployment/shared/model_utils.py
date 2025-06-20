import os
import boto3
import tarfile
import tensorflow as tf
from transformers import BertTokenizer
from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence

# Config
S3_BUCKET = "your-s3-bucket"
S3_KEY = "models/logbert_autoencoder.tar.gz"
LOCAL_MODEL_PATH = "/tmp/logbert_autoencoder"
LOCAL_TAR = "/tmp/model.tar.gz"

# Setup
tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
persistence_file = "/tmp/drain3_persist.state"
template_miner = TemplateMiner(persistence_file=persistence_file)


def download_and_load_model():
    if not os.path.exists(LOCAL_MODEL_PATH):
        s3 = boto3.client("s3")
        s3.download_file(S3_BUCKET, S3_KEY, LOCAL_TAR)
        with tarfile.open(LOCAL_TAR, "r:gz") as tar:
            tar.extractall(path=LOCAL_MODEL_PATH)
    model = tf.keras.models.load_model(LOCAL_MODEL_PATH)
    return model


def extract_template_sequence(log_file):
    sequences = []
    with open(log_file) as f:
        for line in f:
            result = template_miner.add_log_message(line)
            sequences.append(result["template"])
    return sequences


def preprocess(sequences):
    text = " [SEP] ".join(sequences)
    return tokenizer(
        [text], max_length=128, truncation=True, padding="max_length", return_tensors="tf"
    )


def predict_from_file(model, log_file):
    seq = extract_template_sequence(log_file)
    tokens = preprocess(seq)
    result = model({"input_ids": tokens["input_ids"], "attention_mask": tokens["attention_mask"]})
    return result.numpy()[0].tolist()
