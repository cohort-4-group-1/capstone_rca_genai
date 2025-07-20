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
    
    # Simple OTEL setup
    resource = Resource.create({
        "service.name": "airflow-worker",
        "dag.id": "dag_log_rca_orchestrator"
    })
    
    # Configure tracing
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", 
                        "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/traces")
    ))
    trace.set_tracer_provider(trace_provider)
    
    # Configure metrics with correct endpoint from environment
    metrics_endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", 
                                os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", 
                                        "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/metrics")
    
    metrics_provider = MeterProvider(resource=resource, metric_readers=[
        PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=metrics_endpoint),
            export_interval_millis=10000  # Export every 10 seconds
        )
    ])
    metrics.set_meter_provider(metrics_provider)
    
    # Configure logging
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(
        OTLPLogExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT",
                             "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/logs",
            timeout=30
        )
    ))
    
    # Get tracer and meter
    tracer = trace.get_tracer(__name__)
    meter = metrics.get_meter(__name__)
    
    # Simple metrics with correct naming
    dag_counter = meter.create_counter(
        name="dag_runs_total", 
        description="Total DAG runs",
        unit="1"
    )
    task_duration = meter.create_histogram(
        name="task_duration_seconds", 
        description="Task execution duration in seconds",
        unit="s"
    )
    
    OTEL_ENABLED = True
except ImportError:
    OTEL_ENABLED = False
    tracer = None
    meter = None

# Simple logging setup
logger = logging.getLogger(__name__)

# Configure logger with OTEL handler if available
if OTEL_ENABLED:
    try:
        otel_handler = LoggingHandler(logger_provider=logger_provider)
        logger.handlers.clear()
        logger.addHandler(otel_handler)
        logger.propagate = False
        logger.setLevel(logging.INFO)
        
        logger.info("[DAG_ORCHESTRATOR] OTEL logging configured")
        print(f"[DEBUG] OTEL endpoint: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://opentelemetry-collector.monitoring.svc.cluster.local:4318')}")
        print(f"[DEBUG] OTEL metrics endpoint: {os.getenv('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT', 'Not Set')}")
        print(f"[DEBUG] DAG metrics created: dag_runs_total, task_duration_seconds")
    except Exception as e:
        print(f"[ERROR] OTEL logging setup failed: {e}")
else:
    logger.info("[DAG_ORCHESTRATOR] Standard logging")

def on_dag_success(context):
    """Simple DAG success logging with trace ID"""
    run_id = context.get('run_id')
    
    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span("dag_success") as span:
            trace_id = format(span.get_span_context().trace_id, '032x')
            logger.info(f"[DAG_ORCHESTRATOR] Pipeline completed successfully - run_id={run_id} trace_id={trace_id}")
            # Record metric
            dag_counter.add(1, {"status": "success", "dag_id": "dag_log_rca_orchestrator"})
            print(f"[DEBUG] Recorded dag_runs_total metric: status=success")
    else:
        logger.info(f"[DAG_ORCHESTRATOR] Pipeline completed successfully - run_id={run_id}")

def on_dag_failure(context):
    """Simple DAG failure logging with trace ID"""
    run_id = context.get('run_id')
    error = str(context.get('exception', 'Unknown'))
    
    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span("dag_failure") as span:
            trace_id = format(span.get_span_context().trace_id, '032x')
            logger.error(f"[DAG_ORCHESTRATOR] Pipeline failed - run_id={run_id} trace_id={trace_id} error={error}")
            # Record metric
            dag_counter.add(1, {"status": "failure", "dag_id": "dag_log_rca_orchestrator"})
            print(f"[DEBUG] Recorded dag_runs_total metric: status=failure")
    else:
        logger.error(f"[DAG_ORCHESTRATOR] Pipeline failed - run_id={run_id} error={error}")

