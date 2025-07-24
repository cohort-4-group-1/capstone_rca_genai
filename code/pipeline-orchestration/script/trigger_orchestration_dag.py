import boto3
import json
import subprocess
import requests
import os
import logging
import time
from datetime import datetime

# OpenTelemetry imports for unified observability
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Configure OpenTelemetry
resource = Resource.create({
    "service.name": "dag-orchestrator",
    "service.version": "1.0.0",
    "deployment.environment": "dev",
    "k8s.cluster.name": "airflow-cluster",
    "component": "pipeline-orchestration"
})

# Configure tracing
trace_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector:4318") + "/v1/traces"
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace_provider.add_span_processor(span_processor)
trace.set_tracer_provider(trace_provider)

# Configure metrics
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector:4318") + "/v1/metrics"
    ),
    export_interval_millis=5000,
)
metrics_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(metrics_provider)

# Auto-instrument libraries
RequestsInstrumentor().instrument()

# Get tracer and meter
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create metrics
sqs_messages_processed = meter.create_counter(
    "sqs_messages_processed_total",
    description="Total number of SQS messages processed",
    unit="1"
)

dag_triggers_total = meter.create_counter(
    "dag_triggers_total", 
    description="Total number of DAG triggers",
    unit="1"
)

api_pods_deleted_total = meter.create_counter(
    "api_pods_deleted_total",
    description="Total number of API pod deletion operations", 
    unit="1"
)

operation_duration = meter.create_histogram(
    "operation_duration_seconds",
    description="Duration of operations in seconds",
    unit="s"
)

# Configure logging with OTEL trace context
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [DAG_ORCHESTRATOR] - component=dag_orchestrator - trace_id=%(otelTraceID)s span_id=%(otelSpanID)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/dag_orchestrator.log')
    ]
)

logger = logging.getLogger(__name__)

# Custom log formatter to add trace context
class OTelLogFormatter(logging.Formatter):
    def format(self, record):
        span = trace.get_current_span()
        if span:
            span_context = span.get_span_context()
            record.otelTraceID = format(span_context.trace_id, "032x")
            record.otelSpanID = format(span_context.span_id, "016x")
        else:
            record.otelTraceID = ""
            record.otelSpanID = ""
        return super().format(record)

# Apply the formatter
for handler in logger.handlers:
    handler.setFormatter(OTelLogFormatter())

# Add structured logging helper with OTEL integration
def log_structured(level, message, **kwargs):
    """Helper function for structured logging with key-value pairs and span attributes"""
    # Add attributes to current span if available
    span = trace.get_current_span()
    if span and kwargs:
        for key, value in kwargs.items():
            span.set_attribute(f"custom.{key}", str(value))
    
    # Format log message with key-value pairs
    structured_msg = message
    if kwargs:
        kv_pairs = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        structured_msg = f"{message} - {kv_pairs}"
    
    getattr(logger, level)(structured_msg)

# --- Configuration ---
SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/141134438799/rca-queue"
AWS_REGION = "us-east-1"
DAG_ID = "dag_log_rca_orchestrator"
AIRFLOW_POD_LABEL = "component=webserver"  # or scheduler
NAMESPACE = "airflow"

# --- Get Airflow Pod name ---
def get_airflow_pod_name():
    with tracer.start_as_current_span("get_airflow_pod_name") as span:
        span.set_attribute("operation.name", "kubectl_get_pods")
        span.set_attribute("k8s.namespace", NAMESPACE)
        span.set_attribute("k8s.label_selector", AIRFLOW_POD_LABEL)
        
        logger.info("Starting to get Airflow pod name")
        logger.info(f"Looking for pods in namespace: {NAMESPACE} with label: {AIRFLOW_POD_LABEL}")
        
        cmd = [
            "kubectl", "get", "pods",
            "-n", NAMESPACE,
            "-l", AIRFLOW_POD_LABEL,
            "-o", "jsonpath={.items[0].metadata.name}"
        ]
        
        try:
            logger.info(f"Executing command: {' '.join(cmd)}")
            result = subprocess.check_output(cmd).decode("utf-8").strip()
            
            span.set_attribute("pod.name", result)
            span.set_status(trace.Status(trace.StatusCode.OK))
            
            logger.info(f"Successfully found Airflow pod: {result}")
            return result
        except subprocess.CalledProcessError as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, f"kubectl command failed: {e}"))
            span.set_attribute("error.message", str(e))
            logger.error(f"Failed to get Airflow pod name. Command: {' '.join(cmd)}, Error: {e}")
            raise


