# S3 module -- one bucket with encryption, versioning, public-access
# block, and an optional lifecycle rule for noncurrent versions.
#
# Scope is intentionally narrow. Deliberately NOT here:
#
#   - Bucket policies. Every policy is environment-specific; a generic
#     module default would either be too permissive or too restrictive
#     to be useful. Attach policies from the env or a dedicated module.
#
#   - Cross-region replication, inventory, access logging, event
#     notifications. All require a second bucket or external target,
#     which the module cannot guess. Add as needed.
#
#   - Object uploads. Terraform is a poor fit for managing object
#     contents; use the AWS CLI, CI, or a dedicated pipeline.
#
# Floci note: versioning, SSE configuration, and public-access block
# are accepted by Floci's S3 emulation. Encryption is metadata-only --
# objects are stored unencrypted locally.

resource "aws_s3_bucket" "this" {
  bucket        = var.bucket_name
  force_destroy = var.force_destroy

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = var.versioning_enabled ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.sse_algorithm
      kms_master_key_id = var.sse_algorithm == "aws:kms" ? var.kms_master_key_arn : null
    }

    bucket_key_enabled = var.sse_algorithm == "aws:kms" ? var.bucket_key_enabled : null
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  count = var.block_public_access ? 1 : 0

  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  count = var.lifecycle_expiration_days != null || var.noncurrent_version_expiration_days != null ? 1 : 0

  bucket = aws_s3_bucket.this.id

  # Required when versioning is enabled so the rules apply predictably.
  # Harmless when versioning is off.
  dynamic "rule" {
    for_each = var.lifecycle_expiration_days != null ? [1] : []

    content {
      id     = "expire-current-objects"
      status = "Enabled"

      filter {}

      expiration {
        days = var.lifecycle_expiration_days
      }
    }
  }

  dynamic "rule" {
    for_each = var.noncurrent_version_expiration_days != null ? [1] : []

    content {
      id     = "expire-noncurrent-versions"
      status = "Enabled"

      filter {}

      noncurrent_version_expiration {
        noncurrent_days = var.noncurrent_version_expiration_days
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}