# RDS Module for DocFlow
# Creates PostgreSQL RDS instance with pgvector support

variable "name" {
  description = "Instance name"
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
  description = "DB subnet group name"
  type        = string
}

variable "allowed_security_group_ids" {
  description = "Security group IDs allowed to access the database"
  type        = list(string)
  default     = []
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Maximum allocated storage in GB for autoscaling"
  type        = number
  default     = 100
}

variable "engine_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "docflow"
}

variable "database_user" {
  description = "Database username"
  type        = string
  default     = "docflow"
}

variable "multi_az" {
  description = "Enable Multi-AZ"
  type        = bool
  default     = false
}

variable "backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on deletion"
  type        = bool
  default     = true
}

variable "performance_insights_enabled" {
  description = "Enable Performance Insights"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Random password
resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Security Group
resource "aws_security_group" "db" {
  name        = "${var.name}-${var.environment}-db"
  description = "RDS PostgreSQL security group"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from allowed security groups"
    from_port       = 5432
    to_port         = 5432
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
    Name = "${var.name}-${var.environment}-db"
  })
}

# Parameter Group with pgvector
resource "aws_db_parameter_group" "main" {
  name   = "${var.name}-${var.environment}"
  family = "postgres15"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements,pgvector"
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  tags = var.tags
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = "${var.name}-${var.environment}"

  engine               = "postgres"
  engine_version       = var.engine_version
  instance_class       = var.instance_class
  allocated_storage    = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type         = "gp3"
  storage_encrypted    = true

  db_name  = var.database_name
  username = var.database_user
  password = random_password.db.result

  db_subnet_group_name   = var.subnet_group_name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  multi_az               = var.multi_az
  publicly_accessible    = false
  backup_retention_period = var.backup_retention_period
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"

  deletion_protection = var.deletion_protection
  skip_final_snapshot = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-${var.environment}-final"

  performance_insights_enabled = var.performance_insights_enabled
  
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  copy_tags_to_snapshot = true

  tags = var.tags
}

# Store password in Secrets Manager
resource "aws_secretsmanager_secret" "db" {
  name                    = "${var.name}-${var.environment}/rds-credentials"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.database_user
    password = random_password.db.result
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    database = var.database_name
    url      = "postgresql://${var.database_user}:${urlencode(random_password.db.result)}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${var.database_name}"
  })
}

# Outputs
output "endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.main.endpoint
}

output "address" {
  description = "RDS address (hostname)"
  value       = aws_db_instance.main.address
}

output "port" {
  description = "RDS port"
  value       = aws_db_instance.main.port
}

output "database_name" {
  description = "Database name"
  value       = aws_db_instance.main.db_name
}

output "username" {
  description = "Database username"
  value       = aws_db_instance.main.username
}

output "security_group_id" {
  description = "RDS security group ID"
  value       = aws_security_group.db.id
}

output "secret_arn" {
  description = "Secrets Manager secret ARN"
  value       = aws_secretsmanager_secret.db.arn
}

output "connection_url" {
  description = "Database connection URL"
  value       = "postgresql://${var.database_user}:****@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${var.database_name}"
  sensitive   = false
}
