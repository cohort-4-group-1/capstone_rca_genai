from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import boto3
import pandas as pd
import dask.dataframe as dd
import matplotlib.pyplot as plt
from io import BytesIO
import configuration
from dask.distributed import Client

def safe_int(val):
    try:
        return int(val.compute())
    except AttributeError:
        return int(val)

def analyse_contextual_analysis(df):

    



# # DAG Start Time (rounded down to nearest 30 mins minus 5 mins)
# now_utc = datetime.now(timezone.utc)
# start_date_utc = now_utc.replace(minute=(now_utc.minute // 30) * 30, second=0, microsecond=0) - timedelta(minutes=5)
# with DAG(
#     dag_id='dag_log_eda',
#     start_date=datetime(2023, 1, 1),
#     schedule_interval=None,
#     catchup=False,
#     is_paused_upon_creation=False,
#     tags=['s3', 'validation', 'etl'],
# ) as dag:
#     task = PythonOperator(
#         task_id="perform_dask_eda_and_save_to_s3",
#         python_callable=perform_dask_eda_and_save_to_s3
#     )
