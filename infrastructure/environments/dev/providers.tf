
# Terraform requires AWS provider configuration, so we set it up with
# dummy values when not using EKS. This avoids credential errors.

# The actual AWS provider is now in providers-minikube.tf for local development
# and this file is only used for EKS deployments when use_eks = true

# Helm provider with conditional config
provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}
 