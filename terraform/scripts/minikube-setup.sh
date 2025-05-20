#!/bin/bash
# filepath: /Users/alokkashimath/Documents/project_code/ak_poc/iisc/capstone_rca_genai/terraform/scripts/minikube-setup.sh

# Stop any existing minikube clusters
echo "Stopping any existing Minikube clusters..."
minikube stop || true

# Delete existing minikube cluster if it exists
echo "Deleting any existing Minikube clusters..."
minikube delete || true

# Start Minikube with the necessary configurations for M4 Mac with 24GB RAM
echo "Starting Minikube with recommended resources for MLOps platform..."
minikube start --cpus=4 --memory=7000 --disk-size=30g --driver=docker
# # Enable the necessary addons
# echo "Enabling required Minikube addons..."
# minikube addons enable ingress
# minikube addons enable metrics-server
# minikube addons enable dashboard
# minikube addons enable storage-provisioner

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Move to the root of the repo (one level up from script)
TERRAFORM_PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Set up the Kubernetes context for Helm
echo "Configuring kubectl to use Minikube..."
kubectl config use-context minikube

# Install Helm if not already installed
if ! command -v helm &> /dev/null
then
    echo "Helm not found, installing..."
    curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
fi

# Add helm repos for all our applications
echo "Adding Helm repositories for MLOps tools..."
helm repo add apache-airflow https://airflow.apache.org
# helm repo add clearml https://allegroai.github.io/clearml-helm-charts
helm repo add dask https://helm.dask.org
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add mlflow https://community-charts.github.io/helm-charts
helm repo add community-charts https://community-charts.github.io/helm-charts
helm repo update

# Report the Minikube IP for accessing services
echo "Minikube IP: $(minikube ip)"
echo "Minikube Dashboard URL: $(minikube dashboard --url &>/dev/null & sleep 2; echo $!)"
echo "Minikube setup complete. You can now deploy your applications using Terraform."
echo ""
echo "To deploy with Terraform, run:"
echo "cd ${TERRAFORM_PROJECT_ROOT}"
echo "terraform init && terraform apply"
echo " ====================================================="
echo "To remove the services, run:"
echo "cd ${TERRAFORM_PROJECT_ROOT}"
echo "terraform destroy"
echo " ====================================================="
echo "To stop the Minikube cluster, run:"
echo "minikube stop"
echo " ====================================================="
echo "To delete the Minikube cluster, run:"
echo "minikube delete"

