terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.2.0"

  backend "s3" {
    # These values are configured via backend-config in GitHub Actions
    # bucket = "your-terraform-state-bucket"
    # key    = "terraform.tfstate"
    # region = "us-east-1"
    # dynamodb_table = "terraform-lock" # Optional for state locking
  }
}

provider "aws" {
  region = var.aws_region
  
  # Optional configuration
  # default_tags {
  #   tags = {
  #     Environment = var.environment
  #     Project     = var.project_name
  #     ManagedBy   = "Terraform"
  #   }
  # }
}

# Variables
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "rca-with-llm"
  type        = string
  default     = "terraform-aws-example"
}

# Example resource
resource "aws_s3_bucket" "example" {
  bucket = "${var.project_name}-${var.environment}-bucket"

  tags = {
    Name        = "${var.project_name}-bucket"
    Environment = var.environment
  }
}

# Output values
output "bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.example.bucket
}