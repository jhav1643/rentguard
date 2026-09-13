# IAM module -- EKS control-plane role + EKS node-group role.
#
# Scope is intentionally narrow. This module creates exactly the two
# roles that the EKS module needs, plus their policy attachments.
#
# Deliberately NOT implemented yet (a legitimate next step, not an
# oversight):
#
#   - IRSA / OIDC. A proper IRSA setup requires an OIDC provider for
#     the cluster, one IAM role per Kubernetes service account, and a
#     trust policy that binds the role to a specific
#     system:serviceaccount:<namespace>:<name>. That has to be
#     created *after* the cluster exists, so it usually lives in a
#     separate module applied in a second pass, or in the same module
#     with an explicit depends_on aws_eks_cluster.
#
#   - Inline policies. All policies here are AWS-managed. If you need
#     scoped-down permissions, add an aws_iam_policy + attachment.
#
#   - Users, groups, access keys. None of that belongs in this module;
#     it would drift the moment a human onboards.

locals {
  cluster_role_name = coalesce(var.cluster_role_name, "${var.name}-eks-cluster")
  node_role_name    = coalesce(var.node_role_name, "${var.name}-eks-node")
}

# ---------------------------------------------------------------------------
# EKS control-plane role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "eks_cluster_assume_role" {
  statement {
    sid     = "EKSClusterAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_cluster" {
  name                 = local.cluster_role_name
  assume_role_policy   = data.aws_iam_policy_document.eks_cluster_assume_role.json
  permissions_boundary = var.permissions_boundary_arn

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "eks_cluster" {
  count = length(var.cluster_policy_arns)

  role       = aws_iam_role.eks_cluster.name
  policy_arn = var.cluster_policy_arns[count.index]
}

# ---------------------------------------------------------------------------
# EKS node-group role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "eks_node_assume_role" {
  statement {
    sid     = "EKSNodeAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_node" {
  name                 = local.node_role_name
  assume_role_policy   = data.aws_iam_policy_document.eks_node_assume_role.json
  permissions_boundary = var.permissions_boundary_arn

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "eks_node" {
  count = length(var.node_policy_arns)

  role       = aws_iam_role.eks_node.name
  policy_arn = var.node_policy_arns[count.index]
}