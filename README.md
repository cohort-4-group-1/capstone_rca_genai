# capstone_rca_genai
This repository contains the capstone project - RCA with GenAI

# Terraform commands
    terraform init
    terraform validate
    terraform plan
    terraform apply -auto-approve

# How to install Managed Apache Airflow
https://docs.aws.amazon.com/mwaa/latest/userguide/quick-start.html

aws cloudformation create-stack --stack-name rca-apache-workflow --template-body file://rca-apache-workflow.yml --capabilities CAPABILITY_IAM

# How to delete the Airflow stack

aws cloudformation delete-stack --stack-name rca-apache-workflow

# Airflow DAG Reference

https://airflow.apache.org/docs/apache-airflow/2.2.2/tutorial.html


eksctl create cluster --name airflow --region us-east-1 --version 1.32   --nodegroup-name airflow-node-group --node-type t3.medium --nodes 5 --nodes-min 5 --nodes-max 8  --managed

eksctl delete cluster --name airflow-eks --region us-east-1

aws eks --region us-east-1 update-kubeconfig --name apache-airflow-eks

helm install airflow bitnami/airflow --namespace  airflow -f ./values.yaml
