import os, io, traceback, logging
import boto3, joblib, numpy as np, pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException
from drain3.template_miner import TemplateMiner
from drain3.file_persistence import FilePersistence
from typing import List
import configuration

import requests  # Required for invoking LLM-based context analysis
from rca_contextual_analysis import contextual_analysis_batch 
import traceback


from rca_contextual_analysis import contextual_analysis
from otel import logger, tracer, meter, OTEL_ENABLED
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import prometheus_client

# OTEL Logging
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor


# FastAPI app

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)

# Globals
S3_BUCKET = configuration.DEST_BUCKET
S3_TEMPLATE_KEY = configuration.TEMPLATE_DRAIN_FILE_KEY
LOCAL_TEMPLATE_PATH = configuration.TEMPLATE_DRAIN_FILE
MODEL = None
TEMPLATE_MINER = None

# --- OTEL Metrics ---
if OTEL_ENABLED and meter:
    api_requests_total = meter.create_counter(
        name="api_requests_total",
        description="Total number of API requests received"
    )
    api_request_duration = meter.create_histogram(
        name="api_request_duration_seconds",
        description="API request duration in seconds"
    )
    api_errors_total = meter.create_counter(
        name="api_errors_total",
        description="Total number of API errors"
    )
else:
    api_requests_total = None
    api_request_duration = None
    api_errors_total = None

# --- Startup event: Load model and template miner ---
@app.on_event("startup")
def load_resources():
    global MODEL, TEMPLATE_MINER
    logger.info("Starting model and template miner initialization...")

    try:
        s3 = boto3.client("s3")
        logger.info(f"Loading model from S3: {configuration.ISOLATION_FOREST_MODEL_OUTPUT}")
        model_obj = s3.get_object(Bucket=S3_BUCKET, Key=f"{configuration.ISOLATION_FOREST_MODEL_OUTPUT}.pkl")
        vectorizer, iforest = joblib.load(io.BytesIO(model_obj['Body'].read()))
        MODEL = (vectorizer, iforest)
        logger.info("Model loaded successfully")

        logger.info("Downloading Drain3 template file from S3")
        s3.download_file(S3_BUCKET, S3_TEMPLATE_KEY, LOCAL_TEMPLATE_PATH)
        persistence = FilePersistence(LOCAL_TEMPLATE_PATH)
        TEMPLATE_MINER = TemplateMiner(persistence, config=None)
        logger.info("Template miner initialized successfully")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

# --- Utility: Parse log lines into templates ---
def parse_templates(lines: List[str]) -> List[str]:
    return [TEMPLATE_MINER.add_log_message(line).get("template_mined", "") for line in lines]

# --- Utility: Group log templates into sequences ---
def group_sequences(templates: List[str], window_size=10) -> List[str]:
    sequences = []
    for i in range(len(templates) - window_size + 1):
        sequences.append(" ".join(templates[i:i + window_size]))
    return sequences


# --- Utility: Call LLM-based contextual analyzer ---
def analyze_context_with_llm(anomaly_line: str, context_lines: List[str]) -> dict:
    log_template = " ".join(parse_templates(context_lines))
    log_sequence = group_sequences(log_template, window_size=10)
    log_window_text = "\n".join(context_lines)
    logger.info(f"Analyzing context for anomaly line: {anomaly_line}")
    return contextual_analysis(anomaly_line, log_sequence, log_window_text)


# --- API: Upload log and get anomaly prediction ---
@app.post("/analyze-log")
def analyze_log(file: UploadFile = File(...)):
    import time
    start_time = time.time()
    if api_requests_total:
        api_requests_total.add(1, {"endpoint": "/analyze-log"})
    if not MODEL:
        logger.error("Model is not loaded")
        if api_errors_total:
            api_errors_total.add(1, {"endpoint": "/analyze-log", "error": "model_not_loaded"})
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    vectorizer, iforest = MODEL
    
    try:
        # Step 1: Read raw log lines
        lines = [line.decode("utf-8").strip() for line in file.file.readlines() if line.strip()]

        # Step 2: Parse log templates from raw lines
        templates = parse_templates(lines)

        # Step 3: Group templates into sequences
        sequences = group_sequences(templates, window_size=5)
        if not sequences:
            raise HTTPException(status_code=400, detail="Not enough lines to form sequences")

        # Step 4: Vectorize sequences and predict anomalies
        X = vectorizer.transform(sequences)
        preds = iforest.predict(X)              # -1 = anomaly
        scores = iforest.decision_function(X)   # Higher = more anomalous

        anomalies = []
        first_anomaly_found = False
        results = []
        for i, seq in enumerate(sequences):
            anomaly_score = float(scores[i])
            is_anomaly = bool(preds[i] == 1)

            result = {
                "window_start_line": lines[i],
                "anomaly_score": anomaly_score,
                "pred" : preds[i],    
                "is_anomaly": is_anomaly
            }
            window_start = max(i, 0)
            window_end = min(i + 20, len(lines))
            context_window = lines[window_start:window_end]

            if is_anomaly and not first_anomaly_found:
                rca_result = analyze_context_with_llm(
                    anomaly_line=lines[i],
                    context_lines=context_window
                )
                result["rca"] = rca_result
                first_anomaly_found = True
            
            results.append(result)    
        
        return results


    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Log analysis failed: {str(e)}\n{tb}")


