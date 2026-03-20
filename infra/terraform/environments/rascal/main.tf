# NeutronOS Rascal Environment
# ------------------------------------------------------------------------------
# Rascal is a physical GPU server at UT Austin used for self-hosted LLM
# experimentation (Qwen, restricted tier). Requires UT VPN (vpn_profile = "ut-rascal").
#
# This target:
#   1. Installs the NeutronOS Helm chart on the rascal k3d cluster
#   2. Outputs Ollama and PostgreSQL connection info for runtime/config/
#
# Prerequisites (one-time, via scripts/setup-rascal.sh):
#   - k3d + containerd installed on Rascal
#   - k3d cluster "rascal" created
#   - kubeconfig merged locally (kubectl config use-context k3d-rascal)
#   - nvidia container toolkit installed (for GPU resource requests)
#
# Deploy:
#   terraform init
#   terraform apply -var="db_password=<secret>" -var="postgres_password=<secret>"
#
# Teardown:
#   terraform destroy

terraform {
  required_version = ">= 1.5"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.27"
    }
  }
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "kubeconfig_context" {
  description = "kubectl context name for the Rascal k3d cluster"
  type        = string
  default     = "k3d-rascal"
}

variable "namespace" {
  description = "Kubernetes namespace to deploy into"
  type        = string
  default     = "neut"
}

variable "release_name" {
  description = "Helm release name"
  type        = string
  default     = "neut"
}

variable "chart_path" {
  description = "Path to the neutron-os Helm chart"
  type        = string
  default     = "../../helm/charts/neutron-os"
}

variable "db_password" {
  description = "PostgreSQL neut user password"
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "PostgreSQL superuser (postgres) password"
  type        = string
  sensitive   = true
}

variable "ollama_nodeport" {
  description = "NodePort for external Ollama access"
  type        = number
  default     = 31434
}

# -----------------------------------------------------------------------------
# Provider configuration
# -----------------------------------------------------------------------------

provider "helm" {
  kubernetes {
    config_path    = "~/.kube/config"
    config_context = var.kubeconfig_context
  }
}

provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = var.kubeconfig_context
}

# -----------------------------------------------------------------------------
# Namespace
# -----------------------------------------------------------------------------

resource "kubernetes_namespace" "neut" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "neut/environment"             = "rascal"
    }
  }
}

# -----------------------------------------------------------------------------
# Helm release — neutron-os with Rascal overrides
# -----------------------------------------------------------------------------

resource "helm_release" "neutron_os" {
  name             = var.release_name
  chart            = var.chart_path
  namespace        = kubernetes_namespace.neut.metadata[0].name
  create_namespace = false

  values = [
    file("${var.chart_path}/values-rascal.yaml")
  ]

  # Pass secrets at deploy time — never store in values files
  set_sensitive {
    name  = "postgresql.auth.password"
    value = var.db_password
  }

  set_sensitive {
    name  = "postgresql.auth.postgresPassword"
    value = var.postgres_password
  }

  # Ollama is disabled on Rascal — llama-server owns the GPU directly.
  # LLM access is via: https://rascal.austin.utexas.edu:41883/v1 (RASCAL_API_KEY)

  timeout          = 600   # 10 min — model pull can be slow on first deploy
  wait             = true
  wait_for_jobs    = true

  depends_on = [kubernetes_namespace.neut]
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "ollama_internal_url" {
  description = "Ollama ClusterIP endpoint (in-cluster)"
  value       = "http://${var.release_name}-ollama.${var.namespace}.svc.cluster.local:11434"
}

output "ollama_external_url" {
  description = "Ollama NodePort endpoint (from UT VPN — substitute Rascal IP)"
  value       = "http://10.159.142.118:${var.ollama_nodeport}"
}

output "postgresql_service" {
  description = "PostgreSQL ClusterIP service (in-cluster)"
  value       = "${var.release_name}-postgresql.${var.namespace}.svc.cluster.local:5432"
}

output "namespace" {
  description = "Kubernetes namespace"
  value       = var.namespace
}

output "release_name" {
  description = "Helm release name"
  value       = var.release_name
}
