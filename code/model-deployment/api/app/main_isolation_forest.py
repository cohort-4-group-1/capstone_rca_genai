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
from rca_contextual_analysis import contextual_analysis 
import traceback

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
    log_sequence = " ".join(parse_templates(context_lines))  # generate log sequence from templates
    log_window_text = "\n".join(context_lines)
    return contextual_analysis(anomaly_line, log_sequence, log_window_text)

# --- API: Upload log and get anomaly prediction ---
@app.post("/analyze-log")
def analyze_log(file: UploadFile = File(...)):
    if not MODEL:
        raise HTTPException(status_code=500, detail="Isolation Forest model not loaded")

    vectorizer, iforest = MODEL

    try:
        # Step 1: Read raw log lines
        lines = [line.decode("utf-8").strip() for line in file.file.readlines() if line.strip()]

        # Step 2: Parse log templates from raw lines
        templates = parse_templates(lines)

        # Step 3: Group templates into sequences
        sequences = group_sequences(templates, window_size=10)
        if not sequences:
            raise HTTPException(status_code=400, detail="Not enough lines to form sequences")

        # Step 4: Vectorize sequences and predict anomalies
        X = vectorizer.transform(sequences)
        preds = iforest.predict(X)              # -1 = anomaly
        scores = iforest.decision_function(X)   # Higher = more anomalous

        # Step 5: Analyze and return results
        results = []
        for i, seq in enumerate(sequences):
            anomaly_score = float(scores[i])
            is_anomaly = bool(preds[i] == -1)

            result = {
                "window_start_line": lines[i],
                "anomaly_score": anomaly_score,
                "is_anomaly": is_anomaly
            }

            if is_anomaly:
                window_start = max(i, 0)
                window_end = min(i + 20, len(lines))
                context_window = lines[window_start:window_end]

                rca_result = analyze_context_with_llm(
                    anomaly_line=lines[i],
                    context_lines=context_window
                )
                result["rca"] = rca_result

            results.append(result)

        return results

    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Log analysis failed: {str(e)}\n{tb}")
