variable "name" {
  type        = string
  description = "Name prefix for IAM roles created by this module."
}

variable "cluster_role_name" {
  type        = string
  default     = null
  description = <<-EOT
    Override for the EKS control-plane role name. Defaults to
    "<name>-eks-cluster" when null.
  EOT
}

variable "node_role_name" {
  type        = string
  default     = null
  description = <<-EOT
    Override for the EKS node-group role name. Defaults to
    "<name>-eks-node" when null.
  EOT
}

variable "cluster_policy_arns" {
  type = list(string)
  default = [
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController",
  ]
  description = <<-EOT
    Managed policy ARNs attached to the EKS control-plane role.
    Override only if you know why you're removing the defaults.
  EOT
}

variable "node_policy_arns" {
  type = list(string)
  default = [
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
  ]
  description = <<-EOT
    Managed policy ARNs attached to the EKS node-group role.
    Override only if you know why you're removing the defaults.
  EOT
}

variable "permissions_boundary_arn" {
  type        = string
  default     = null
  description = "Optional permissions boundary applied to every role created by this module."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to all IAM resources."
}