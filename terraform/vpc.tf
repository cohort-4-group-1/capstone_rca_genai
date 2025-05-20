
# Only create VPC when use_eks is true
locals {
  create_vpc = var.use_eks
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  count   = local.create_vpc ? 1 : 0

  name = "${var.project_name}-${var.environment}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = true
  one_nat_gateway_per_az = false
  enable_dns_hostnames   = true
  enable_dns_support     = true

  # EKS required tags
  public_subnet_tags = {
    "kubernetes.io/cluster/${var.eks_cluster_name}" = "shared"
    "kubernetes.io/role/elb"                        = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/cluster/${var.eks_cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"               = "1"
  }

  tags = {
    Environment = var.environment
    Project     = var.project_name
    Terraform   = "true"
  }
}

# Output VPC information
output "vpc_id" {
  description = "The ID of the VPC"
  value       = local.create_vpc ? module.vpc[0].vpc_id : null
}

output "vpc_private_subnets" {
  description = "List of IDs of private subnets"
  value       = local.create_vpc ? module.vpc[0].private_subnets : null
}

output "vpc_public_subnets" {
  description = "List of IDs of public subnets"
  value       = local.create_vpc ? module.vpc[0].public_subnets : null
}
