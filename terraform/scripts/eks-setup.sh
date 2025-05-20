#!/bin/bash
# filepath: /Users/alokkashimath/Documents/project_code/ak_poc/iisc/capstone_rca_genai/terraform/scripts/eks-setup.sh

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    echo "Visit: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "kubectl is not installed. Please install it first."
    echo "Visit: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Move to the root of the repo (one level up from script)
TERRAFORM_PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Get the AWS region and EKS cluster name from Terraform output
cd "$TERRAFORM_PROJECT_ROOT"
# Make sure the Terraform state exists
if [ ! -f "terraform.tfstate" ]; then
    echo "Terraform state file not found. Please run terraform init and terraform apply first."
    exit 1
fi

# Extract EKS cluster information
CLUSTER_NAME=$(terraform output -raw eks_cluster_id 2>/dev/null)
AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")

if [ -z "$CLUSTER_NAME" ]; then
    echo "EKS cluster name not found in Terraform output. Make sure 'use_eks' is set to true and terraform apply has been run."
    exit 1
fi

echo "====================================================="
echo "Setting up kubectl for EKS cluster: $CLUSTER_NAME"
echo "====================================================="

# Update kubeconfig
echo "Updating kubeconfig for EKS cluster..."
aws eks update-kubeconfig --region $AWS_REGION --name $CLUSTER_NAME

# Verify the connection
echo "Verifying connection to EKS cluster..."
kubectl get nodes

# Verify cluster info
echo "Cluster information:"
kubectl cluster-info

echo "====================================================="
echo "EKS setup complete. You can now interact with your EKS cluster using kubectl."
echo "====================================================="
