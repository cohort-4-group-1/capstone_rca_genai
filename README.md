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

kubectl port-forward pod/airflow-webserver-688d749456-ngd8r 8080:8080 -n airflow        
kubectl port-forward pod/mlflow-d8f567dff-jpcpn 5000:5000 -n mlflow        

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
terraform state show aws_s3_bucket.my_bucket

terraform destroy --auto-approve

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


# FastAPI
docker build -t logbert-api -f Dockerfile.api .
docker tag logbert-api sujittah/logbert-api:latest
docker push sujittah/logbert-api:latest

# Gradio
docker build -t logbert-ui -f Dockerfile.gradio .
docker tag logbert-ui sujittah/logbert-ui:latest
docker push sujittah/logbert-ui:latest


 aws ec2 describe-volumes --filters Name=tag:ebs.csi.aws.com/cluster,Values=true Name=status,Values=available --query "Volumes[*][VolumeId,Tags[?Key=='kubernetes.io/created-for/pvc/name']|[0].Value,Size,CreateTime]" --output table
```

To delete all the volumes 

``` s.csi.aws.com/cluster,Values=true Name=status,Values=available --query "Volumes[*].VolumeId" --output text | xargs -n1 aws ec2 delete-volume --volume-id




vol-059159e86323fde4c                                                                        