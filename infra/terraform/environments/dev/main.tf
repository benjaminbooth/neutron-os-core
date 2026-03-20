# NeutronOS Dev Environment (AWS)
# --------------------------------
# Deploys the rds-pgvector module on a minimal t3.micro instance.

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # TODO: Uncomment after creating the S3 bucket and DynamoDB table:
  #   aws s3api create-bucket --bucket neutronos-tf-state --region us-east-1
  #   aws dynamodb create-table \
  #     --table-name neutronos-tf-lock \
  #     --attribute-definitions AttributeName=LockID,AttributeType=S \
  #     --key-schema AttributeName=LockID,KeyType=HASH \
  #     --billing-mode PAY_PER_REQUEST
  #
  # backend "s3" {
  #   bucket         = "neutronos-tf-state"
  #   key            = "dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "neutronos-tf-lock"
  #   encrypt        = true
  # }
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

# -----------------------------------------------------------------------------
# Provider
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "NeutronOS"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# TODO: VPC Module
# -----------------------------------------------------------------------------
# module "vpc" {
#   source  = "terraform-aws-modules/vpc/aws"
#   version = "~> 5.0"
#
#   name = "neutronos-${var.environment}"
#   cidr = "10.0.0.0/16"
#
#   azs             = ["${var.region}a", "${var.region}b"]
#   private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
#   public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
#
#   enable_nat_gateway = true
#   single_nat_gateway = true   # cost savings for dev
#
#   tags = {
#     Environment = var.environment
#   }
# }

# -----------------------------------------------------------------------------
# TODO: EKS Module
# -----------------------------------------------------------------------------
# module "eks" {
#   source  = "terraform-aws-modules/eks/aws"
#   version = "~> 20.0"
#
#   cluster_name    = "neutronos-${var.environment}"
#   cluster_version = "1.29"
#
#   vpc_id     = module.vpc.vpc_id
#   subnet_ids = module.vpc.private_subnets
#
#   eks_managed_node_groups = {
#     default = {
#       instance_types = ["t3.medium"]
#       min_size       = 1
#       max_size       = 3
#       desired_size   = 2
#     }
#   }
# }

# -----------------------------------------------------------------------------
# RDS pgvector
# -----------------------------------------------------------------------------

# Temporary placeholder values — replace with VPC module outputs once VPC is
# provisioned (see TODO above).
variable "vpc_id" {
  description = "VPC ID (provide via tfvars or replace with module.vpc.vpc_id)"
  type        = string
}

variable "subnet_group_name" {
  description = "DB subnet group name (provide via tfvars or create from VPC module)"
  type        = string
}

module "rds" {
  source = "../../modules/rds-pgvector"

  name        = "neutron-os"
  environment = var.environment

  vpc_id            = var.vpc_id
  subnet_group_name = var.subnet_group_name

  instance_class        = "db.t3.micro"
  allocated_storage     = 20
  max_allocated_storage = 50
  engine_version        = "15.4"

  multi_az            = false
  deletion_protection = false
  skip_final_snapshot = true

  backup_retention_period      = 3
  performance_insights_enabled = false

  tags = {
    CostCenter = "neutronos-dev"
  }
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.endpoint
}

output "rds_connection_string" {
  description = "PostgreSQL connection string"
  value       = module.rds.connection_string
  sensitive   = true
}

output "rds_password" {
  description = "Database password"
  value       = module.rds.password
  sensitive   = true
}
