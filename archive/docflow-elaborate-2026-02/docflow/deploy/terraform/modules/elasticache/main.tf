# ElastiCache Module for DocFlow
# Creates Redis cluster for caching

variable "name" {
  description = "Cluster name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_group_name" {
  description = "ElastiCache subnet group name"
  type        = string
}

variable "allowed_security_group_ids" {
  description = "Security group IDs allowed to access Redis"
  type        = list(string)
  default     = []
}

variable "node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

variable "engine_version" {
  description = "Redis version"
  type        = string
  default     = "7.0"
}

variable "parameter_group_family" {
  description = "Parameter group family"
  type        = string
  default     = "redis7"
}

variable "automatic_failover_enabled" {
  description = "Enable automatic failover (requires 2+ nodes)"
  type        = bool
  default     = false
}

variable "multi_az_enabled" {
  description = "Enable Multi-AZ (requires automatic_failover_enabled)"
  type        = bool
  default     = false
}

variable "snapshot_retention_limit" {
  description = "Snapshot retention days"
  type        = number
  default     = 0
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Security Group
resource "aws_security_group" "redis" {
  name        = "${var.name}-${var.environment}-redis"
  description = "ElastiCache Redis security group"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Redis from allowed security groups"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name}-${var.environment}-redis"
  })
}

# Parameter Group
resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.name}-${var.environment}"
  family = var.parameter_group_family

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = var.tags
}

# Redis Replication Group (for HA) or Cluster
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.name}-${var.environment}"
  description          = "DocFlow Redis cluster for ${var.environment}"

  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  parameter_group_name = aws_elasticache_parameter_group.main.name

  subnet_group_name  = var.subnet_group_name
  security_group_ids = [aws_security_group.redis.id]

  automatic_failover_enabled = var.automatic_failover_enabled
  multi_az_enabled           = var.multi_az_enabled

  at_rest_encryption_enabled = true
  transit_encryption_enabled = false  # Set to true if clients support TLS

  snapshot_retention_limit = var.snapshot_retention_limit
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "mon:05:00-mon:06:00"

  apply_immediately = var.environment != "prod"

  tags = var.tags
}

# Store connection info in Secrets Manager
resource "aws_secretsmanager_secret" "redis" {
  name                    = "${var.name}-${var.environment}/redis-credentials"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id
  secret_string = jsonencode({
    host = aws_elasticache_replication_group.main.primary_endpoint_address
    port = 6379
    url  = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379"
  })
}

# Outputs
output "endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "port" {
  description = "Redis port"
  value       = 6379
}

output "security_group_id" {
  description = "Redis security group ID"
  value       = aws_security_group.redis.id
}

output "secret_arn" {
  description = "Secrets Manager secret ARN"
  value       = aws_secretsmanager_secret.redis.arn
}

output "connection_url" {
  description = "Redis connection URL"
  value       = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379"
}
