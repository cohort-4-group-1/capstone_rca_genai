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
        "service.version": "1.0.0",
        "dag.id": "dag_log_rca_orchestrator",
        "k8s.namespace.name": "airflow",  # Set correct namespace
        "k8s.pod.name": os.getenv("HOSTNAME", "unknown-pod"),
        "k8s.container.name": "worker",
        "k8s.cluster.name": "airflow-cluster",
        "deployment.environment": "production"
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
    
    # Configure logging - Direct OTEL export to Collector
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(
        OTLPLogExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT",
                             "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/logs",
            timeout=30,
            headers={"Content-Type": "application/x-protobuf"}
        )
    ))
    
    # Get tracer and meter for instrumentation
    tracer = trace.get_tracer(__name__)
    meter = metrics.get_meter(__name__)
    
    # Define metrics
    dag_executions = meter.create_counter("dag_executions_total", description="Total DAG executions")
    dag_duration = meter.create_histogram("dag_duration_seconds", description="DAG execution duration in seconds")
    task_executions = meter.create_counter("task_executions_total", description="Total task executions")
    task_duration = meter.create_histogram("task_duration_seconds", description="Task execution duration in seconds")
    pipeline_stages = meter.create_counter("pipeline_stages_total", description="Pipeline stages completed")
    
    OTEL_ENABLED = True
except ImportError:
    OTEL_ENABLED = False
    # Create dummy objects for when OTEL is not available
    tracer = None
    meter = None

# Direct OTEL logging setup - efficient single path to Loki
logger = logging.getLogger(__name__)

# Configure logger with OTEL handler for direct export
if OTEL_ENABLED:
    try:
        # Create OTEL handler for direct export
        otel_handler = LoggingHandler(logger_provider=logger_provider)
        
        # IMPORTANT: Only use OTEL handler - no file logging to avoid redundancy
        logger.handlers.clear()  # Remove any existing handlers
        logger.addHandler(otel_handler)
        logger.propagate = False  # Prevent propagation to avoid duplicate logs
        
        logger.setLevel(logging.INFO)
        
        # Wait a moment for any initialization to complete
        import time
        time.sleep(0.1)
        
        logger.info("[DAG_ORCHESTRATOR] Direct OTEL logging configured - single path to Loki")
        logger.info(f"[DAG_ORCHESTRATOR] Service: airflow-dag-orchestrator, Pod: {os.getenv('HOSTNAME', 'unknown-pod')}")
        
        # Force immediate flush
        otel_handler.flush()
        
        print(f"[DEBUG] OTEL logging configured successfully - endpoint: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://opentelemetry-collector.monitoring.svc.cluster.local:4318')}")
            
    except Exception as e:
        print(f"[ERROR] OTEL logging setup failed: {e}")
        logger.warning(f"[DAG_ORCHESTRATOR] OTEL logging setup failed: {e}")
else:
    logger.info("[DAG_ORCHESTRATOR] OTEL not available - using standard logging")

def on_dag_success(context):
    """Log DAG success with comprehensive observability"""
    run_id = context.get('run_id')
    dag_id = context.get('dag').dag_id
    start_date = context.get('data_interval_start')
    end_date = context.get('data_interval_end')
    
    # Calculate duration if possible
    duration = None
    if start_date and end_date:
        duration = (end_date - start_date).total_seconds()
    
    # Tracing
    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span("dag_success") as span:
            span.set_attributes({
                "dag.id": dag_id,
                "dag.run_id": run_id,
                "dag.status": "success",
                "dag.duration_seconds": duration or 0,
                "k8s.pod.name": os.getenv("HOSTNAME", "unknown-pod")
            })
            
            # Logging
            logger.info(f"[DAG_ORCHESTRATOR] DAG completed successfully - run_id={run_id} duration={duration}s")
            
            # Metrics
            dag_executions.add(1, {
                "status": "success", 
                "dag_id": dag_id,
                "pod_name": os.getenv("HOSTNAME", "unknown-pod")
            })
            
            if duration:
                dag_duration.record(duration, {
                    "status": "success",
                    "dag_id": dag_id
                })
    else:
        logger.info(f"[DAG_ORCHESTRATOR] DAG completed successfully - run_id={run_id}")
    
    print(f"[DEBUG] DAG success logged via OTEL - run_id={run_id} duration={duration}s")

