terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.7.0"
    }
  }

  required_version = ">= 1.2.0"

  # Uncomment if you're storing state remotely
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-lock"
  # }
}

# AWS Configuration Variables (for EKS/infra if needed)
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "rca-with-llm"
}

module "airflow" {
  source           = "./modules/helm_release"
  count            = var.install_airflow ? 1 : 0

  enabled          = true
  name             = "airflow"
  namespace        = "airflow"
  chart            = "airflow"
  repo             = "https://airflow.apache.org"
  values_files     = ["${path.module}/values/airflow-values.yaml"]
  chart_version    = "1.16.0"
}
module "clearml" {
  source       = "./modules/helm_release"
  count        = var.install_clearml ? 1 : 0

  enabled      = true
  name         = "clearml"
  namespace    = "clearml"
  chart        = "clearml"
  repo         = "https://clearml.github.io/clearml-helm-charts"
  values_files = ["${path.module}/values/clearml-values.yaml"]
  chart_version = "7.14.4"
}

module "prometheus" {
  source       = "./modules/helm_release"
  count        = var.install_prometheus ? 1 : 0

  enabled      = true
  name         = "prometheus"
  namespace    = "monitoring"
  chart        = "prometheus"
  repo         = "https://prometheus-community.github.io/helm-charts"
  values_files = ["${path.module}/values/prometheus-values.yaml"]
  chart_version = "25.18.0"
}

module "grafana" {
  source       = "./modules/helm_release"
  count        = var.install_grafana ? 1 : 0

  enabled      = true
  name         = "grafana"
  namespace    = "monitoring"
  chart        = "grafana"
  repo         = "https://grafana.github.io/helm-charts"
  values_files = ["${path.module}/values/grafana-values.yaml"]
  chart_version = "7.3.0"
}

module "dask" {
  source       = "./modules/helm_release"
  count        = var.install_dask ? 1 : 0

  enabled      = true
  name         = "dask"
  namespace    = "dask"
  chart        = "dask"
  repo         = "https://helm.dask.org"
  values_files = ["${path.module}/values/dask-values.yaml"]
  chart_version = "2024.1.1"
}

module "mlflow" {
  source         = "./modules/helm_release"
  count          = var.install_mlflow ? 1 : 0

  enabled        = true
  name           = "mlflow"
  namespace      = "mlflow"
  chart          = "mlflow"
  repo           = "https://community-charts.github.io/helm-charts"
  chart_version  = "0.7.3"
  values_files   = ["${path.module}/values/mlflow-values.yaml"]
}