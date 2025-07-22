import logging
import os

# OpenTelemetry imports
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

    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "rca-api"),
    })

    # Tracing
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/traces")
    ))
    trace.set_tracer_provider(trace_provider)
    tracer = trace.get_tracer(__name__)

    # Metrics
    metrics_endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector.monitoring.svc.cluster.local:4318") + "/v1/metrics")
    metrics_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=metrics_endpoint, headers={}),
                export_interval_millis=5000
            )
        ]
    )
    metrics.set_meter_provider(metrics_provider)
    meter = metrics.get_meter(__name__)

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
except ImportError as e:
    logger = logging.getLogger("rca-otel")
    tracer = None
    meter = None
    OTEL_ENABLED = False
    logger.warning(f"[OTEL] OpenTelemetry not available: {e}")
