
# Only create EKS storage classes when use_eks is true
locals {
  create_storage_classes = var.use_eks
}

# Define a Kubernetes Storage Class for EBS
resource "kubernetes_storage_class" "ebs_gp2" {
  count = local.create_storage_classes ? 1 : 0

  metadata {
    name = "ebs-gp2"
    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }

  storage_provisioner = "kubernetes.io/aws-ebs"
  reclaim_policy      = "Delete"
  volume_binding_mode = "WaitForFirstConsumer"
  parameters = {
    type      = "gp2"
    fsType    = "ext4"
    encrypted = "true"
  }
}

# Define a Storage Class for high performance workloads (io1 EBS)
resource "kubernetes_storage_class" "ebs_io1" {
  count = local.create_storage_classes ? 1 : 0

  metadata {
    name = "ebs-io1"
  }

  storage_provisioner = "kubernetes.io/aws-ebs"
  reclaim_policy      = "Delete"
  volume_binding_mode = "WaitForFirstConsumer"
  parameters = {
    type       = "io1"
    iopsPerGB  = "50"
    fsType     = "ext4"
    encrypted  = "true"
  }
}