# --- API: Upload log and get anomaly prediction ---
@app.post("/analyze-log-anamaly")
def analyze_log_anamaly(file: UploadFile = File(...)):
    import time
    start_time = time.time()
    if not MODEL:
        raise HTTPException(status_code=500, detail="Isolation Forest model not loaded")

    vectorizer, iforest = MODEL

    try:
        # --- Custom OTEL trace span for log analysis ---
        with tracer.start_as_current_span("analyze_log_request", attributes={"endpoint": "/analyze-log"}):
            # Step 1: Read raw log lines
            lines = [line.decode("utf-8").strip() for line in file.file.readlines() if line.strip()]
            logger.info(f"Received log file with {len(lines)} lines")

            #Step 2: Parse log templates from raw lines
            logger.info("Parsing log templates")
            templates = parse_templates(lines)

            # Step 3: Group templates into sequences
            logger.info("Grouping log templates into sequences")
            sequences = group_sequences(templates, window_size=10)
            if not sequences:
                logger.warning("Not enough log lines to form sequences")
                raise HTTPException(status_code=400, detail="Not enough lines to form sequences")

            # Step 4: Predict anomalies using Isolation Forest
            logger.info("Running Isolation Forest anomaly detection")
            vectorizer, iforest = MODEL
            X = vectorizer.transform(sequences)
            preds = iforest.predict(X) # -1 = anomaly
            scores = iforest.decision_function(X) # Higher = more anomalous

            # Step 5: Prepare results
            logger.info("Preparing results")
            results = []
            first_anomaly_found = False

            for i, seq in enumerate(sequences):
                # Ensure is_anomaly is a native Python bool, not numpy.bool_
                is_anomaly = bool(preds[i] == -1)
                anomaly_score = float(scores[i])
                result = {
                    "window_start_line": lines[i],
                    "anomaly_score": anomaly_score,
                    "is_anomaly": is_anomaly
                }

                if is_anomaly and not first_anomaly_found:
                    logger.info(f"Anomaly detected at line {i} with score {anomaly_score:.4f}")
                    window_start = max(i, 0)
                    window_end = min(i + 20, len(lines))
                    context_window = lines[window_start:window_end]

                    try:
                        rca_result = analyze_context_with_llm(
                            anomaly_line=lines[i],
                            context_lines=context_window
                        )
                        logger.info(f"RCA analysis result for anomaly at line {i}: {rca_result}")
                        result["rca"] = rca_result
                        first_anomaly_found = True

                    except Exception as rca_err:
                        logger.warning(f"Failed RCA analysis for anomaly at line {i}: {rca_err}")

                results.append(result)

            logger.info("Log analysis completed")
            duration = time.time() - start_time
            if api_request_duration:
                api_request_duration.record(duration, {"endpoint": "/analyze-log", "status": "success"})
            return results
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Log analysis failed: {e}")
        if api_errors_total:
            api_errors_total.add(1, {"endpoint": "/analyze-log", "error": type(e).__name__})
        if api_request_duration:
            api_request_duration.record(0.0, {"endpoint": "/analyze-log", "status": "error"})
        raise HTTPException(status_code=500, detail=f"Log analysis failed: {str(e)}\n{tb}")


# --- API: Prometheus metrics endpoint ---
@app.get("/metrics")
def metrics():
    # Expose all default and custom Prometheus metrics
    """Endpoint that returns Prometheus metrics in text format for scraping."""
    logger.info("Metrics endpoint accessed")
    return PlainTextResponse(generate_latest(prometheus_client.REGISTRY), media_type=CONTENT_TYPE_LATEST)