# orchestrator_dag.py
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime

with DAG(
    dag_id="dag_log_rca_orchestrator",
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["orchestrator"]
) as dag:

    trigger_dag_log_parse = TriggerDagRunOperator(
        task_id="trigger_log_parse",
        trigger_dag_id="dag_log_parse",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed', 'skipped']
    )
    
    trigger_dag_log_eda = TriggerDagRunOperator(
        task_id="trigger_log_eda",
        trigger_dag_id="dag_log_eda",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed', 'skipped']
    )

    trigger_dag_log_template = TriggerDagRunOperator(
        task_id="trigger_log_template",
        trigger_dag_id="dag_log_template",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed', 'skipped']
    )

    trigger_dag_log_sequence = TriggerDagRunOperator(
        task_id="trigger_log_sequence",
        trigger_dag_id="dag_log_sequence",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed', 'skipped']
    )

    trigger_dag_log_clustering_kmeans = TriggerDagRunOperator(
        task_id="trigger_train_rca_model_clustering_kmeans",
        trigger_dag_id="dag_log_clustering_kmeans",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed', 'skipped']
    )

    trigger_dag_log_deep_network_clustering_kmeans = TriggerDagRunOperator(
        task_id="trigger_train_autoencoder_kmeans_pipeline",
        trigger_dag_id="dag_log_deep_network_clustering_kmeans",
        wait_for_completion=True,
        poke_interval=30,
        allowed_states=['success'], 
        failed_states=['failed', 'skipped']
    )

    trigger_dag_log_parse >> trigger_dag_log_eda >> trigger_dag_log_template >> trigger_dag_log_sequence >> [
        trigger_dag_log_clustering_kmeans,
        trigger_dag_log_deep_network_clustering_kmeans
    ]
