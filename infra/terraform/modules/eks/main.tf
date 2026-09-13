# EKS module -- control plane + one managed node group.
#
# Deliberately minimal so the same module works against both real AWS
# and Floci. Things that are NOT here on purpose:
#
#   - IRSA / OIDC provider (next step; see modules/iam/main.tf)
#   - Managed add-ons (vpc-cni, coredns, kube-proxy) -- EKS installs
#     sensible defaults, and Floci does not emulate add-on lifecycle
#   - Fargate profiles, launch templates, multiple node groups
#
# Floci note: Floci's EKS emulation is backed by a real k3s node and
# accepts the standard CreateCluster / CreateNodegroup API surface.
# Some fields (endpoint_*_access, enabled_cluster_log_types,
# capacity_type = SPOT) are accepted but not acted on.

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  role_arn = var.cluster_role_arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = var.endpoint_private_access
    endpoint_public_access  = var.endpoint_public_access
  }

  enabled_cluster_log_types = var.cluster_enabled_log_types

  tags = var.tags

  # EKS will not create the control plane until the cluster role can be
  # assumed. The role is created in module.iam; the env files already
  # express depends_on at the module-call level.
  lifecycle {
    ignore_changes = [
      # Prevent Terraform from fighting EKS over control-plane log
      # types that may be toggled out-of-band. Drop this if you want
      # Terraform to own them strictly.
      enabled_cluster_log_types,
    ]
  }
}

resource "aws_eks_node_group" "this" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-ng"
  node_role_arn   = var.node_role_arn

  subnet_ids = var.node_subnet_ids != null ? var.node_subnet_ids : var.subnet_ids

  scaling_config {
    desired_size = var.desired_size
    min_size     = var.min_size
    max_size     = var.max_size
  }

  instance_types = var.instance_types
  capacity_type  = var.capacity_type
  disk_size      = var.disk_size

  labels = var.node_labels

  tags = var.tags

  depends_on = [aws_eks_cluster.this]

  lifecycle {
    # Cluster Autoscaler (or any external scaler) can change desired_size
    # at runtime. Without this, every subsequent `terraform plan` tries
    # to reset it back to var.desired_size.
    #
    # If you want Terraform to own the replica count strictly, remove
    # this block.
    ignore_changes = [scaling_config[0].desired_size]
  }
}