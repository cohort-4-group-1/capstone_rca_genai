# 🚀 Terraform Helm Deployment for Kubernetes (Minikube & EKS)

This repository provides a modular and configurable Terraform setup to deploy multiple MLOps services (Airflow, ClearML, Prometheus, Grafana, Dask, MLflow) using Helm charts on Kubernetes clusters. It supports both **Minikube (for local testing)** and **AWS EKS (for cloud deployment)**, with feature flags for each component.

---

## 📁 Directory Structure Overview

```
terraform/
├── main.tf                # Root Terraform configuration calling modules
├── variables.tf           # Feature flags and configurable inputs
├── terraform.tfvars       # Control which services to install (toggle true/false)
├── eks.tf                 # EKS cluster configuration (conditional)
├── vpc.tf                 # VPC setup for EKS (conditional)
├── storage-classes.tf     # Storage classes for EKS
├── providers.tf           # Provider config for EKS/Minikube
├── providers-minikube.tf  # Mock AWS provider for Minikube
├── scripts/               # Helper scripts for setup/testing
│   ├── minikube-setup.sh
│   ├── eks-setup.sh
│   ├── run-terraform-minikube.sh
│   └── test-deployment.sh
├── values/                # Custom Helm values per service
│   ├── airflow-values.yaml
│   ├── clearml-values.yaml
│   ├── dask-values.yaml
│   ├── grafana-values.yaml
│   ├── mlflow-values.yaml
│   └── prometheus-values.yaml
└── modules/helm_release/  # Reusable module to deploy Helm charts
    └── main.tf            # Defines the helm_release resource

.github/
└── workflows/
    ├── terraform-aws.yml      # CI/CD for EKS
    └── terraform-destroy.yml  # Safe destroy workflow

infrastructure/
├── cloudformation/            # (Optional) CloudFormation templates
├── environments/              # (Optional) Per-env Terraform
└── helm-chart/                # (Optional) Custom Helm charts

code/
└── poc/                       # Example ML code, DAGs, etc.
datasets/                      # Example datasets
```

---

## ⚙️ Prerequisites

Make sure the following are installed:

* [Terraform](https://developer.hashicorp.com/terraform/downloads)
* [Helm](https://helm.sh/docs/intro/install/)
* [kubectl](https://kubernetes.io/docs/tasks/tools/)
* [Minikube](https://minikube.sigs.k8s.io/docs/start/) **(for local)**
* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) **(for EKS)**
* `aws eks update-kubeconfig` configured for your EKS cluster

---

## 📦 What This Deploys (with Feature Flags)

Each service can be enabled or disabled via `terraform.tfvars`:

```hcl
install_airflow    = true
install_clearml    = false
install_prometheus = true
install_grafana    = false
install_dask       = false
install_mlflow     = false
```

This determines whether the module for that service is applied. You can also toggle EKS/Minikube with:

```hcl
use_eks = true   # Deploy to EKS
# or
use_eks = false  # Deploy to Minikube
```

---

## 🧪 Local Installation (Minikube)

### 1. Start Minikube

```bash
minikube start --cpus=4 --memory=8192
```

### 2. Run Terraform

```bash
cd terraform
../terraform/scripts/minikube-setup.sh   # (optional: helper for local env)
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

### 3. Port-forward to Access UI (example: Airflow)

```bash
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow
```

Open [http://localhost:8080](http://localhost:8080) in your browser.

---

## ☁️ Cloud Installation (EKS)

### 1. Configure EKS kubeconfig

```bash
aws eks update-kubeconfig --region <region> --name <cluster-name>
```

### 2. Verify Access

```bash
kubectl get nodes
```

### 3. Deploy with Terraform

```bash
cd terraform
terraform init
terraform apply -var-file="terraform.tfvars"
```

---

## 🤖 CI/CD Automation

- **GitHub Actions**: Automated workflows for deploy/destroy in `.github/workflows/`.
- **terraform-aws.yml**: Deploys to EKS on push to `main`.
- **terraform-destroy.yml**: Manual, with safety checks for environment and confirmation.

---

## 🧾 Module Details: `./modules/helm_release`

This module wraps Helm chart deployment with the following inputs:

* `name`: Helm release name
* `namespace`: Kubernetes namespace
* `chart`: Chart name
* `repo`: Helm chart repo URL
* `chart_version`: Optional chart version pin
* `values_files`: List of YAML files to override default values
* `enabled`: Feature flag to deploy or skip

It uses `helm_release` to install the chart, with `wait = false` and `timeout = 600` to improve compatibility.

---

## 🔁 Switching Between Minikube and EKS

Use `kubectl config use-context <context>` to switch:

```bash
kubectl config get-contexts
kubectl config use-context minikube  # for local
kubectl config use-context <eks-name>  # for EKS
```

Then simply re-run Terraform:

```bash
terraform apply -var-file="terraform.tfvars"
```

---

## 🧹 Cleanup

```bash
terraform destroy -var-file="terraform.tfvars"
# and optionally
kubectl delete namespace airflow
```

---

## ✅ Tips

* Pin Helm chart versions via `chart_version = "x.y.z"` in each module block
* Use separate namespaces per environment to avoid conflicts
* Use `wait = false` in Helm for services like Airflow to avoid readiness timeouts
* Use the helper scripts in `terraform/scripts/` for setup and testing
* For EKS, ensure your AWS credentials and S3 backend are configured for state

---

## 📬 Need Help?

Feel free to open an issue or reach out for example values, production tuning, or EKS cost optimization.
