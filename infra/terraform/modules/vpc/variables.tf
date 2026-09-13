variable "name" {
  type        = string
  description = "Name prefix applied to every resource created by this module."
}

variable "cidr_block" {
  type        = string
  default     = "10.0.0.0/16"
  description = "CIDR block for the VPC."
}

variable "azs" {
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
  description = <<-EOT
    Availability zones used by public and private subnets. The number
    of AZs does not need to match the number of subnets; subnets cycle
    through this list.
  EOT
}

variable "public_subnet_cidrs" {
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
  description = "CIDR blocks for public subnets. Set to [] to create none."
}

variable "private_subnet_cidrs" {
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
  description = "CIDR blocks for private subnets. Set to [] to create none."
}

variable "enable_dns_support" {
  type        = bool
  default     = true
  description = "Enable DNS resolution in the VPC. Required by EKS."
}

variable "enable_dns_hostnames" {
  type        = bool
  default     = true
  description = "Assign DNS hostnames to instances. Required by EKS."
}

variable "map_public_ip_on_launch" {
  type        = bool
  default     = true
  description = "Auto-assign public IPs to instances in public subnets."
}

variable "enable_nat_gateway" {
  type        = bool
  default     = false
  description = <<-EOT
    Create NAT gateway(s) so private subnets have outbound internet.
    Off by default: a single NAT gateway costs ~$32/month plus data
    processing on real AWS. Turn on only when something actually lives
    in the private subnets. Ignored by Floci.
  EOT
}

variable "single_nat_gateway" {
  type        = bool
  default     = true
  description = <<-EOT
    When enable_nat_gateway is true, use one NAT gateway shared across
    all private subnets instead of one per subnet. Saves money at the
    cost of an AZ failure taking down egress. Ignored when
    enable_nat_gateway is false.
  EOT
}

variable "enable_flow_logs" {
  type        = bool
  default     = false
  description = <<-EOT
    Enable VPC flow logs to CloudWatch Logs. Off by default; ingestion
    and storage cost money on real AWS and Floci does not emulate them.
  EOT
}

variable "flow_logs_retention_days" {
  type        = number
  default     = 7
  description = "CloudWatch Logs retention for flow logs, when enabled."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to all resources."
}