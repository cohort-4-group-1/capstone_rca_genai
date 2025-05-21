# Only create EKS resources when use_eks is true
locals {
  create_eks = var.use_eks
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"
  count   = local.create_eks ? 1 : 0

  cluster_name    = var.eks_cluster_name
  cluster_version = var.eks_cluster_version

  cluster_endpoint_public_access = false

  vpc_id     = module.vpc[0].vpc_id
  subnet_ids = module.vpc[0].private_subnets

  # EKS Managed Node Group(s)
  eks_managed_node_group_defaults = {
    instance_types = var.eks_instance_types
    disk_size      = 100
  }

  eks_managed_node_groups = {
    mlops_nodes = {
      min_size     = var.eks_node_group_min_size
      max_size     = var.eks_node_group_max_size
      desired_size = var.eks_node_group_desired_size

      instance_types = var.eks_instance_types
      capacity_type  = "ON_DEMAND"

      # Properly space out upgrades of nodes
      update_config = {
        max_unavailable_percentage = 25
      }

      # Labels and taints
      labels = {
        role = "mlops-workload"
      }
    }
  }

  # Create IAM role for service accounts (IRSA)
  enable_irsa = true

  # Add tags for Kubernetes auto-discovery
  tags = {
    Environment = var.environment
    Project     = var.project_name
    Terraform   = "true"
  }
}

# Update the kubeconfig for EKS
resource "null_resource" "update_kubeconfig" {
  count      = local.create_eks ? 1 : 0
  depends_on = [module.eks]

  provisioner "local-exec" {
    command = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks[0].cluster_id}"
  }
}

# Output EKS cluster information
output "eks_cluster_id" {
  description = "EKS cluster ID"
  value       = local.create_eks ? module.eks[0].cluster_id : null
}

output "eks_cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = local.create_eks ? module.eks[0].cluster_endpoint : null
}

output "eks_cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = local.create_eks ? module.eks[0].cluster_certificate_authority_data : null
  sensitive   = true
}
