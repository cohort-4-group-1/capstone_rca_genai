# MLOps Platform Deployment Guide

This guide provides detailed instructions for deploying the MLOps platform either on Minikube (locally) or on AWS EKS.

## Prerequisites

- Docker
- Kubernetes CLI (kubectl)
- Helm
- Terraform >= 1.2.0
- AWS CLI (for EKS deployment)
- Minikube (for local deployment)

## Deployment Options

This setup can be deployed in two ways:

1. **Local Minikube**: For development and testing
2. **AWS EKS**: For production environments

## Local Minikube Deployment

### Step 1: Set up Minikube

```bash
# Run the Minikube setup script
./scripts/minikube-setup.sh
```

This script:
- Starts Minikube with appropriate resources
- Enables necessary addons
- Adds Helm repositories for all services

### Step 2: Deploy the MLOps platform

```bash
# Initialize Terraform ./terrraform
terraform init

# Apply the Terraform configuration ./terraform
terraform apply
```

## AWS EKS Deployment

### Step 1: Configure AWS credentials

```bash
# Configure AWS CLI
aws configure
```

### Step 2: Update terraform.tfvars

Edit `terraform.tfvars` and set:
```
use_eks = true
```

Also update other EKS-related settings as needed:
```
aws_region = "us-east-1"
eks_cluster_name = "mlops-platform"
eks_instance_types = ["t3.medium"]
```

### Step 3: Deploy the MLOps platform

```bash
# Initialize Terraform
terraform init

# Apply the Terraform configuration
terraform apply
```

### Step 4: Configure kubectl for EKS

```bash
# Run the EKS setup script
./scripts/eks-setup.sh
```

## Accessing the Services

### Local Minikube

Use port-forwarding to access the services locally:

```bash
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
```


## Cleanup

### Minikube

```bash
# Destroy the Terraform resources
terraform destroy

# Stop Minikube
minikube stop
```

### EKS

```bash
# Destroy the Terraform resources (this will delete the EKS cluster)
terraform destroy
```
