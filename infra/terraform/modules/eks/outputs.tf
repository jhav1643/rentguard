output "cluster_id" {
  value       = aws_eks_cluster.this.id
  description = "EKS cluster ID (same as the cluster name in current AWS API)."
}

output "cluster_name" {
  value       = aws_eks_cluster.this.name
  description = "EKS cluster name."
}

output "cluster_arn" {
  value       = aws_eks_cluster.this.arn
  description = "EKS cluster ARN."
}

output "cluster_endpoint" {
  value       = aws_eks_cluster.this.endpoint
  description = "EKS API server endpoint. Against Floci this points at the local control plane."
}

output "cluster_certificate_authority_data" {
  value       = aws_eks_cluster.this.certificate_authority[0].data
  description = "Base64-encoded certificate authority data for the cluster."
  sensitive   = true
}

output "cluster_version" {
  value       = aws_eks_cluster.this.version
  description = "Kubernetes version reported by the control plane."
}

output "node_group_id" {
  value       = aws_eks_node_group.this.id
  description = "Managed node group ID."
}

output "node_group_arn" {
  value       = aws_eks_node_group.this.arn
  description = "Managed node group ARN."
}

output "node_group_status" {
  value       = aws_eks_node_group.this.status
  description = "Managed node group status (e.g. ACTIVE)."
}