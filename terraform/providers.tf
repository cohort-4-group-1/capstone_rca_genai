
# Terraform requires AWS provider configuration, so we set it up with
# dummy values when not using EKS. This avoids credential errors.

# The actual AWS provider is now in providers-minikube.tf for local development
# and this file is only used for EKS deployments when use_eks = true

# Helm provider with conditional config
provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
    
    # Only use EKS connection parameters when use_eks = true
    dynamic "exec" {
      for_each = var.use_eks ? [1] : []
      content {
        api_version = "client.authentication.k8s.io/v1beta1"
        command     = "aws"
        args        = ["eks", "get-token", "--cluster-name", module.eks[0].cluster_id]
      }
    }

    host                   = var.use_eks ? module.eks[0].cluster_endpoint : null
    cluster_ca_certificate = var.use_eks ? base64decode(module.eks[0].cluster_certificate_authority_data) : null
  }
}

# Kubernetes provider with conditional config
provider "kubernetes" {
  config_path = "~/.kube/config"

  # Only use EKS connection parameters when use_eks = true
  dynamic "exec" {
    for_each = var.use_eks ? [1] : []
    content {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks[0].cluster_id]
    }
  }

  host                   = var.use_eks ? module.eks[0].cluster_endpoint : null
  cluster_ca_certificate = var.use_eks ? base64decode(module.eks[0].cluster_certificate_authority_data) : null
}