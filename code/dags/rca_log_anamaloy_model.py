from transformers import BertTokenizer, TFBertModel
import tensorflow as tf
import pandas as pd
import mlflow
import mlflow.tensorflow
from sklearn.model_selection import train_test_split

# Configuration
MODEL_NAME = "bert-base-uncased"
EPOCHS = 5
BATCH_SIZE = 16
MAX_LEN = 128
LEARNING_RATE = 2e-5

# Load tokenizer and model
tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)
bert_model = TFBertModel.from_pretrained(MODEL_NAME)

# Load session sequences (no labels needed)
df = pd.read_csv("logbert_template_text_input.csv")
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

# Split into train/val sets
train_ids, val_ids, train_mask, val_mask = train_test_split(
    input_ids, attention_mask, test_size=0.2, random_state=42
)

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

# Instantiate and compile
model = LogBERTAutoencoder(bert_model)
model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
    loss=tf.keras.losses.MeanSquaredError()
)

# Define checkpoint callback
checkpoint_cb = tf.keras.callbacks.ModelCheckpoint(
    "logbert_autoencoder_best.h5",
    save_best_only=True,
    monitor="val_loss",
    mode="min",
    verbose=1
)

# Enable MLflow auto-logging
mlflow.tensorflow.autolog()

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
    mlflow.log_artifact("logbert_autoencoder_best.h5")

print("✅ Unsupervised training complete. Best model saved and tracked in MLflow.")
