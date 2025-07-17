# Terraform configuration and required providers
terraform {
  backend "s3" {
    bucket  = "rca-tfstate-dev" 
    key     = "terraform.tfstate"     
    region  = "us-east-1"  
    encrypt = true
  }
 
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

# AWS Provider configuration
provider "aws" {
  region = var.aws_region
   
  # Enhanced timeout and retry configurations to prevent context deadline exceeded errors
  default_tags {
    tags = {
      Environment = "dev"
      Project     = var.project_name
      ManagedBy   = "terraform"
    }
  }
   
  # Robust retry configuration for API calls to handle timeouts
  retry_mode                      = "adaptive"
  max_retries                     = 30
  
  # Additional configurations for better reliability during destroy
  skip_credentials_validation     = false
  skip_region_validation         = false
  skip_requesting_account_id     = false
  
  # Ignore certain tags that might cause conflicts during destroy
  ignore_tags {
    keys = ["kubernetes.io/cluster/*"]
  }
}

# Kubernetes Provider configuration
provider "kubernetes" {
  host                   = aws_eks_cluster.main.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.main.certificate_authority[0].data)
 
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", aws_eks_cluster.main.name]
  }
}

# Helm Provider configuration  
provider "helm" {
  kubernetes = {
    host                   = aws_eks_cluster.main.endpoint
    cluster_ca_certificate = base64decode(aws_eks_cluster.main.certificate_authority[0].data)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", aws_eks_cluster.main.name]
    }
  }
}
