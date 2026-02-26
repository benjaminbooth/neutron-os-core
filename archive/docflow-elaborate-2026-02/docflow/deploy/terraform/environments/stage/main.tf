# DocFlow Stage Environment
# Terraform configuration for AWS staging infrastructure

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Remote state in S3
  # Uncomment and configure for your environment
  # backend "s3" {
  #   bucket         = "docflow-terraform-state"
  #   key            = "stage/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "docflow-terraform-locks"
  #   encrypt        = true
  # }
}

# =============================================================================
# Providers
# =============================================================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "stage"
      Project     = "docflow"
      ManagedBy   = "terraform"
    }
  }
}

# Kubernetes provider - configured after EKS is created
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

# Helm provider
provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "stage"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "docflow_version" {
  description = "DocFlow Helm chart version"
  type        = string
  default     = "0.1.0"
}

# =============================================================================
# Locals
# =============================================================================

locals {
  name = "docflow-${var.environment}"
  azs  = ["${var.aws_region}a", "${var.aws_region}b"]

  tags = {
    Environment = var.environment
    Project     = "docflow"
    ManagedBy   = "terraform"
  }
}

# =============================================================================
# VPC
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = var.vpc_cidr

  azs              = local.azs
  private_subnets  = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets   = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 4, i + length(local.azs))]
  database_subnets = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 4, i + 2 * length(local.azs))]

  create_database_subnet_group = true

  enable_nat_gateway   = true
  single_nat_gateway   = true # Cost saving for stage
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Tags for EKS
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }

  tags = local.tags
}

# =============================================================================
# EKS Cluster
# =============================================================================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = local.name
  cluster_version = "1.28"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  # Addons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # Managed node group
  eks_managed_node_groups = {
    general = {
      name = "${local.name}-general"

      instance_types = ["t3.medium"]
      capacity_type  = "SPOT" # Cost saving for stage

      min_size     = 1
      max_size     = 3
      desired_size = 2

      labels = {
        workload = "general"
      }
    }
  }

  # Enable IRSA
  enable_irsa = true

  tags = local.tags
}

# EBS CSI Driver IRSA
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }

  tags = local.tags
}

# =============================================================================
# RDS PostgreSQL with pgvector
# =============================================================================

# Security group for RDS
resource "aws_security_group" "rds" {
  name_prefix = "${local.name}-rds-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }

  tags = local.tags
}

# Random password for RDS
resource "random_password" "rds" {
  length  = 32
  special = false
}

# RDS instance
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = local.name

  engine               = "postgres"
  engine_version       = "15.4"
  family               = "postgres15"
  major_engine_version = "15"
  instance_class       = "db.t3.medium"

  allocated_storage     = 20
  max_allocated_storage = 50

  db_name  = "docflow"
  username = "docflow"
  password = random_password.rds.result
  port     = 5432

  # Single AZ for stage
  multi_az = false

  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Backups
  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # Encryption
  storage_encrypted = true

  # Allow deletion for stage
  deletion_protection = false
  skip_final_snapshot = true

  tags = local.tags
}

# Store RDS credentials in Secrets Manager
resource "aws_secretsmanager_secret" "rds" {
  name = "${local.name}/rds-credentials"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "rds" {
  secret_id = aws_secretsmanager_secret.rds.id
  secret_string = jsonencode({
    username = module.rds.db_instance_username
    password = random_password.rds.result
    host     = module.rds.db_instance_address
    port     = module.rds.db_instance_port
    database = "docflow"
    url      = "postgresql://${module.rds.db_instance_username}:${random_password.rds.result}@${module.rds.db_instance_address}:${module.rds.db_instance_port}/docflow"
  })
}

# =============================================================================
# ElastiCache Redis
# =============================================================================

resource "aws_security_group" "redis" {
  name_prefix = "${local.name}-redis-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }

  tags = local.tags
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = local.name
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = local.name
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  tags = local.tags
}

# =============================================================================
# Kubernetes Resources
# =============================================================================

# Namespace
resource "kubernetes_namespace" "docflow" {
  metadata {
    name = "docflow"
    labels = {
      name = "docflow"
    }
  }

  depends_on = [module.eks]
}

# External Secrets for RDS credentials
resource "kubernetes_secret" "db_credentials" {
  metadata {
    name      = "docflow-db-credentials"
    namespace = kubernetes_namespace.docflow.metadata[0].name
  }

  data = {
    url      = "postgresql://${module.rds.db_instance_username}:${random_password.rds.result}@${module.rds.db_instance_address}:${module.rds.db_instance_port}/docflow"
    host     = module.rds.db_instance_address
    port     = tostring(module.rds.db_instance_port)
    username = module.rds.db_instance_username
    password = random_password.rds.result
    database = "docflow"
  }

  depends_on = [module.rds]
}

# =============================================================================
# Helm Release
# =============================================================================

resource "helm_release" "docflow" {
  name       = "docflow"
  namespace  = kubernetes_namespace.docflow.metadata[0].name
  repository = "https://gitlab.example.com/api/v4/projects/123/packages/helm/stable"
  chart      = "docflow"
  version    = var.docflow_version

  values = [
    templatefile("${path.module}/values.yaml", {
      environment    = var.environment
      redis_endpoint = aws_elasticache_cluster.redis.cache_nodes[0].address
    })
  ]

  set {
    name  = "database.external.existingSecret"
    value = kubernetes_secret.db_credentials.metadata[0].name
  }

  depends_on = [
    module.eks,
    module.rds,
    aws_elasticache_cluster.redis,
    kubernetes_secret.db_credentials,
  ]
}

# =============================================================================
# Outputs
# =============================================================================

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.db_instance_endpoint
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}
