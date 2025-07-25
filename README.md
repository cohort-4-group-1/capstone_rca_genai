# capstone_rca_genai
This repository contains the capstone project - RCA with GenAI

## 📋 Table of Contents
- [Infrastructure Setup](#infrastructure-setup)
- [Observability Stack](#observability-stack)
- [Application Services](#application-services)
- [Development Commands](#development-commands)

## 🏗️ Infrastructure Setup

# Terraform commands
    terraform init
    terraform validate
    terraform plan
    terraform apply -auto-approve

## 📊 Observability Stack

This project includes a comprehensive observability stack for monitoring logs, metrics, and traces:

- **Loki**: Log aggregation and storage
- **Prometheus**: Metrics collection and storage  
- **Jaeger**: Distributed tracing
- **OpenTelemetry Collector**: Unified telemetry hub
- **Grafana**: Unified dashboard for all observability data

**📖 For detailed setup and usage:** See [`infrastructure/environments/dev/OBSERVABILITY_SETUP.md`](infrastructure/environments/dev/OBSERVABILITY_SETUP.md)

### Quick Access to Observability Services:
```bash
# Grafana (unified dashboard)
kubectl port-forward -n monitoring svc/grafana 3000:3000

# Prometheus (metrics)
kubectl port-forward -n monitoring svc/prometheus-server 9090:80

# Loki (logs) 
kubectl port-forward -n monitoring svc/loki-gateway 3100:80

# Jaeger (traces)
kubectl port-forward -n monitoring svc/jaeger-query 16686:16686
```

# How to install Managed Apache Airflow
https://docs.aws.amazon.com/mwaa/latest/userguide/quick-start.html

aws cloudformation create-stack --stack-name rca-apache-workflow --template-body file://rca-apache-workflow.yml --capabilities CAPABILITY_IAM

# How to delete the Airflow stack

aws cloudformation delete-stack --stack-name rca-apache-workflow

# Airflow DAG Reference

https://airflow.apache.org/docs/apache-airflow/2.2.2/tutorial.html


eksctl create cluster --name airflow --region us-east-1 --version 1.32   --nodegroup-name airflow-node-group --node-type t3.medium --nodes 5 --nodes-min 5 --nodes-max 8  --managed

eksctl delete cluster --name airflow-eks --region us-east-1

aws eks --region us-east-1 update-kubeconfig --name iisc-capstone-rca-eks                                                  
helm install airflow bitnami/airflow --namespace  airflow -f ./values.yaml


## Changelog

5.21.2025: Updated the access keys for Terraform setup.

## docker command

docker build -t airflow/airflow-custom:2.10.5 .
docker tag airflow/airflow-custom:2.10.5 sujittah/airflow-custom:2.10.5
docker push sujittah/airflow-custom:2.10.5


docker build -t dask/dask-custom:2023.12.1 .
docker tag dask/dask-custom:2023.12.1 sujittah/dask-custom:2023.12.1
docker push sujittah/dask-custom:2023.12.1


kubectl port-forward pod/airflow-webserver-75dcbd77db-n7s6d 8080:8080 -n airflow        
kubectl port-forward pod/mlflow-d8f567dff-zrnf9 5000:5000 -n mlflow   
kubectl port-forward pod/logbert-api-65cc455f5-6xl98  9000:9000 -n api
kubectl port-forward pod/logbert-ui-594f4c5d66-d7xt9  7860:7860 -n api

kubectl port-forward pod/airflow-webserver-759fccf694-ftk5n 8080:8080 -n airflow        
```

## 🔧 Application Services

### Port Forwarding Commands:

kubectl port-forward pod/mlflo   
kubectl port-forward pod/logbert-api-f89c5b9ff-kshzr  9000:9000 -n api


kubectl port-forward pod/mlflo



w-d8f567dff-k5fl7 5000:5080 -n mlflow        


# Airflow
kubectl port-forward -n airflow svc/airflow-webserver 8080:8080

# ClearML
kubectl port-forward -n clearml svc/clearml-webserver 8080:8080

# Prometheus
kubectl port-forward -n monitoring svc/prometheus-server 9090:9090

# Grafana
kubectl port-forward -n monitoring svc/grafana 3000:3000

# Dask
kubectl port-forward -n dask svc/dask-scheduler 8787:8787

# MLflow
kubectl port-forward -n mlflow svc/mlflow 5000:5000

# Terraform 
terraform init -reconfigure  -backend-config="profile=default"
terraform validate
terraform apply --auto-approve
terraform show
terraform state list
terraform state show <resource_name>
terraform state show aws _s3_bucket.my_bucket

terraform destroy --auto-approve

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


# FastAPI
docker build -t logbert-api -f Dockerfile.api .
docker tag logbert-api sujittah/logbert-api:latest
docker push sujittah/logbert-api:latest
docker run -p 9000:9000 -e AWS_ACCESS_KEY_ID=AKIASBXCEUGHRC6J7JWK -e AWS_SECRET_ACCESS_KEY=IJQoce3B5Aak19zxcTSlqBsOfp+/zegLtCJSlfQ -e AWS_DEFAULT_REGION=us-east-1 logbert-api --encoder

# Gradio
docker build -t logbert-ui -f Dockerfile.gradio .
docker tag logbert-ui sujittah/logbert-ui:latest
docker push sujittah/logbert-ui:latest

# Various Commads
 aws ec2 describe-volumes --filters Name=tag:ebs.csi.aws.com/cluster,Values=true Name=status,Values=available --query "Volumes[*][VolumeId,Tags[?Key=='kubernetes.io/created-for/pvc/name']|[0].Value,Size,CreateTime]" --output table
```

To delete all the volumes 

``` s.csi.aws.com/cluster,Values=true Name=status,Values=available --query "Volumes[*].VolumeId" --output text | xargs -n1 aws ec2 delete-volume --volume-id

aws ec2 delete-volume --volume-id 
vol-059159e86323fde4c                                                                        

uvicorn main_isolation_forest:app --host 0.0.0.0 --port 9000 --reload

aws eks --region us-east-1 update-kubeconfig --name iisc-capstone-rca-eks
kubetctl get pods -n airflow
kubectl port-forward pod/airflow-webserver-5d5f6f77cc-dbmbs 8080:8080 -n airflow        


aws logs describe-log-streams --log-group-name "/aws/lambda/SendMessageToSQS" --order-by LastEventTime --descending 
 --limit 3

 aws iam attach-user-policy --user-name terraform --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsReadOnlyAccess

 aws iam put-user-policy --user-name terraform --policy-name LambdaLogsReadAccess --policy-document file://cloudwatch-logs-inline-policy.json

aws logs get-log-events `
  --log-group-name "/aws/lambda/SendMessageToSQS" `
  --log-stream-name "2025/06/30/`[$LATEST`]71e28f6cfdd94ba98001444434efeb26"

helm upgrade --install rca-api code/model-deployment/logbert-chart-api -f code/model-deployment/logbert-chart-api/values.yaml  --namespace api

aws iam get-role --role-name iisc-capstone-rca-model-s3-access --query "Role.AssumeRolePolicyDocument" --output json

aws iam list-roles --query "Roles[?starts_with(RoleName, 'logbert-s3-access')].RoleName" --output text

aws lambda invoke --function-name SendMessageToSQS  output.json

iisc-capstone-rca-airflow-s3-access
aws s3api get-bucket-notification-configuration --bucket rca.logs.openstack


curl -X 'POST' \
  'http://airflow-webserver.airflow.svc.cluster.local:8080/api/v1/dags/dag_log_rca_orchestrator/dagRuns' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -u admin:Admin \
  -d '{
    "conf": {},
    "dag_run_id": "dag_log_rca_orchestrator",
    "data_interval_end": "2025-07-03T12:27:26.575Z",
    "data_interval_start": "2025-07-03T12:27:26.575Z",
    "logical_date": "2025-07-03T12:27:26.575Z",
    "note": "string"
}'