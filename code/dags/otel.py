# Simple OpenTelemetry setup (optional - graceful fallback if not available)
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
import os
import logging

try:
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
    
    # Configure metrics - use the specific endpoint if available
    metrics_endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", 
                                os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", 
                                        "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/metrics")
    
    metrics_provider = MeterProvider(
        resource=resource, 
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=metrics_endpoint,
                    headers={}
                ),
                export_interval_millis=5000  # Export every 5 seconds
            )
        ]
    )
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
    meter = metrics.get_meter(__name__)# Simple OpenTelemetry setup (optional - graceful fallback if not available)
     # Logging
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(
        OTLPLogExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/logs",
            timeout=30
        )
    ))

    logger = logging.getLogger("rca-otel")
    otel_handler = LoggingHandler(logger_provider=logger_provider)
    logger.handlers.clear()
    logger.addHandler(otel_handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.info("[OTEL] OpenTelemetry logging configured")
    OTEL_ENABLED = True


   
except Exception as e:
    OTEL_ENABLED = False
    tracer = None
    meter = None
    logger = logging.getLogger("rca-otel")
    logger.error(f"[OTEL] OpenTelemetry setup failed: {str(e)}")