def on_task_success(context):
    """Simple task success logging with timing"""
    task_instance = context.get('task_instance')
    task_id = task_instance.task_id
    
    # Calculate duration
    duration = 0
    if task_instance.start_date and task_instance.end_date:
        duration = (task_instance.end_date - task_instance.start_date).total_seconds()
    
    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span("task_success") as span:
            trace_id = format(span.get_span_context().trace_id, '032x')
            logger.info(f"[DAG_ORCHESTRATOR] Task completed: {task_id} - {duration:.1f}s - trace_id={trace_id}")
            # Record metric
            task_duration.record(duration, {"task": task_id, "status": "success", "dag_id": "dag_log_rca_orchestrator"})
            print(f"[DEBUG] Recorded task_duration_seconds metric: {task_id}={duration:.1f}s")
    else:
        logger.info(f"[DAG_ORCHESTRATOR] Task completed: {task_id} - {duration:.1f}s")

# =============================================================================
# DAG DEFINITION - Clean and Simple
# =============================================================================

with DAG(
    dag_id="dag_log_rca_orchestrator",
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    is_paused_upon_creation=False,
    tags=["orchestrator", "otel-instrumented", "observability"],
    on_success_callback=on_dag_success,
    on_failure_callback=on_dag_failure
) as dag:

    # Initialize DAG with tracing
    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span("dag_initialization") as span:
            trace_id = format(span.get_span_context().trace_id, '032x')
            logger.info(f"[DAG_ORCHESTRATOR] RCA Pipeline Orchestrator started - trace_id={trace_id}")
    else:
        logger.info("[DAG_ORCHESTRATOR] RCA Pipeline Orchestrator started")

    # =============================================================================
    # STAGE 1: DATA PREPARATION (Sequential)
    # =============================================================================
    
    logger.info("[DAG_ORCHESTRATOR] Defining Stage 1: Data Preparation (Sequential)")
    
    trigger_dag_log_parse = TriggerDagRunOperator(
        task_id="trigger_log_parse",
        trigger_dag_id="dag_log_parse",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed'],
        on_success_callback=on_task_success
    )

    logger.info("[DAG_ORCHESTRATOR] trigger_log_eda initialized")
    
    trigger_dag_log_eda = TriggerDagRunOperator(
        task_id="trigger_log_eda",
        trigger_dag_id="dag_log_eda",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("[DAG_ORCHESTRATOR] trigger_log_template initialized")

    trigger_dag_log_template = TriggerDagRunOperator(
        task_id="trigger_log_template",
        trigger_dag_id="dag_log_template",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("[DAG_ORCHESTRATOR] trigger_log_sequence initialized")

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

    logger.info("[DAG_ORCHESTRATOR] Defining Stage 2: Model Training (Parallel)")

    logger.info("[DAG_ORCHESTRATOR] trigger_train_rca_model_clustering_kmeans initialized")

    trigger_dag_log_clustering_kmeans = TriggerDagRunOperator(
        task_id="trigger_train_rca_model_clustering_kmeans",
        trigger_dag_id="dag_log_clustering_kmeans",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("[DAG_ORCHESTRATOR] trigger_train_autoencoder_kmeans_pipeline initialized")
    trigger_dag_log_deep_network_clustering_kmeans = TriggerDagRunOperator(
        task_id="trigger_train_autoencoder_kmeans_pipeline",
        trigger_dag_id="dag_log_deep_network_clustering_kmeans",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
    )

    logger.info("[DAG_ORCHESTRATOR] trigger_log_clustering_iforest initialized")
    
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
    
    logger.info("[DAG_ORCHESTRATOR] Defining Stage 3: Notification")
    
    logger.info("[DAG_ORCHESTRATOR] trigger_send_sqs_message_dag initialized")

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

    # Enhanced pipeline structure logging with observability
    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span("pipeline_structure_defined") as span:
            trace_id = format(span.get_span_context().trace_id, '032x')
            logger.info(f"[DAG_ORCHESTRATOR] Pipeline ready - 3 stages, 7 tasks - trace_id={trace_id}")
    else:
        logger.info("[DAG_ORCHESTRATOR] Pipeline ready - 3 stages, 7 tasks")

