# Application Installation Flags
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

# EKS Configuration
variable "use_eks" {
  type        = bool
  default     = false
  description = "Whether to deploy on EKS (true) or Minikube (false)"
}

variable "eks_cluster_name" {
  type        = string
  default     = "mlops-cluster"
  description = "Name of the EKS cluster"
}

variable "eks_cluster_version" {
  type        = string
  default     = "1.29"
  description = "Kubernetes version for the EKS cluster"
}

variable "eks_instance_types" {
  type        = list(string)
default     = ["t3.medium"]
  description = "EC2 instance types for EKS node groups"
}

variable "eks_node_group_min_size" {
  type        = number
  default     = 2
  description = "Minimum number of nodes in the EKS node group"
}

variable "eks_node_group_max_size" {
  type        = number
  default     = 5
  description = "Maximum number of nodes in the EKS node group"
}

variable "eks_node_group_desired_size" {
  type        = number
  default     = 3
  description = "Desired number of nodes in the EKS node group"
}
