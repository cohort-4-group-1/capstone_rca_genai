# orchestrator_dag.py
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime
import logging
import os

# Simple OpenTelemetry setup (optional - graceful fallback if not available)
try:
    from opentelemetry import trace, metrics
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource
    
    # Minimal OTEL setup
    resource = Resource.create({
        "service.name": "airflow-dag-orchestrator",
        "dag.id": "dag_log_rca_orchestrator"
    })
    
    # Configure tracing
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", 
                        "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/traces")
    ))
    trace.set_tracer_provider(trace_provider)
    
    # Configure metrics
    metrics_provider = MeterProvider(resource=resource, metric_readers=[
        PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT",
                             "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/metrics"),
            export_interval_millis=5000
        )
    ])
    metrics.set_meter_provider(metrics_provider)
    
    # Configure logging (NEW - this sends logs directly to OTEL)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(
        OTLPLogExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT",
                       "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/logs")
    ))
    
    meter = metrics.get_meter(__name__)
    dag_executions = meter.create_counter("dag_executions_total", description="DAG executions")
    OTEL_ENABLED = True
except ImportError:
    OTEL_ENABLED = False

# Hybrid OTEL + Console logging setup (logs appear in both OTEL and kubectl logs)
logger = logging.getLogger(__name__)

# Configure logger for both OTEL and console output
if OTEL_ENABLED:
    try:
        # Create OTEL handler for direct export
        otel_handler = LoggingHandler(logger_provider=logger_provider)
        
        # Add OTEL handler WITHOUT clearing existing handlers
        logger.addHandler(otel_handler)
        
        # Keep propagation enabled so logs also appear in kubectl logs
        logger.propagate = True
        
        # Set appropriate log level
        logger.setLevel(logging.INFO)
        
        logger.info("[DAG_ORCHESTRATOR] Hybrid OTEL + Console logging configured - logs sent to both collector and kubectl logs")
    except Exception as e:
        # Fallback to basic logging if OTEL fails
        logger.warning(f"[DAG_ORCHESTRATOR] OTEL logging failed, falling back to standard logging: {e}")
else:
    # Fallback for when OTEL is not available
    logger.info("[DAG_ORCHESTRATOR] OTEL not available - using standard Python logging")

def on_dag_success(context):
    """Log DAG success"""
    logger.info(f"[DAG_ORCHESTRATOR] DAG completed successfully - run_id={context.get('run_id')}")
    if OTEL_ENABLED:
        dag_executions.add(1, {"status": "success"})

def on_dag_failure(context):
    """Log DAG failure"""
    error = str(context.get('exception', 'Unknown'))
    logger.error(f"[DAG_ORCHESTRATOR] DAG execution failed - run_id={context.get('run_id')} error={error}")
    if OTEL_ENABLED:
        dag_executions.add(1, {"status": "failure"})

# =============================================================================
# DAG DEFINITION - Clean and Simple
# =============================================================================

with DAG(
    dag_id="dag_log_rca_orchestrator",
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    is_paused_upon_creation=False,
    tags=["orchestrator", "otel-instrumented"],
    on_success_callback=on_dag_success,
    on_failure_callback=on_dag_failure
) as dag:

    # Log DAG start
    logger.info("[DAG_ORCHESTRATOR] RCA Pipeline Orchestrator initialized")

    # =============================================================================
    # STAGE 1: DATA PREPARATION (Sequential)
    # =============================================================================
    
    trigger_dag_log_parse = TriggerDagRunOperator(
        task_id="trigger_log_parse",
        trigger_dag_id="dag_log_parse",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("trigger_log_eda initialized")
    
    trigger_dag_log_eda = TriggerDagRunOperator(
        task_id="trigger_log_eda",
        trigger_dag_id="dag_log_eda",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("trigger_log_template initialized")

    trigger_dag_log_template = TriggerDagRunOperator(
        task_id="trigger_log_template",
        trigger_dag_id="dag_log_template",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("trigger_log_sequence initialized")

    trigger_dag_log_sequence = TriggerDagRunOperator(
        task_id="trigger_log_sequence",
        trigger_dag_id="dag_log_sequence",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    # =============================================================================
    # STAGE 2: MODEL TRAINING (Parallel)
    # =============================================================================

    logger.info("trigger_train_rca_model_clustering_kmeans initialized")

    trigger_dag_log_clustering_kmeans = TriggerDagRunOperator(
        task_id="trigger_train_rca_model_clustering_kmeans",
        trigger_dag_id="dag_log_clustering_kmeans",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("trigger_train_autoencoder_kmeans_pipeline initialized")
    trigger_dag_log_deep_network_clustering_kmeans = TriggerDagRunOperator(
        task_id="trigger_train_autoencoder_kmeans_pipeline",
        trigger_dag_id="dag_log_deep_network_clustering_kmeans",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("trigger_log_clustering_iforest initialized")
    
    trigger_dag_log_clustering_iforest = TriggerDagRunOperator(
        task_id="trigger_log_clustering_iforest",
        trigger_dag_id="dag_log_clustering_iforest",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )
    
    # =============================================================================
    # STAGE 3: NOTIFICATION
    # =============================================================================
    
    logger.info("trigger_send_sqs_message_dag initialized")

    trigger_dag_notify_model_updates = TriggerDagRunOperator(
        task_id="trigger_send_sqs_message",
        trigger_dag_id="send_sqs_message_dag",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    # =============================================================================
    # PIPELINE DEPENDENCIES
    # =============================================================================
    
    # Stage 1: Data preparation (sequential)
    trigger_dag_log_parse >> trigger_dag_log_eda >> trigger_dag_log_template >> trigger_dag_log_sequence >> [
        # Stage 2: Model training (parallel)
        trigger_dag_log_clustering_kmeans,
        trigger_dag_log_deep_network_clustering_kmeans,
        trigger_dag_log_clustering_iforest
    ] >> trigger_dag_notify_model_updates  # Stage 3: Notification

    # Log pipeline structure
    logger.info("[DAG_ORCHESTRATOR] Pipeline structure defined - 3 stages: data_preparation -> model_training -> notification")