# --- Trigger Airflow DAG ---
def trigger_dag(pod_name, dag_id, conf=None):
    with tracer.start_as_current_span("trigger_dag") as span:
        span.set_attribute("operation.name", "airflow_dag_trigger")
        span.set_attribute("dag.id", dag_id)
        span.set_attribute("pod.name", pod_name)
        span.set_attribute("k8s.namespace", NAMESPACE)
        
        logger.info(f"Starting to trigger DAG: {dag_id} in pod: {pod_name}")
        
        try:
            base_cmd = ["kubectl", "exec", "-n", NAMESPACE, pod_name, "--", "airflow", "dags", "trigger", dag_id]
            if conf:
                conf_json = json.dumps(conf)
                base_cmd += ["--conf", conf_json]
                span.set_attribute("dag.config", conf_json)
                logger.info(f"DAG configuration provided: {conf_json}")
            
            logger.info(f"Executing command: {' '.join(base_cmd)}")
            start_time = time.time()
            
            subprocess.run(base_cmd, check=True)
            
            execution_time = time.time() - start_time
            span.set_attribute("operation.duration_seconds", execution_time)
            span.set_status(trace.Status(trace.StatusCode.OK))
            
            # Record metric
            dag_triggers_total.add(1, {"dag_id": dag_id, "status": "success"})
            operation_duration.record(execution_time, {"operation": "dag_trigger"})
            
            logger.info(f"Successfully triggered DAG {dag_id} in {execution_time:.2f} seconds")
            log_structured("info", "DAG triggered successfully", 
                          dag_id=dag_id, pod_name=pod_name, execution_time_seconds=execution_time)
            
        except subprocess.CalledProcessError as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, f"DAG trigger failed: {e}"))
            span.set_attribute("error.message", str(e))
            
            # Record failure metric
            dag_triggers_total.add(1, {"dag_id": dag_id, "status": "error"})
            
            logger.error(f"Error triggering DAG {dag_id} in pod {pod_name}. Command: {' '.join(base_cmd)}, Error: {e}")
            raise
        
# --- Delete API pods ---
def delete_api_pods():
    with tracer.start_as_current_span("delete_api_pods") as span:
        span.set_attribute("operation.name", "kubectl_delete_pods")
        span.set_attribute("k8s.namespace", "api")
        
        logger.info("Starting to delete all API pods")
        
        base_cmd = ["kubectl", "delete", "pods", "-n", 'api', "--all"]
        
        try:
            logger.info(f"Executing command: {' '.join(base_cmd)}")
            start_time = time.time()
            
            subprocess.run(base_cmd, check=True)
            
            execution_time = time.time() - start_time
            span.set_attribute("operation.duration_seconds", execution_time)
            span.set_status(trace.Status(trace.StatusCode.OK))
            
            # Record metrics
            api_pods_deleted_total.add(1, {"status": "success"})
            operation_duration.record(execution_time, {"operation": "delete_api_pods"})
            
            logger.info(f"Successfully deleted all API pods in {execution_time:.2f} seconds")
            log_structured("info", "API pods deleted successfully", 
                          namespace="api", execution_time_seconds=execution_time)
            
        except subprocess.CalledProcessError as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, f"Pod deletion failed: {e}"))
            span.set_attribute("error.message", str(e))
            
            # Record failure metric
            api_pods_deleted_total.add(1, {"status": "error"})
            
            logger.error(f"Error deleting API pods. Command: {' '.join(base_cmd)}, Error: {e}")
            raise


def trigger_dag_by_api(conf=None):
    logger.info("Starting to trigger DAG via Airflow REST API")
    
    AIRFLOW_API_BASE = "http://airflow-webserver.airflow.svc.cluster.local:8080/api/v1"
    url = f"{AIRFLOW_API_BASE}/dags/{DAG_ID}/dagRuns"
    payload = {
        "conf": conf or {},
    }
    
    logger.info(f"API endpoint: {url}")
    logger.info(f"Request payload: {json.dumps(payload, indent=2)}")
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, auth=("admin", "admin"))  # if using basic auth
        execution_time = time.time() - start_time
        
        logger.info(f"API request completed in {execution_time:.2f} seconds")
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response body: {response.text}")
        
        response.raise_for_status()
        logger.info("Successfully triggered DAG via API")
        log_structured("info", "DAG triggered via API successfully", 
                      dag_id=DAG_ID, api_endpoint=url, execution_time_seconds=execution_time)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error triggering DAG via API. URL: {url}, Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}, Body: {e.response.text}")
        raise

