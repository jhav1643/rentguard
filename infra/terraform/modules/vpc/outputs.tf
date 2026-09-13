output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID."
}

output "vpc_cidr_block" {
  value       = aws_vpc.this.cidr_block
  description = "CIDR block assigned to the VPC."
}

output "vpc_arn" {
  value       = aws_vpc.this.arn
  description = "VPC ARN."
}

output "internet_gateway_id" {
  value       = aws_internet_gateway.this.id
  description = "Internet gateway ID."
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "Public subnet IDs, in the order the CIDRs were provided."
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "Private subnet IDs, in the order the CIDRs were provided."
}

output "public_route_table_id" {
  value       = aws_route_table.public.id
  description = "Public route table ID."
}

output "private_route_table_ids" {
  value       = aws_route_table.private[*].id
  description = "Private route table IDs."
}

output "nat_gateway_ids" {
  value       = aws_nat_gateway.this[*].id
  description = "NAT gateway IDs. Empty when enable_nat_gateway is false."
}

output "nat_gateway_public_ips" {
  value       = aws_eip.nat[*].public_ip
  description = "Elastic IPs associated with NAT gateways. Empty when enable_nat_gateway is false."
}