output "eks_cluster_role_name" {
  value       = aws_iam_role.eks_cluster.name
  description = "Name of the EKS control-plane IAM role."
}

output "eks_cluster_role_arn" {
  value       = aws_iam_role.eks_cluster.arn
  description = "ARN of the EKS control-plane IAM role. Consumed by modules/eks."
}

output "eks_node_role_name" {
  value       = aws_iam_role.eks_node.name
  description = "Name of the EKS node-group IAM role."
}

output "eks_node_role_arn" {
  value       = aws_iam_role.eks_node.arn
  description = "ARN of the EKS node-group IAM role. Consumed by modules/eks."
}