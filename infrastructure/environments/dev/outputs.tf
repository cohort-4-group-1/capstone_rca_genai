# Output the repository URL
output "ecr_repository_urls" {
  value = {
    my_ecr_repo       = aws_ecr_repository.my_ecr_repo.repository_url
    gradio_ecr_repo   = aws_ecr_repository.gradio_ecr_repo.repository_url
    trigger_ecr_repo  = aws_ecr_repository.trigger_ecr_repo.repository_url
  }
}

# Output node group IDs and volume sizes
output "node_group_ids" {
  value = {
    eks_node_group_id = aws_eks_node_group.default.id
    eks_volume_size   = aws_eks_node_group.default.disk_size
  }
}

# Output the EKS cluster name
output "eks_cluster_name" {
  value = aws_eks_cluster.main.name
}

# Output the VPC ID
output "vpc_id" {
  value = aws_vpc.main.id
}

