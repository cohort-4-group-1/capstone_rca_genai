#!/bin/bash

echo "Ensuring Prometheus scrape configuration is applied..."

# Wait for Prometheus pod to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server -n monitoring --timeout=300s

# Check if the extraScrapeConfigs are properly applied
if ! kubectl get configmap prometheus-server -n monitoring -o yaml | grep -q "opentelemetry-collector"; then
  echo "Prometheus extraScrapeConfigs not found, applying manual patch..."
  echo "Note: This should be automatic with Terraform. Check if prometheus-values.yaml is being applied correctly."
  
  # Apply the scrape configuration patch
  kubectl patch configmap prometheus-server -n monitoring --patch='
data:
  prometheus.yml: |
    global:
      evaluation_interval: 1m
      scrape_interval: 1m
      scrape_timeout: 10s
      external_labels:
        cluster: airflow-cluster
    rule_files:
    - /etc/config/recording_rules.yml
    - /etc/config/alerting_rules.yml
    - /etc/config/rules
    - /etc/config/alerts
    scrape_configs:
    - job_name: prometheus
      static_configs:
      - targets:
        - localhost:9090
    # OpenTelemetry Collector metrics (where custom DAG metrics are exposed)
    - job_name: opentelemetry-collector
      static_configs:
      - targets:
        - opentelemetry-collector.monitoring.svc.cluster.local:8889
      scrape_interval: 15s
      metrics_path: /metrics
      scheme: http
    # Airflow built-in metrics
    - job_name: airflow-webserver
      static_configs:
      - targets:
        - airflow-webserver.airflow.svc.cluster.local:8080
      scrape_interval: 30s
      metrics_path: /admin/metrics
      scheme: http
    - job_name: airflow-scheduler
      static_configs:
      - targets:
        - airflow-scheduler.airflow.svc.cluster.local:8080
      scrape_interval: 30s
      metrics_path: /admin/metrics
      scheme: http
    alerting:
      alertmanagers:
      - static_configs:
        - targets:
          - prometheus-alertmanager.monitoring.svc.cluster.local:9093
        scheme: http
        timeout: 10s
        api_version: v2
'
  
  # Restart Prometheus to apply the new configuration
  echo "Restarting Prometheus to apply new configuration..."
  kubectl delete pod -l app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server -n monitoring
  
  # Wait for Prometheus to be ready again
  kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server -n monitoring --timeout=300s
  
  echo "Prometheus configuration applied and restarted successfully!"
else
  echo "Prometheus extraScrapeConfigs already properly configured."
fi

echo ""
echo "=== PERMANENT SOLUTION ==="
echo "To avoid manual patches, ensure Terraform properly applies prometheus-values.yaml:"
echo "1. Run: terraform apply -target=module.prometheus[0] -replace=module.prometheus[0].helm_release.this[0]"
echo "2. This forces Helm to recreate the Prometheus release with correct values"
echo "3. The values/prometheus-values.yaml file already contains the correct extraScrapeConfigs"
