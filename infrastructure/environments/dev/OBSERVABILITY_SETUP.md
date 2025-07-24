# Observability Stack for Airflow

This document describes the comprehensive observability setup that has been implemented for monitoring Airflow logs, metrics, and traces.

## Components Overview

The observability stack consists of the following components:

### 1. **Loki** - Log Aggregation
- **Purpose**: Centralized log storage and querying
- **Configuration**: `loki-values.yaml`
- **Deployment**: SingleBinary mode with 10Gi persistent storage
- **Storage**: GP3 storage class for optimal performance
- **Access**: Available via Grafana or direct API calls

### 2. **OpenTelemetry Collector** - Unified Telemetry Hub
- **Purpose**: Single agent for collecting logs, metrics, and traces
- **Configuration**: `otel-collector-values.yaml`
- **Deployment**: DaemonSet running on all nodes for log collection + centralized processing
- **Features**: 
  - **Logs**: Direct Kubernetes pod log collection and forwarding to Loki
  - **Metrics**: Prometheus scraping and Kubernetes cluster metrics
  - **Traces**: OTLP trace collection and forwarding to Jaeger
- **Benefits**: Unified configuration, reduced complexity, better resource efficiency

### 3. **Jaeger** - Distributed Tracing
- **Purpose**: Tracks request flows across Airflow components
- **Configuration**: `jaeger-values.yaml`
- **Deployment**: All-in-one deployment with persistent storage
- **Ports**: 
  - UI: 16686
  - Collector: 14268
  - OTLP gRPC: 4317
  - OTLP HTTP: 4318

### 4. **Grafana** - Visualization Dashboard
- **Purpose**: Unified dashboard for logs, metrics, and traces
- **Configuration**: `grafana-values.yaml`
- **Datasources**:
  - Prometheus (metrics)
  - Loki (logs)
  - Jaeger (traces)
- **Features**: Pre-configured Airflow dashboards, correlation between logs and traces

## Data Flow

```
Airflow Pods → OpenTelemetry Collector → Loki (Logs)
              ↓                      → Prometheus (Metrics)  
              ↓                      → Jaeger (Traces)
              ↓
              → Grafana (Unified Dashboard)
```

## Airflow Integration

### OpenTelemetry Instrumentation
- **Configuration**: Added to `airflow-values.yaml`
- **Auto-instrumentation**: Flask, SQLAlchemy, Psycopg2, Requests
- **Custom configuration**: `airflow-otel-configmap.yaml`
- **Unified telemetry**: Logs, metrics, and traces all sent to OTEL Collector
- **Trace correlation**: Log entries include trace IDs for correlation

### Environment Variables
```yaml
OTEL_SERVICE_NAME: "airflow"
OTEL_EXPORTER_OTLP_ENDPOINT: "http://opentelemetry-collector:4318"
OTEL_TRACES_EXPORTER: "otlp"
OTEL_METRICS_EXPORTER: "otlp"
OTEL_LOGS_EXPORTER: "otlp"
```

### Log Enhancement
- Custom log formatter adds trace context
- Structured logging for better parsing
- Correlation between logs and distributed traces

## Deployment Commands

To deploy the complete observability stack:

```bash
# Deploy observability components
terraform plan
terraform apply

# Verify deployments
kubectl get pods -n loki
kubectl get pods -n jaeger  
kubectl get pods -n opentelemetry-operator-system
kubectl get pods -n monitoring  # Grafana Alloy
kubectl get pods -n airflow

# Access Grafana dashboard
kubectl port-forward -n grafana svc/grafana 3000:80
# Visit: http://localhost:3000
```

## Accessing the Stack

### Grafana Dashboard
- **URL**: `http://localhost:3000` (via port-forward)
- **Credentials**: Admin credentials configured in helm values
- **Features**:
  - Airflow overview dashboard
  - Infrastructure monitoring
  - Log exploration with Loki
  - Trace analysis with Jaeger

### Direct Access to Components
```bash
# Loki (logs)
kubectl port-forward -n loki svc/loki-gateway 3100:80

# Jaeger UI (traces)  
kubectl port-forward -n jaeger svc/jaeger-query 16686:16686

# Prometheus (metrics)
kubectl port-forward -n prometheus svc/prometheus-server 9090:80
```

## Monitoring Capabilities

### 1. **Log Analysis**
- Real-time log streaming from all Airflow components
- Structured log querying with LogQL
- Log-based alerting
- Trace correlation in log entries

### 2. **Metrics Monitoring**
- Airflow DAG execution metrics
- Task success/failure rates
- Queue sizes and worker utilization
- Kubernetes cluster metrics
- Custom business metrics from DAGs

### 3. **Distributed Tracing**
- End-to-end request tracing
- DAG execution flow visualization
- Performance bottleneck identification
- Cross-service dependency mapping

### 4. **Alerting**
- Grafana alerting rules
- Integration with Slack/email notifications
- SLA monitoring for critical DAGs
- Infrastructure health alerts

## Best Practices

### 1. **Resource Management**
- Configured resource limits for all components
- GP3 storage for optimal cost/performance
- Efficient log retention policies

### 2. **Security**
- RBAC configured for all components
- Non-root containers with security contexts
- ServiceAccount with minimal permissions

### 3. **Performance**
- Batch processing for telemetry data
- Memory limiters to prevent OOM
- Optimized sampling rates for traces

### 4. **Maintenance**
- ServiceMonitors for self-monitoring
- Health checks for all components
- Automated log rotation and cleanup

## Troubleshooting

### Common Issues
1. **OTEL Collector not receiving data**: Check Airflow environment variables
2. **Loki storage issues**: Verify GP3 storage class and PVC status
3. **Missing traces**: Ensure OTLP exporters are configured correctly
4. **High resource usage**: Adjust sampling rates and batch sizes

### Debugging Commands
```bash
# Check OTEL collector logs
kubectl logs -n opentelemetry-operator-system deployment/opentelemetry-collector

# Check OTEL collector logs and log processing
kubectl logs -n opentelemetry-operator-system daemonset/opentelemetry-collector

# Check Jaeger connectivity
kubectl logs -n jaeger deployment/jaeger
```

## Configuration Files

- `variables.tf`: Feature flags for observability components
- `main.tf`: Helm module definitions
- `loki-values.yaml`: Loki configuration
- `alloy-values.yaml`: Modern log collection configuration (replaces promtail-values.yaml)  
- `jaeger-values.yaml`: Distributed tracing configuration
- `otel-collector-values.yaml`: Telemetry collection hub
- `grafana-values.yaml`: Dashboard and datasource configuration
- `airflow-values.yaml`: Airflow with OTEL instrumentation
- `airflow-otel-configmap.yaml`: OTEL auto-instrumentation configuration

This observability stack provides comprehensive monitoring for your Airflow deployment, enabling you to monitor logs via Loki, metrics via Prometheus, and traces via Jaeger, all unified in Grafana dashboards.
