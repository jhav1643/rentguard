variable "bucket_name" {
  type        = string
  description = <<-EOT
    S3 bucket name. On real AWS this must be globally unique and
    DNS-compliant (lowercase, 3-63 chars, no underscores). Floci does
    not enforce uniqueness, so any stable string works locally.
  EOT
}

variable "versioning_enabled" {
  type        = bool
  default     = true
  description = "Enable S3 bucket versioning."
}

variable "force_destroy" {
  type        = bool
  default     = false
  description = <<-EOT
    Allow Terraform to destroy a non-empty bucket. Set true in dev and
    demo so `terraform destroy` does not fail on leftover objects. Keep
    false for anything resembling production.
  EOT
}

variable "sse_algorithm" {
  type        = string
  default     = "AES256"
  description = <<-EOT
    Server-side encryption algorithm. AES256 (SSE-S3) by default.
    Use "aws:kms" plus kms_master_key_arn for SSE-KMS on real AWS.
    Floci accepts the setting but does not actually encrypt.
  EOT
}

variable "kms_master_key_arn" {
  type        = string
  default     = null
  description = "KMS key ARN. Only used when sse_algorithm is \"aws:kms\". Ignored by Floci."
}

variable "bucket_key_enabled" {
  type        = bool
  default     = true
  description = "Enable S3 Bucket Keys to reduce KMS request cost. Only relevant for SSE-KMS."
}

variable "block_public_access" {
  type        = bool
  default     = true
  description = "Apply the standard public-access block. Leave true unless you have a specific reason not to."
}

variable "lifecycle_expiration_days" {
  type        = number
  default     = null
  description = <<-EOT
    If set, objects expire after this many days. Null disables the
    lifecycle rule entirely. Useful in dev to keep storage bounded.
  EOT
}

variable "noncurrent_version_expiration_days" {
  type        = number
  default     = 30
  description = "Days to retain noncurrent object versions when versioning is enabled. Null disables the rule."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to all resources."
}