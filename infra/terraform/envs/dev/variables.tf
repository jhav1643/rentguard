variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Region passed to the AWS provider. Floci ignores it for most services but the provider requires a value."
}

variable "deploy_eks" {
  type        = bool
  default     = true
  description = <<-EOT
    Deploy EKS in the local Floci environment. Requires Floci running
    with rootful Docker (k3s needs kernel-level access). Set false to
    iterate on VPC/IAM/S3 only, e.g. when Docker is unavailable.
  EOT
}

variable "bucket_name" {
  type        = string
  default     = "rentguard-dev-artifacts"
  description = "S3 bucket name in Floci. Uniqueness rules are not enforced locally, so a fixed name is fine."
}

variable "cluster_name" {
  type        = string
  default     = "rentguard-dev-eks"
  description = "EKS cluster name in Floci."
}