# fastapi_app/main.py

from contextlib import asynccontextmanager
import os
import io
import boto3
import joblib
import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException
from drain3.template_miner import TemplateMiner
from drain3.file_persistence import FilePersistence
import numpy as np
from typing import List
import configuration
import requests  # Required for invoking LLM-based context analysis

app = FastAPI()

# --- Globals ---
S3_BUCKET = configuration.DEST_BUCKET
#S3_MODEL_KEY = configuration.CLUSTERING_MODEL_OUTPUT  # Joblib: vectorizer, encoder, kmeans
S3_TEMPLATE_KEY = configuration.TEMPLATE_DRAIN_FILE_KEY  # Drain3 template state file
LOCAL_TEMPLATE_PATH = configuration.TEMPLATE_DRAIN_FILE
MODEL = None
TEMPLATE_MINER = None


# # --- Load from S3 on startup ---
@app.on_event("startup")
def load_resources():
    global MODEL, TEMPLATE_MINER
    
    # Load model from S3
    s3 = boto3.client("s3")
    print(f"Loading model from S3...{configuration.ISOLATION_FOREST_MODEL_OUTPUT}")
    model_obj = s3.get_object(Bucket=S3_BUCKET, Key=f"{configuration.ISOLATION_FOREST_MODEL_OUTPUT}.pkl")
    vectorizer, iforest =  joblib.load(io.BytesIO(model_obj['Body'].read()))
    
    MODEL = (vectorizer,  iforest)
    print("Encoder and pipeline loaded successfully")

    # Load Drain3 state file from S3
    print("Loading Drain3 template from S3...")
    s3.download_file(S3_BUCKET, S3_TEMPLATE_KEY, LOCAL_TEMPLATE_PATH)
    persistence = FilePersistence(LOCAL_TEMPLATE_PATH)
    TEMPLATE_MINER = TemplateMiner(persistence, config=None)

    print("Model and template miner loaded.")


# --- Utility: Parse log lines into templates ---
def parse_templates(lines: List[str]) -> List[str]:
     return [
        TEMPLATE_MINER.add_log_message(line).get("template_mined", "")
        for line in lines
    ]

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
        raise HTTPException(status_code=500, detail="Clustering model not loaded")

    vectorizer, iforest = MODEL

    try:
        # Read log lines
        lines = [line.decode("utf-8").strip() for line in file.file.readlines() if line.strip()]

        # Create sequences
        sequences = group_sequences(lines, window_size=10)
        if not sequences:
            raise HTTPException(status_code=400, detail="Not enough lines to form sequences")

        # Vectorize
        X = vectorizer.transform(sequences)

        preds = iforest.predict(X)          # -1 = anomaly
        scores = iforest.decision_function(X)  # higher = more anomalous

        results = []
        for i, seq in enumerate(sequences):
            anomaly_score = float(scores[i])
            if (bool(preds[i] == -1) == False): 
                result = {
                    "window_start_line": lines[i],
                    "anomaly_score": anomaly_score,
                    "is_anomaly": bool(preds[i] == -1)
                }
                results.append(result)

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log analysis failed: {str(e)}")
