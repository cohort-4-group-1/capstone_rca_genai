# Observability Guide: Logs, Metrics, and Traces for Capstone RCA GenAI

## Overview
This document explains how observability is implemented in the Capstone RCA GenAI project, covering logs, metrics, and traces for both the API and Airflow components. It describes the OpenTelemetry (OTEL) setup, the role of the OTEL Collector (as a DaemonSet), and how data flows to backends like Prometheus, Grafana, Jaeger, and Loki.

---

## 1. OpenTelemetry Architecture

- **OTEL SDKs**: Used in both the API (FastAPI) and Airflow DAGs to instrument code for logs, metrics, and traces.
- **OTEL Collector (DaemonSet)**: Runs on every node in the cluster, receiving telemetry from all pods via OTLP (gRPC/HTTP).
- **Backends**:
  - **Prometheus**: Stores and visualizes metrics (via Grafana dashboards).
  - **Jaeger**: Stores and visualizes traces (distributed tracing).
  - **Loki**: Stores and visualizes logs (via Grafana).

---

## 2. API Observability (FastAPI)

### a. Metrics
- **Emitted via OTEL Python SDK** using the OTLP exporter.
- **Custom Metrics**:
  - `api_requests_total`: Counter for total API requests.
  - `api_request_duration_seconds`: Histogram for request durations.
  - `api_errors_total`: Counter for API errors.
- **Flow**: API → OTEL Collector (OTLP HTTP) → Prometheus Exporter → Prometheus → Grafana
- **Prometheus Scraping**: Prometheus scrapes the OTEL Collector's `/metrics` endpoint (port 8889), not the API directly.

### b. Traces
- **Emitted via OTEL Python SDK** (auto-instrumented and custom spans).
- **Flow**: API → OTEL Collector (OTLP HTTP) → Jaeger Exporter → Jaeger UI
- **Usage**: Distributed tracing for API endpoints and internal operations.

### c. Logs
- **Emitted via OTEL Python SDK** (structured logs).
- **Flow**: API → OTEL Collector (OTLP HTTP) → Loki Exporter → Loki → Grafana
- **Usage**: Centralized, queryable logs for debugging and monitoring.

---

## 3. Airflow Observability

### a. Metrics
- **Emitted via OTEL Python SDK** in DAG code (custom metrics for DAG/task runs, durations, etc.).
- **Flow**: Airflow DAGs → OTEL Collector (OTLP HTTP) → Prometheus Exporter → Prometheus → Grafana
- **Prometheus Scraping**: Prometheus scrapes the OTEL Collector's `/metrics` endpoint.

### b. Traces
- **Emitted via OTEL Python SDK** in DAG code (custom spans for DAG/task execution).
- **Flow**: Airflow DAGs → OTEL Collector → Jaeger Exporter → Jaeger UI

### c. Logs
- **Collected via OTEL Collector Filelog Receiver** from pod log files.
- **Flow**: Airflow pod logs → OTEL Collector (filelog receiver) → Loki Exporter → Loki → Grafana

---

## 4. OTEL Collector as DaemonSet
- **Deployment**: The OTEL Collector runs as a DaemonSet in the `monitoring` namespace, ensuring every node can collect telemetry from all pods.
- **Receivers**:
  - `otlp`: Receives logs, metrics, and traces from instrumented apps (API, Airflow) via OTLP HTTP/gRPC.
  - `filelog`: Collects logs from Kubernetes pod log files.
  - `prometheus`: (Optional) Can scrape metrics endpoints if needed.
- **Exporters**:
  - `prometheus`: Exposes metrics for Prometheus to scrape.
  - `jaeger`: Sends traces to Jaeger.
  - `loki`: Sends logs to Loki.

---

## 5. Namespaces and Integration
- **API**: Deployed in the `api` namespace, instrumented with OTEL SDK, sends telemetry to the OTEL Collector in `monitoring`.
- **Airflow**: Deployed in the `airflow` namespace, DAGs instrumented with OTEL SDK, sends telemetry to the OTEL Collector.
- **Collector**: Deployed as a DaemonSet in the `monitoring` namespace, accessible cluster-wide.

---

## 6. How to View Observability Data
- **Metrics**: View in Grafana (data source: Prometheus). Dashboards show API and Airflow metrics.
- **Traces**: View in Jaeger UI. Search for traces by service name or provide the trace_id to view the spans if add for any endpoint how much time is consumed per span(e.g., `rca-api`, `airflow-worker`).
- **Logs**: View in Grafana (data source: Loki). Query logs by pod, namespace, or label.

---

## 7. Troubleshooting
- **No metrics in Prometheus?**
  - Check OTEL Collector logs for errors.
  - Ensure correct OTEL environment variables in pods.
  - Confirm Prometheus is scraping the OTEL Collector's `/metrics` endpoint.
- **No traces in Jaeger?**
  - Check OTEL Collector and Jaeger logs.
  - Ensure OTEL SDK is instrumenting your code.
- **No logs in Loki?**
  - Check filelog receiver config in OTEL Collector.
  - Ensure pod logs are being written to expected locations.

---

## 8. References
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [Prometheus](https://prometheus.io/)
- [Grafana](https://grafana.com/)
- [Jaeger](https://www.jaegertracing.io/)
- [Loki](https://grafana.com/oss/loki/)

---

For further details, see the code in `code/model-deployment/api/app/otel.py`, Airflow DAGs, and the OTEL Collector Helm values in `infrastructure/environments/dev/values/otel-collector-values.yaml`.