# --- Main logic ---
def main():
    with tracer.start_as_current_span("dag_orchestrator_main") as main_span:
        main_span.set_attribute("service.name", "dag-orchestrator")
        main_span.set_attribute("operation.name", "sqs_message_processing")
        
        logger.info("=" * 60)
        logger.info("DAG ORCHESTRATOR STARTED")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info(f"SQS Queue URL: {SQS_QUEUE_URL}")
        logger.info(f"AWS Region: {AWS_REGION}")
        logger.info(f"Target DAG ID: {DAG_ID}")
        logger.info(f"Airflow Namespace: {NAMESPACE}")
        logger.info("=" * 60)
        
        try:
            # Initialize SQS client
            with tracer.start_as_current_span("sqs_client_init") as span:
                logger.info("Initializing AWS SQS client")
                sqs = boto3.client("sqs", region_name=AWS_REGION)
                span.set_attribute("aws.region", AWS_REGION)
                logger.info("SQS client initialized successfully")
            
            # Poll for messages
            with tracer.start_as_current_span("sqs_receive_message") as span:
                span.set_attribute("sqs.queue_url", SQS_QUEUE_URL)
                
                logger.info(f"Starting to poll messages from queue: {SQS_QUEUE_URL}")
                response = sqs.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=10
                )
                logger.info("SQS receive_message call completed")

                messages = response.get("Messages", [])
                message_count = len(messages)
                
                span.set_attribute("sqs.message_count", message_count)
                main_span.set_attribute("total_messages_processed", message_count)
                
                logger.info(f"Found {message_count} message(s) in the queue")
                log_structured("info", "SQS polling completed", 
                              queue_url=SQS_QUEUE_URL, message_count=message_count)
           
            if not messages:
                logger.info("No messages found in the queue. Exiting gracefully.")
                main_span.set_attribute("exit_reason", "no_messages")
                return

            # Process each message
            for i, msg in enumerate(messages):
                with tracer.start_as_current_span(f"process_message_{i+1}") as msg_span:
                    logger.info(f"Processing message {i+1}/{len(messages)}")
                    
                    receipt_handle = msg["ReceiptHandle"]
                    body = json.loads(msg["Body"])
                    
                    msg_span.set_attribute("sqs.receipt_handle", receipt_handle[:20])
                    msg_span.set_attribute("sqs.message_body", json.dumps(body))
                    
                    logger.info(f"Message receipt handle: {receipt_handle[:20]}...")
                    logger.info(f"Message body: {json.dumps(body, indent=2)}")
                    
                    # Handle retrain_model messages
                    if 'retrain_model' in msg['Body']:
                        with tracer.start_as_current_span("handle_retrain_model") as span:
                            span.set_attribute("command.type", "retrain_model")
                            
                            logger.info("Detected 'retrain_model' command in message")
                            log_structured("info", "Processing retrain_model command", 
                                          command_type="retrain_model", message_id=receipt_handle[:20])
                            
                            try:
                                pod_name = get_airflow_pod_name()
                                logger.info(f"Retrieved Airflow pod name: {pod_name}")

                                trigger_dag(pod_name=pod_name, dag_id=DAG_ID)
                                logger.info(f"DAG {DAG_ID} triggered successfully")
                                
                                # Delete message from queue
                                with tracer.start_as_current_span("sqs_delete_message"):
                                    logger.info("Deleting processed message from SQS queue")
                                    sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
                                    logger.info("Message deleted successfully from queue")
                                
                                # Record success metric
                                sqs_messages_processed.add(1, {"command_type": "retrain_model", "status": "success"})
                                span.set_status(trace.Status(trace.StatusCode.OK))
                                
                            except Exception as e:
                                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                                sqs_messages_processed.add(1, {"command_type": "retrain_model", "status": "error"})
                                logger.error(f"Error processing retrain_model command: {e}")
                                logger.error("Message will remain in queue for retry")
                                
                    # Handle model_updated messages
                    elif 'model_updated' in msg['Body']: 
                        with tracer.start_as_current_span("handle_model_updated") as span:
                            span.set_attribute("command.type", "model_updated")
                            
                            logger.info("Detected 'model_updated' command in message")
                            log_structured("info", "Processing model_updated command", 
                                          command_type="model_updated", message_id=receipt_handle[:20])
                            
                            try:
                                delete_api_pods()
                                logger.info("API pods deleted successfully")
                                
                                # Delete message from queue
                                with tracer.start_as_current_span("sqs_delete_message"):
                                    logger.info("Deleting processed message from SQS queue")
                                    sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
                                    logger.info("Message deleted successfully from queue")
                                
                                # Record success metric
                                sqs_messages_processed.add(1, {"command_type": "model_updated", "status": "success"})
                                span.set_status(trace.Status(trace.StatusCode.OK))
                                
                            except Exception as e:
                                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                                sqs_messages_processed.add(1, {"command_type": "model_updated", "status": "error"})
                                logger.error(f"Error processing model_updated command: {e}")
                                logger.error("Message will remain in queue for retry")

                    else:
                        with tracer.start_as_current_span("handle_unknown_message") as span:
                            span.set_attribute("command.type", "unknown")
                            
                            logger.warning("No recognized command found in message")
                            logger.warning(f"Expected 'retrain_model' or 'model_updated', but message body was: {msg['Body']}")
                            
                            # Optionally delete unrecognized messages
                            logger.info("Deleting unrecognized message from queue")
                            sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
                            logger.info("Unrecognized message deleted from queue")
                            
                            # Record metric
                            sqs_messages_processed.add(1, {"command_type": "unknown", "status": "processed"})
                            span.set_status(trace.Status(trace.StatusCode.OK))

        except Exception as e:
            main_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Critical error in main execution: {e}")
            logger.error("DAG Orchestrator will exit with error")
            raise
        
        finally:
            logger.info("=" * 60)
            logger.info("DAG ORCHESTRATOR COMPLETED")
            logger.info(f"End timestamp: {datetime.now().isoformat()}")
            logger.info("=" * 60)

if __name__ == "__main__":
    main()
