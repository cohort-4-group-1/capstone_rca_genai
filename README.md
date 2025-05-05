# capstone_rca_genai
This repository contains the capstone project - RCA with GenAI

# How to install Managed Apache Airflow
https://docs.aws.amazon.com/mwaa/latest/userguide/quick-start.html

aws cloudformation create-stack --stack-name rca-apache-workflow --template-body file://rca-apache-workflow.yml --capabilities CAPABILITY_IAM

# How to delete the Airflow stack

aws cloudformation delete-stack --stack-name rca-apache-workflow

# Airflow DAG Reference

https://airflow.apache.org/docs/apache-airflow/2.2.2/tutorial.html
