# fastapi_app/main.py

import os
import io
import boto3
import joblib
import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException
from drain3.template_miner_config import TemplateMinerConfig
from drain3.template_miner import TemplateMiner
from drain3.file_persistence import FilePersistence
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from tensorflow.keras.models import load_model
import numpy as np
from typing import List
import tempfile
import configuration
import json
import requests  # Required for invoking LLM-based context analysis

app = FastAPI()

# --- Globals ---
S3_BUCKET = configuration.DEST_BUCKET
S3_MODEL_KEY = configuration.CLUSTERING_MODEL_OUTPUT  # Joblib: vectorizer, encoder, kmeans
S3_TEMPLATE_KEY = configuration.TEMPLATE_DRAIN_FILE  # Drain3 template state file
LOCAL_TEMPLATE_PATH = "/tmp/drain3_state.bin"
MODEL = None
TEMPLATE_MINER = None

# --- Load from S3 on startup ---
@app.on_event("startup")
def load_resources():
    global MODEL, TEMPLATE_MINER
    
    # Load model from S3
    s3 = boto3.client("s3")
    print("Loading model from S3...")
    model_obj = s3.get_object(Bucket=S3_BUCKET, Key=S3_MODEL_KEY)
    MODEL = joblib.load(io.BytesIO(model_obj['Body'].read()))

    # Load Drain3 state file from S3
    print("Loading Drain3 template from S3...")
    s3.download_file(S3_BUCKET, S3_TEMPLATE_KEY, LOCAL_TEMPLATE_PATH)
    config = TemplateMinerConfig()
    config.load_default()
    persistence = FilePersistence(LOCAL_TEMPLATE_PATH)
    TEMPLATE_MINER = TemplateMiner(persistence, config)

    print("Model and template miner loaded.")


# --- Utility: Parse log lines into templates ---
def parse_templates(lines: List[str]) -> List[str]:
    return [TEMPLATE_MINER.add_log_message(line).template_mined or "" for line in lines]

# --- Utility: Group templates into sequences ---
def group_sequences(templates: List[str], window_size=10) -> List[str]:
    sequences = []
    for i in range(len(templates) - window_size + 1):
        seq = " ".join(templates[i:i+window_size])
        sequences.append(seq)
    return sequences

# --- Utility: Call LLM-based contextual analyzer ---
def analyze_context_with_llm(anomaly_line: str, context_lines: List[str]) -> dict:
    try:
        response = requests.post(
            url="http://lambda-llm-context:8080/analyze",  # Replace with actual service URL or proxy
            json={
                "anomaly_line": anomaly_line,
                "log_window": context_lines
            },
            timeout=10
        )
        return response.json()
    except Exception as e:
        return {"error": str(e), "message": "LLM analysis failed"}

# --- API: Upload log and get anomaly prediction ---
@app.post("/analyze-log")
def analyze_log(file: UploadFile = File(...)):
    if not MODEL:
        raise HTTPException(status_code=500, detail="Model not loaded")

    vectorizer, encoder, kmeans = MODEL

    # Read uploaded log file
    lines = [line.decode("utf-8").strip() for line in file.file.readlines() if line.strip()]

    # Step 1: Parse templates
    templates = parse_templates(lines)

    # Step 2: Group into sequences
    sequences = group_sequences(templates, window_size=10)
    if not sequences:
        raise HTTPException(status_code=400, detail="Not enough lines to create sequences")

    # Step 3: Vectorize, encode, cluster
    X = vectorizer.transform(sequences).toarray()
    latent = encoder.predict(X)
    clusters = kmeans.predict(latent)

    # Step 4: Calculate reconstruction error as anomaly score
    recon = encoder.model.predict(X)  # Assumes decoder is part of encoder.model
    anomaly_scores = np.mean((X - recon)**2, axis=1)

    # Step 5: Map sequence result back to lines and enrich with LLM
    results = []
    for i, seq in enumerate(sequences):
        context_lines = lines[i:i+10]  # context window
        #llm_analysis = analyze_context_with_llm(anomaly_line=lines[i], context_lines=context_lines)
        result = {
            "log_window_start": lines[i],
            "sequence": sequences[i],
            "cluster": int(clusters[i]),
            "anomaly_score": float(anomaly_scores[i])#,
            #"context_analysis": llm_analysis
        }
        results.append(result)

    return results
