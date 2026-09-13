locals {
  name = "rentguard-dev"

  tags = {
    Environment = "dev"
    ManagedBy   = "terraform"
    Project     = "rentguard"
  }
}

module "vpc" {
  source = "../../modules/vpc"

  name                 = local.name
  cidr_block           = "10.0.0.0/16"
  azs                  = ["us-east-1a", "us-east-1b"]
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24"]

  # Floci does not simulate NAT or real subnet routing, so there is
  # no reason to create a NAT gateway here.
  enable_nat_gateway = false

  tags = local.tags
}

module "iam" {
  source = "../../modules/iam"

  name = local.name

  tags = local.tags
}

module "s3" {
  source = "../../modules/s3"

  bucket_name        = var.bucket_name
  versioning_enabled = true
  force_destroy      = true # dev bucket -- safe to destroy even if non-empty

  tags = local.tags
}

module "eks" {
  count = var.deploy_eks ? 1 : 0

  source = "../../modules/eks"

  cluster_name       = var.cluster_name
  kubernetes_version = "1.29"

  cluster_role_arn = module.iam.eks_cluster_role_arn
  node_role_arn    = module.iam.eks_node_role_arn

  # Public subnets only. Floci does not emulate private-subnet egress,
  # so this is correct here (unlike demo, where private subnets are used).
  subnet_ids = module.vpc.public_subnet_ids

  desired_size   = 1
  min_size       = 1
  max_size       = 2
  instance_types = ["t3.medium"]

  tags = local.tags

  depends_on = [module.iam, module.vpc]
}