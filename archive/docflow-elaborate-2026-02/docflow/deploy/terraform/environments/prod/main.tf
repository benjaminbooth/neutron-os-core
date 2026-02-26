# Production Environment for DocFlow
# High availability configuration with Multi-AZ

terraform {
  required_version = ">= 1.5.0"

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

  # Uncomment and configure for remote state
  # backend "s3" {
  #   bucket         = "docflow-terraform-state-ACCOUNT_ID"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "docflow-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "docflow"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "docflow"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

# Get available AZs
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 3)  # 3 AZs for prod
  
  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  name        = var.project_name
  environment = var.environment
  cidr        = "10.1.0.0/16"  # Different CIDR from stage
  azs         = local.azs

  public_subnets   = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
  private_subnets  = ["10.1.11.0/24", "10.1.12.0/24", "10.1.13.0/24"]
  database_subnets = ["10.1.21.0/24", "10.1.22.0/24", "10.1.23.0/24"]

  tags = local.tags
}

# EKS Module
module "eks" {
  source = "../../modules/eks"

  name               = var.project_name
  environment        = var.environment
  kubernetes_version = "1.29"
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids

  node_groups = {
    general = {
      instance_types = ["m6i.large", "m6a.large"]
      capacity_type  = "ON_DEMAND"  # On-demand for production reliability
      min_size       = 3
      max_size       = 10
      desired_size   = 3
      disk_size      = 100
      labels = {
        role = "general"
      }
    }
    compute = {
      instance_types = ["c6i.xlarge", "c6a.xlarge"]
      capacity_type  = "ON_DEMAND"
      min_size       = 0
      max_size       = 5
      desired_size   = 2
      disk_size      = 100
      labels = {
        role = "compute"
      }
    }
  }

  tags = local.tags
}

# RDS Module - Multi-AZ for production
module "rds" {
  source = "../../modules/rds"

  name              = var.project_name
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  subnet_group_name = module.vpc.database_subnet_group_name

  allowed_security_group_ids = [module.eks.node_security_group_id]

  instance_class        = "db.r6g.large"  # Larger instance for prod
  allocated_storage     = 50
  max_allocated_storage = 500
  engine_version        = "15.4"
  database_name         = "docflow"
  database_user         = "docflow"

  multi_az                     = true   # Multi-AZ for HA
  backup_retention_period      = 30     # 30 days backup retention
  deletion_protection          = true   # Prevent accidental deletion
  skip_final_snapshot          = false  # Take final snapshot
  performance_insights_enabled = true   # Enable performance insights

  tags = local.tags
}

# ElastiCache Module - Cluster mode for production
module "elasticache" {
  source = "../../modules/elasticache"

  name              = var.project_name
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  subnet_group_name = module.vpc.elasticache_subnet_group_name

  allowed_security_group_ids = [module.eks.node_security_group_id]

  node_type                  = "cache.r6g.large"  # Larger instance for prod
  num_cache_nodes            = 2                   # 2 nodes for HA
  engine_version             = "7.0"
  automatic_failover_enabled = true               # Enable failover
  multi_az_enabled           = true               # Multi-AZ
  snapshot_retention_limit   = 7                  # 7 days snapshot retention

  tags = local.tags
}

# Kubernetes Provider Configuration
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

# Helm Provider Configuration
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

# Create namespace
resource "kubernetes_namespace" "docflow" {
  metadata {
    name = "docflow-prod"
    labels = {
      name        = "docflow-prod"
      environment = "production"
    }
  }

  depends_on = [module.eks]
}

# Create secrets in Kubernetes from Secrets Manager
data "aws_secretsmanager_secret_version" "db" {
  secret_id  = module.rds.secret_arn
  depends_on = [module.rds]
}

data "aws_secretsmanager_secret_version" "redis" {
  secret_id  = module.elasticache.secret_arn
  depends_on = [module.elasticache]
}

resource "kubernetes_secret" "db_credentials" {
  metadata {
    name      = "docflow-db-credentials"
    namespace = kubernetes_namespace.docflow.metadata[0].name
  }

  data = {
    url      = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)["url"]
    host     = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)["host"]
    port     = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)["port"]
    database = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)["database"]
    username = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)["username"]
    password = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)["password"]
  }

  type = "Opaque"
}

resource "kubernetes_secret" "redis_credentials" {
  metadata {
    name      = "docflow-redis-credentials"
    namespace = kubernetes_namespace.docflow.metadata[0].name
  }

  data = {
    url  = jsondecode(data.aws_secretsmanager_secret_version.redis.secret_string)["url"]
    host = jsondecode(data.aws_secretsmanager_secret_version.redis.secret_string)["host"]
    port = jsondecode(data.aws_secretsmanager_secret_version.redis.secret_string)["port"]
  }

  type = "Opaque"
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

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
  value       = module.rds.endpoint
}

output "rds_secret_arn" {
  description = "RDS secret ARN in Secrets Manager"
  value       = module.rds.secret_arn
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.elasticache.endpoint
}

output "redis_secret_arn" {
  description = "Redis secret ARN in Secrets Manager"
  value       = module.elasticache.secret_arn
}

output "kubeconfig_command" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}

output "namespace" {
  description = "Kubernetes namespace for DocFlow"
  value       = kubernetes_namespace.docflow.metadata[0].name
}
