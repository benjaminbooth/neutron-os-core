# NeutronOS Local Environment (Rascal Simulation)
# ------------------------------------------------
# This environment does NOT provision AWS resources.
# It assumes PostgreSQL 16 + pgvector is installed directly on the host
# (e.g., via the setup-rascal.sh script).
#
# Purpose: provide the same Terraform output interface as the rds-pgvector
# module so that downstream automation can consume connection info uniformly.

terraform {
  required_version = ">= 1.5"
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "db_host" {
  description = "PostgreSQL host"
  type        = string
  default     = "localhost"
}

variable "db_port" {
  description = "PostgreSQL port"
  type        = number
  default     = 5432
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "neut_db"
}

variable "db_user" {
  description = "Database user"
  type        = string
  default     = "neut"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "apply_schema" {
  description = "Whether to apply schema.sql on terraform apply"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Schema provisioner
# -----------------------------------------------------------------------------

resource "null_resource" "apply_schema" {
  count = var.apply_schema ? 1 : 0

  provisioner "local-exec" {
    command = "PGPASSWORD='${var.db_password}' psql -h ${var.db_host} -p ${var.db_port} -U ${var.db_user} -d ${var.db_name} -f ${path.module}/../../db/schema.sql"
  }

  triggers = {
    schema_hash = filemd5("${path.module}/../../db/schema.sql")
  }
}

# -----------------------------------------------------------------------------
# Outputs — same interface as rds-pgvector module
# -----------------------------------------------------------------------------

output "endpoint" {
  description = "PostgreSQL endpoint (host:port)"
  value       = "${var.db_host}:${var.db_port}"
}

output "address" {
  description = "PostgreSQL host"
  value       = var.db_host
}

output "port" {
  description = "PostgreSQL port"
  value       = var.db_port
}

output "database_name" {
  description = "Database name"
  value       = var.db_name
}

output "username" {
  description = "Database username"
  value       = var.db_user
}

output "password" {
  description = "Database password"
  value       = var.db_password
  sensitive   = true
}

output "security_group_id" {
  description = "Security group ID (not applicable for local)"
  value       = "n/a"
}

output "connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${var.db_user}:${var.db_password}@${var.db_host}:${var.db_port}/${var.db_name}"
  sensitive   = true
}
