# orchestrator_dag.py
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime

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

    wait_for_template = ExternalTaskSensor(
        task_id="wait_for_template_completion",
        external_dag_id="dag_log_template",
        external_task_id="generate_template",
        allowed_states=["success"],
        timeout=600,
        poke_interval=30,
        mode="poke"
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

    dag_log_parse >> dag_log_template
    dag_log_template >> wait_for_template >> dag_log_sequence
    dag_log_sequence >> [dag_log_clustering_kmeans, dag_log_deep_network_clustering_kmeans]