# Output the repository URL
output "repository_url" {
  value = aws_ecr_repository.my_ecr_repo.repository_url
}