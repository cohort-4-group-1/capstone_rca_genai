# orchestrator_dag.py
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime
from airflow.utils.dates import days_ago
from airflow.utils.context import Context

def get_current_execution_date(execution_date, **kwargs):
    return execution_date

with DAG(
    dag_id="dag_log_rca_orchestrator",
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["orchestrator"]
) as dag:

    dag_log_parse = TriggerDagRunOperator(
        task_id="parse_convert_raw_log_to_structured",
        trigger_dag_id="dag_log_parse"
    )

    dag_log_template = TriggerDagRunOperator(
        task_id="generate_template",
        trigger_dag_id="dag_log_template"
        
    )

    dag_log_sequence = TriggerDagRunOperator(
        task_id="generate_log_sequence",
        trigger_dag_id="dag_log_sequence"
    )

    dag_log_clustering_kmeans = TriggerDagRunOperator(
        task_id="train_rca_model_clustering_kmeans",
        trigger_dag_id="dag_log_clustering_kmeans"
    )

    dag_log_deep_network_clustering_kmeans = TriggerDagRunOperator(
        task_id="train_autoencoder_kmeans_pipeline",
        trigger_dag_id="dag_log_deep_network_clustering_kmeans"
    )

    dag_log_parse >> dag_log_template >> dag_log_sequence >>  [dag_log_clustering_kmeans, dag_log_deep_network_clustering_kmeans]