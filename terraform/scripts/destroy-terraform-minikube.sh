#!/bin/bash
# filepath: /Users/alokkashimath/Documents/project_code/ak_poc/iisc/capstone_rca_genai/terraform/scripts/run-terraform-minikube.sh

# This script runs Terraform with the necessary AWS environment variables disabled for Minikube deployment

# Set Terraform working directory
cd "$(dirname "$0")/.."

# Disable AWS EC2 metadata API check to avoid credential errors
export AWS_EC2_METADATA_DISABLED=true

echo "Running Terraform with AWS metadata API disabled..."
echo "Current directory: $(pwd)"

# Run Terraform
terraform destroy
