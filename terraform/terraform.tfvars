// Application Installation Configuration
install_airflow    = false
install_prometheus = false
install_grafana    = false
install_dask       = false
install_mlflow     = true # this would be installed
install_clearml    = false # this would not be installed

// Platform Selection
use_eks            = false  // Set to true for EKS, false for Minikube

// AWS/EKS Configuration
aws_region         = "us-east-1"
eks_cluster_name   = "mlops-platform"
eks_cluster_version = "1.29"
eks_instance_types = ["t3.medium"]
eks_node_group_min_size = 2
eks_node_group_max_size = 5
eks_node_group_desired_size = 3