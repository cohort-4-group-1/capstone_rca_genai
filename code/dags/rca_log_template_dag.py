from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import rca_log_template  
import rca_log_sequence_generator

default_args = {
    'start_date': datetime(2024, 1, 1),
    'retries': 0
}

with DAG(
    dag_id="Step_3_rca_log_template_pipeline",
    schedule_interval=None,
    default_args=default_args,
    catchup=False,
    tags=["drain3", "log-parsing", "rca"],
    description="Extracts templates from structured logs and appends log key references"
) as dag:

    generate_templates = PythonOperator(
        task_id="generate_templates",
        python_callable=rca_log_template.convert_template_from_structured_log
    )

    append_log_keys = PythonOperator(
        task_id="append_log_keys_to_structured_log",
        python_callable=rca_log_template.append_log_key_to_structured_log
    )

    generate_log_sequence = PythonOperator(
        task_id="generate_log_sequence",
        python_callable=rca_log_sequence_generator.generate_log_sequence
    )

    generate_templates >> append_log_keys >> generate_log_sequence
