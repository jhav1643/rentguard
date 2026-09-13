variable "cluster_name" {
    type = string
    description = "The name of the EKS cluster."
}

variable "kubernetes_version" {
    type = string
    default = "1.29"
     description = <<-EOT
    Kubernetes version for the EKS cluster.
    Pick a version still in standard support -- extended-support versions
    add ~$0.60/hr per cluster on real AWS.
  EOT
}

variable "subnet_ids" {
    type = list(string)
    description = "The list of subnet IDs to use for the EKS cluster."
}

variable "cluster_role_arn" {
    type = string
    description = "The ARN of the IAM role to use for the EKS cluster."
}

variable "node_role_arn" {
    type = string
    description = "The ARN of the IAM role to use for the EKS worker nodes."
}

variable "desired_size" {
    type = number
    default = 1
    description = "The desired number of worker nodes in the EKS cluster."
}

variable "min_size" {
    type = number
    default = 1
    description = "The minimum number of worker nodes in the EKS cluster."
}

variable "max_size" {
    type = number
    default = 2
    description = "The maximum number of worker nodes in the EKS cluster."
}

variable "node_subnet_ids" {
    type = list(string)
    default = null
    description = "The list of subnet IDs to use for the EKS worker nodes."
}

variable "instance_types" {
    type        = list(string)
    default     = ["t3.medium"]
    description = "EC2 instance types for the node group."
}

variable "capacity_type" {
    type = string
    default = "ON_DEMAND"
    description = "The capacity type for the EKS worker nodes. Can be ON_DEMAND or SPOT."
}

variable "disk_size" {
    type        = number
    default     = 20
    description = "The disk size (in GiB) for the EKS worker nodes."
}

variable "node_labels" {
    type        = map(string)
    default     = {}
    description = "A map of labels to apply to the EKS worker nodes."
}

variable "cluster_enabled_log_types" {
  type        = list(string)
  default     = []
  description = <<-EOT
    Control-plane log types to send to CloudWatch. Empty by default
    to keep cost near zero. Floci ignores this.
  EOT
}

variable "endpoint_private_access" {
  type        = bool
  default     = true
  description = "Enable the private EKS API endpoint."
}

variable "endpoint_public_access" {
  type        = bool
  default     = true
  description = "Enable the public EKS API endpoint. Floci always exposes a public-style endpoint."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to the cluster and node group."
}
