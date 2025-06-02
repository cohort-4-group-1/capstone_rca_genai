#-------------------------------------------------------------
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix used for naming resources"
  type        = string
  default = "iisc-capstone-rca"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.192.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "List of CIDR blocks for public subnets"
  type        = list(string)
  default     = [
    "10.192.0.0/20",    # us-east-1a
    "10.192.16.0/20",   # us-east-1b
    "10.192.32.0/20"    # us-east-1c
  ]
}

variable "private_subnet_cidrs" {
  description = "List of CIDR blocks for private subnets"
  type        = list(string)
  default     = [
    "10.192.128.0/20",  # us-east-1a
    "10.192.144.0/20",  # us-east-1b
    "10.192.160.0/20"   # us-east-1c
  ]
}

variable "azs" {
  description = "List of availability zones in the region"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default = "iisc-capstone-rca"
}
variable "tfstate_bucket" {
  description = "Name of the project"
  type        = string
  default = "iisc_capstone_rca_tfstate"
}

<<<<<<< HEAD

variable "use_eks" {
  description = "EKS will be used or not"
  type        = bool
  default = "true"
}

variable "install_airflow" {
  description = "EKS will be used or not"
  type        = bool
  default = false
}

variable "install_prometheus" {
  description = "EKS will be used or not"
  type        = bool
  default = false
}

variable "install_grafana" {
  description = "EKS will be used or not"
  type        = bool
  default = false
}

variable "install_dask" {
  description = "EKS will be used or not"
  type        = bool
  default = false
}

variable "install_mlflow" {
  description = "EKS will be used or not"
  type        = bool
  default = true
}

variable "install_clearml" {
  description = "EKS will be used or not"
  type        = bool
  default = true
}


=======
#--------------------------------------------------------------
# Application Installation Flags
#--------------------------------------------------------------
variable "install_airflow" {
  type        = bool
  default     = true
  description = "Whether to install Apache Airflow"
}

variable "install_clearml" {
  type        = bool
  default     = true
  description = "Whether to install ClearML"
}

variable "install_prometheus" {
  type        = bool
  default     = true
  description = "Whether to install Prometheus"
}

variable "install_grafana" {
  type        = bool
  default     = true
  description = "Whether to install Grafana"
}

variable "install_dask" {
  type        = bool
  default     = true
  description = "Whether to install Dask"
}

variable "install_mlflow" {
  type        = bool
  default     = true
  description = "Whether to install MLflow"
}

variable "install_postgres" {
  description = "Whether to install PostgreSQL"
  type        = bool
  default     = true
}
>>>>>>> 46bffdcd71f246d7763aa343612daf0b5495813c