def on_dag_failure(context):
    """Log DAG failure with comprehensive observability"""
    error = str(context.get('exception', 'Unknown'))
    run_id = context.get('run_id')
    dag_id = context.get('dag').dag_id
    task_id = context.get('task_instance', {}).task_id if context.get('task_instance') else 'unknown'
    
    # Tracing
    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span("dag_failure") as span:
            span.set_attributes({
                "dag.id": dag_id,
                "dag.run_id": run_id,
                "dag.status": "failure",
                "dag.error": error,
                "dag.failed_task": task_id,
                "k8s.pod.name": os.getenv("HOSTNAME", "unknown-pod")
            })
            span.set_status(trace.Status(trace.StatusCode.ERROR, error))
            
            # Logging
            logger.error(f"[DAG_ORCHESTRATOR] DAG execution failed - run_id={run_id} task={task_id} error={error}")
            
            # Metrics
            dag_executions.add(1, {
                "status": "failure", 
                "dag_id": dag_id,
                "failed_task": task_id,
                "pod_name": os.getenv("HOSTNAME", "unknown-pod")
            })
    else:
        logger.error(f"[DAG_ORCHESTRATOR] DAG execution failed - run_id={run_id} error={error}")
    
    print(f"[DEBUG] DAG failure logged via OTEL - run_id={run_id} error={error}")

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
            span.set_attributes({
                "dag.id": "dag_log_rca_orchestrator",
                "dag.type": "orchestrator",
                "dag.stages": 3,
                "k8s.pod.name": os.getenv("HOSTNAME", "unknown-pod")
            })
            
            # Log DAG start with enhanced context
            logger.info("[DAG_ORCHESTRATOR] RCA Pipeline Orchestrator initialized with full observability")
            logger.info(f"[DAG_ORCHESTRATOR] OTEL instrumentation active - traces, metrics, and logs enabled")
            
            span.add_event("dag_initialized", {
                "stages_planned": 3,
                "tasks_planned": 7,
                "observability": "enabled"
            })
    else:
        logger.info("[DAG_ORCHESTRATOR] RCA Pipeline Orchestrator initialized")

    # =============================================================================
    # STAGE 1: DATA PREPARATION (Sequential)
    # =============================================================================
    
    logger.info("[DAG_ORCHESTRATOR] Defining Stage 1: Data Preparation (Sequential)")
    if OTEL_ENABLED:
        pipeline_stages.add(1, {"stage": "data_preparation", "stage_number": 1, "type": "sequential"})
    
    trigger_dag_log_parse = TriggerDagRunOperator(
        task_id="trigger_log_parse",
        trigger_dag_id="dag_log_parse",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed']
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
    if OTEL_ENABLED:
        pipeline_stages.add(1, {"stage": "model_training", "stage_number": 2, "type": "parallel"})

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
    if OTEL_ENABLED:
        pipeline_stages.add(1, {"stage": "notification", "stage_number": 3, "type": "single"})
    
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
            span.set_attributes({
                "pipeline.stages": 3,
                "pipeline.total_tasks": 7,
                "pipeline.parallel_tasks": 3,
                "pipeline.sequential_tasks": 4,
                "pipeline.type": "ml_rca_pipeline"
            })
            
            logger.info("[DAG_ORCHESTRATOR] Pipeline structure defined with full observability")
            logger.info("[DAG_ORCHESTRATOR] 3 stages: data_preparation -> model_training -> notification")
            logger.info(f"[DAG_ORCHESTRATOR] Total tasks: 7 (4 sequential, 3 parallel)")
            logger.info(f"[DAG_ORCHESTRATOR] Observability: logs->OTEL->Loki, traces->OTEL->Jaeger, metrics->OTEL->Prometheus")
            
            span.add_event("pipeline_ready", {
                "dag_id": "dag_log_rca_orchestrator",
                "observability_configured": True,
                "single_path_logging": True
            })
    else:
        logger.info("[DAG_ORCHESTRATOR] Pipeline structure defined - 3 stages: data_preparation -> model_training -> notification")

