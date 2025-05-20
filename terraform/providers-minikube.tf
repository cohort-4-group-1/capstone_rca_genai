# Mock AWS provider for local Minikube development
provider "aws" {
  region                      = "us-east-1"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  s3_use_path_style           = true
  
  # Add a fake endpoint that will never be called
  endpoints {
    ec2 = "http://localhost:1"
    eks = "http://localhost:1"
    iam = "http://localhost:1"
    s3  = "http://localhost:1"
  }
  
  # Dummy credentials that won't be used
  access_key = "mock_access_key"
  secret_key = "mock_secret_key"
}
