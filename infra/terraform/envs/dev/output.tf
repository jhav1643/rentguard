output "vpc_id" {
  value       = module.vpc.vpc_id
  description = "VPC ID in Floci."
}

output "public_subnet_ids" {
  value       = module.vpc.public_subnet_ids
  description = "Public subnet IDs."
}

output "private_subnet_ids" {
  value       = module.vpc.private_subnet_ids
  description = "Private subnet IDs."
}

output "bucket_name" {
  value       = module.s3.bucket_id
  description = "S3 bucket name in Floci."
}

output "bucket_arn" {
  value       = module.s3.bucket_arn
  description = "S3 bucket ARN in Floci."
}

output "eks_cluster_name" {
  value       = var.deploy_eks ? module.eks[0].cluster_name : "EKS not deployed (deploy_eks=false)"
  description = "EKS cluster name, or a marker string when EKS is gated off."
}

output "eks_cluster_endpoint" {
  value       = var.deploy_eks ? module.eks[0].cluster_endpoint : "EKS not deployed (deploy_eks=false)"
  description = "EKS API server endpoint, or a marker string when EKS is gated off."
}

output "iam_eks_cluster_role_arn" {
  value       = module.iam.eks_cluster_role_arn
  description = "IAM role ARN for the EKS control plane."
}

output "iam_eks_node_role_arn" {
  value       = module.iam.eks_node_role_arn
  description = "IAM role ARN for the EKS managed node group."
}