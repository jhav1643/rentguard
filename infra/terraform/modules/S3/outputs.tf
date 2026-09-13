output "bucket_id" {
  value       = aws_s3_bucket.this.id
  description = "Bucket ID. For S3 this is the same value as the bucket name."
}

output "bucket_name" {
  value       = aws_s3_bucket.this.bucket
  description = <<-EOT
    Bucket name as configured. Identical to bucket_id in practice;
    provided separately so downstream config that reads
    `module.s3.bucket_name` works without a wrapper.
  EOT
}

output "bucket_arn" {
  value       = aws_s3_bucket.this.arn
  description = "Bucket ARN. Useful for attaching IAM policies outside this module."
}

output "bucket_regional_domain_name" {
  value       = aws_s3_bucket.this.bucket_regional_domain_name
  description = "Regional domain name of the bucket."
}