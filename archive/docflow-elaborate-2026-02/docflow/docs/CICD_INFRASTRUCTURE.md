# DocFlow CI/CD & Infrastructure Plan

> A model infrastructure setup for Neutron OS projects: private-first development with open source transition path, blue/green deployments, and zero-downtime guarantees.

## Overview

This document covers:
1. **Package & Plugin Hosting** - Private now, public later
2. **Repository Strategy** - GitLab private → GitHub public transition
3. **Infrastructure Architecture** - AWS + Kubernetes
4. **Local Development** - K3D mirroring production
5. **CI/CD Pipelines** - GitLab CI with GitHub Actions ready
6. **Blue/Green Deployments** - Zero-downtime releases
7. **Open Source Preparation** - Content scrubbing and licensing

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Infrastructure Overview                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LOCAL (K3D)              STAGE (AWS EKS)           PROD (AWS EKS)         │
│   ─────────────            ──────────────            ─────────────          │
│   Developer laptops        Pre-production            Production             │
│   Full stack replica       Same config as prod       Blue/Green deploy      │
│   Fast iteration           Integration testing       High availability      │
│                                                                              │
│   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐         │
│   │   K3D       │          │   EKS       │          │   EKS       │         │
│   │   Cluster   │          │   Cluster   │          │   Cluster   │         │
│   └──────┬──────┘          └──────┬──────┘          └──────┬──────┘         │
│          │                        │                        │                 │
│   ┌──────┴──────┐          ┌──────┴──────┐          ┌──────┴──────┐         │
│   │ PostgreSQL  │          │    RDS      │          │    RDS      │         │
│   │ (container) │          │ PostgreSQL  │          │ PostgreSQL  │         │
│   │ + pgvector  │          │ + pgvector  │          │ Multi-AZ    │         │
│   └─────────────┘          └─────────────┘          └─────────────┘         │
│                                                                              │
│   GitLab Container         GitLab Container         GitLab Container        │
│   Registry (private)       Registry (private)       Registry (private)      │
│         │                        │                        │                  │
│         └────────────────────────┴────────────────────────┘                  │
│                                  │                                           │
│                    ┌─────────────┴─────────────┐                             │
│                    │  Future: GitHub Packages  │                             │
│                    │  (public, post-OSS)       │                             │
│                    └───────────────────────────┘                             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Package & Plugin Hosting Strategy

### Phase 1: Private (Now)

| Artifact | Private Host | Access |
|----------|--------------|--------|
| Python packages | GitLab Package Registry | Team members via PAT |
| Container images | GitLab Container Registry | Pull via CI/CD tokens |
| VS Code extension | GitLab Generic Packages | Manual VSIX install |
| PyCharm plugin | GitLab Generic Packages | Manual ZIP install |
| Helm charts | GitLab Helm Registry | Terraform pulls via token |
| Terraform modules | GitLab repo submodules | Git clone with token |

**GitLab Package Registry Setup:**

```yaml
# .gitlab-ci.yml - publish Python package
publish-pypi:
  stage: publish
  image: python:3.11
  script:
    - pip install build twine
    - python -m build
    - TWINE_PASSWORD=${CI_JOB_TOKEN} TWINE_USERNAME=gitlab-ci-token 
      python -m twine upload --repository-url ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/pypi dist/*
  rules:
    - if: $CI_COMMIT_TAG
```

**Install from private registry:**

```bash
# ~/.pip/pip.conf (or per-project)
[global]
extra-index-url = https://__token__:${GITLAB_PAT}@gitlab.example.com/api/v4/projects/123/packages/pypi/simple
```

### Phase 2: Public (Post Open Source)

| Artifact | Public Host | Transition |
|----------|-------------|------------|
| Python packages | PyPI | Publish docflow package |
| Container images | GitHub Container Registry (ghcr.io) | Mirror from GitLab |
| VS Code extension | VS Code Marketplace | Publish under neutron-os org |
| PyCharm plugin | JetBrains Marketplace | Publish under Neutron OS |
| Helm charts | GitHub Pages / ArtifactHub | Public Helm repo |
| Terraform modules | Terraform Registry | Publish as verified module |

---

## 2. Repository Strategy

### Current: Private GitLab

```
gitlab.example.com/neutron-os/
├── docflow/                 # This project
├── neutron-cli/             # Future CLI umbrella
├── infrastructure/          # Terraform modules
└── helm-charts/             # Helm chart repository
```

### Transition: GitLab → GitHub

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Open Source Transition Timeline                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: Internal (Now)                                                    │
│  ───────────────────────                                                    │
│  • All code in private GitLab                                               │
│  • Team uses private package registry                                       │
│  • Document UT references for later scrubbing                               │
│                                                                             │
│  Phase 2: Prepare (Before OSS)                                              │
│  ─────────────────────────────                                              │
│  • Create scrubbing script (see Section 7)                                  │
│  • Review with UT compliance                                                │
│  • Set up GitHub org: github.com/neutron-os                                 │
│  • Prepare LICENSE (Apache 2.0 recommended)                                 │
│  • Write public README, CONTRIBUTING                                        │
│                                                                             │
│  Phase 3: Mirror (Transition)                                               │
│  ────────────────────────────                                               │
│  • Set up GitLab → GitHub mirroring                                         │
│  • Keep GitLab as source of truth during transition                         │
│  • Test GitHub Actions CI in parallel                                       │
│                                                                             │
│  Phase 4: Public (Post OSS)                                                 │
│  ──────────────────────────                                                 │
│  • GitHub becomes primary                                                   │
│  • GitLab mirrors GitHub (reverse direction)                                │
│  • Private internal fork for UT-specific configs                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Repository Structure for Open Source

```
github.com/neutron-os/docflow/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── release.yml
│   │   └── security.yml
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
├── src/docflow/              # Python source
├── extensions/
│   ├── vscode/               # VS Code extension
│   └── intellij/             # PyCharm plugin
├── deploy/
│   ├── helm/                 # Helm charts
│   ├── terraform/            # Terraform modules
│   └── k3d/                  # Local dev setup
├── docs/
├── examples/
│   └── medical-research/     # Generic examples (scrubbed)
├── LICENSE                   # Apache 2.0
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
└── pyproject.toml
```

---

## 3. Infrastructure Architecture

### AWS Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              AWS Infrastructure                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                              VPC                                        ││
│  │                                                                         ││
│  │   Public Subnets                    Private Subnets                     ││
│  │   ┌─────────────────┐               ┌─────────────────┐                 ││
│  │   │  ALB            │               │  EKS Nodes      │                 ││
│  │   │  (ingress)      │───────────────│  (workers)      │                 ││
│  │   └─────────────────┘               └────────┬────────┘                 ││
│  │                                              │                          ││
│  │   ┌─────────────────┐               ┌───────┴────────┐                  ││
│  │   │  NAT Gateway    │               │  RDS PostgreSQL│                  ││
│  │   │  (egress)       │               │  + pgvector    │                  ││
│  │   └─────────────────┘               │  (Multi-AZ)    │                  ││
│  │                                     └────────────────┘                  ││
│  │                                                                         ││
│  │   ┌─────────────────┐               ┌────────────────┐                  ││
│  │   │  Route 53       │               │  ElastiCache   │                  ││
│  │   │  (DNS)          │               │  Redis         │                  ││
│  │   └─────────────────┘               └────────────────┘                  ││
│  │                                                                         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  S3             │  │  Secrets Manager│  │  CloudWatch     │             │
│  │  (documents,    │  │  (credentials)  │  │  (logs/metrics) │             │
│  │   backups)      │  │                 │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Kubernetes Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Namespace: docflow-blue                    Namespace: docflow-green        │
│  ┌────────────────────────────┐             ┌────────────────────────────┐  │
│  │                            │             │                            │  │
│  │  ┌──────────┐ ┌──────────┐ │             │  ┌──────────┐ ┌──────────┐ │  │
│  │  │ API      │ │ Agent    │ │             │  │ API      │ │ Agent    │ │  │
│  │  │ Server   │ │ Server   │ │             │  │ Server   │ │ Server   │ │  │
│  │  │ (3 pods) │ │ (2 pods) │ │             │  │ (3 pods) │ │ (2 pods) │ │  │
│  │  └──────────┘ └──────────┘ │             │  └──────────┘ └──────────┘ │  │
│  │                            │             │                            │  │
│  │  ┌──────────┐ ┌──────────┐ │             │  ┌──────────┐ ┌──────────┐ │  │
│  │  │ Worker   │ │ Embedder │ │             │  │ Worker   │ │ Embedder │ │  │
│  │  │ (jobs)   │ │ Service  │ │             │  │ (jobs)   │ │ Service  │ │  │
│  │  └──────────┘ └──────────┘ │             │  └──────────┘ └──────────┘ │  │
│  │                            │             │                            │  │
│  └────────────────────────────┘             └────────────────────────────┘  │
│            │                                           │                     │
│            │         Service Mesh (optional)           │                     │
│            └───────────────────┬───────────────────────┘                     │
│                                │                                             │
│  Namespace: docflow-infra      │                                             │
│  ┌─────────────────────────────┴──────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ Ingress      │  │ Cert-Manager │  │ External     │                  │ │
│  │  │ Controller   │  │              │  │ Secrets      │                  │ │
│  │  │ (nginx)      │  │              │  │ Operator     │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Namespace: monitoring                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Prometheus │ Grafana │ Loki │ AlertManager                             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Local Development with K3D

### Quick Start

```bash
# Prerequisites
brew install k3d kubectl helm terraform

# Create local cluster
cd deploy/k3d
make create-cluster

# Deploy full stack
make deploy-all

# Access services
echo "DocFlow API: http://localhost:8080"
echo "DocFlow Agent: ws://localhost:8765"
echo "Grafana: http://localhost:3000"
```

### K3D Cluster Configuration

```yaml
# deploy/k3d/k3d-config.yaml
apiVersion: k3d.io/v1alpha5
kind: Simple
metadata:
  name: docflow-local
servers: 1
agents: 2
kubeAPI:
  host: "localhost"
  hostIP: "127.0.0.1"
  hostPort: "6443"
image: rancher/k3s:v1.28.5-k3s1
ports:
  - port: 8080:80
    nodeFilters:
      - loadbalancer
  - port: 8443:443
    nodeFilters:
      - loadbalancer
  - port: 5432:5432
    nodeFilters:
      - loadbalancer
  - port: 8765:8765
    nodeFilters:
      - loadbalancer
options:
  k3d:
    wait: true
    timeout: "120s"
  k3s:
    extraArgs:
      - arg: --disable=traefik
        nodeFilters:
          - server:*
  kubeconfig:
    updateDefaultKubeconfig: true
    switchCurrentContext: true
registries:
  create:
    name: registry.localhost
    host: "0.0.0.0"
    hostPort: "5111"
volumes:
  - volume: /tmp/k3d-docflow-storage:/var/lib/rancher/k3s/storage
    nodeFilters:
      - all
```

### Local Makefile

```makefile
# deploy/k3d/Makefile

CLUSTER_NAME := docflow-local
NAMESPACE := docflow
REGISTRY := registry.localhost:5111

.PHONY: create-cluster delete-cluster deploy-all clean

# === Cluster Management ===

create-cluster:
	@echo "Creating K3D cluster..."
	k3d cluster create --config k3d-config.yaml
	@echo "Installing NGINX Ingress..."
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
	@echo "Waiting for ingress controller..."
	kubectl wait --namespace ingress-nginx \
		--for=condition=ready pod \
		--selector=app.kubernetes.io/component=controller \
		--timeout=120s
	@echo "Creating namespace..."
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -

delete-cluster:
	k3d cluster delete $(CLUSTER_NAME)

# === Build & Push ===

build-images:
	docker build -t $(REGISTRY)/docflow-api:local -f docker/Dockerfile.api .
	docker build -t $(REGISTRY)/docflow-agent:local -f docker/Dockerfile.agent .
	docker push $(REGISTRY)/docflow-api:local
	docker push $(REGISTRY)/docflow-agent:local

# === Deploy ===

deploy-infra:
	@echo "Deploying PostgreSQL with pgvector..."
	helm upgrade --install postgresql bitnami/postgresql \
		--namespace $(NAMESPACE) \
		--values values/postgresql-local.yaml \
		--wait
	@echo "Deploying Redis..."
	helm upgrade --install redis bitnami/redis \
		--namespace $(NAMESPACE) \
		--values values/redis-local.yaml \
		--wait

deploy-app: build-images
	@echo "Deploying DocFlow..."
	helm upgrade --install docflow ../helm/docflow \
		--namespace $(NAMESPACE) \
		--values values/docflow-local.yaml \
		--set image.tag=local \
		--wait

deploy-monitoring:
	@echo "Deploying monitoring stack..."
	helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
		--namespace monitoring \
		--create-namespace \
		--values values/monitoring-local.yaml \
		--wait

deploy-all: deploy-infra deploy-app deploy-monitoring
	@echo "All services deployed!"
	@echo ""
	@echo "Access points:"
	@echo "  DocFlow API:    http://localhost:8080"
	@echo "  DocFlow Agent:  ws://localhost:8765"
	@echo "  Grafana:        http://localhost:3000 (admin/admin)"
	@echo "  PostgreSQL:     localhost:5432"

# === Testing ===

test-local:
	@echo "Running local integration tests..."
	kubectl run test-runner --rm -it --restart=Never \
		--namespace $(NAMESPACE) \
		--image=$(REGISTRY)/docflow-api:local \
		-- pytest tests/integration/

# === Utilities ===

logs-api:
	kubectl logs -f -l app=docflow-api --namespace $(NAMESPACE)

logs-agent:
	kubectl logs -f -l app=docflow-agent --namespace $(NAMESPACE)

shell-api:
	kubectl exec -it deploy/docflow-api --namespace $(NAMESPACE) -- /bin/bash

port-forward-db:
	kubectl port-forward svc/postgresql 5432:5432 --namespace $(NAMESPACE)

clean:
	helm uninstall docflow --namespace $(NAMESPACE) || true
	helm uninstall postgresql --namespace $(NAMESPACE) || true
	helm uninstall redis --namespace $(NAMESPACE) || true
```

### Local Values Files

```yaml
# deploy/k3d/values/postgresql-local.yaml
auth:
  postgresPassword: localdev
  database: docflow
  
primary:
  initdb:
    scripts:
      init-pgvector.sql: |
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
  persistence:
    size: 5Gi
  resources:
    requests:
      memory: 256Mi
      cpu: 100m
    limits:
      memory: 512Mi
      cpu: 500m
```

```yaml
# deploy/k3d/values/docflow-local.yaml
replicaCount:
  api: 1
  agent: 1
  
image:
  repository: registry.localhost:5111/docflow-api
  tag: local
  pullPolicy: Always

env:
  DOCFLOW_ENV: local
  DATABASE_URL: postgresql://postgres:localdev@postgresql:5432/docflow
  REDIS_URL: redis://redis-master:6379
  LLM_PROVIDER: local
  LLM_ENDPOINT: http://ollama:11434
  EMBEDDING_MODEL: nomic-embed-text
  
resources:
  api:
    requests:
      memory: 256Mi
      cpu: 100m
    limits:
      memory: 512Mi
      cpu: 500m
  agent:
    requests:
      memory: 512Mi
      cpu: 200m
    limits:
      memory: 1Gi
      cpu: 1000m

# Local development extras
ollama:
  enabled: true
  models:
    - nomic-embed-text
    - llama3.2

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: docflow.localhost
      paths:
        - path: /
          pathType: Prefix
```

---

## 5. Terraform Modules

### Module Structure

```
deploy/terraform/
├── modules/
│   ├── vpc/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── eks/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── rds/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── elasticache/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── s3/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── environments/
│   ├── stage/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── prod/
│       ├── main.tf
│       ├── variables.tf
│       ├── terraform.tfvars
│       └── backend.tf
└── README.md
```

### VPC Module

```hcl
# deploy/terraform/modules/vpc/main.tf

variable "environment" {
  description = "Environment name (stage, prod)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
}

locals {
  name = "docflow-${var.environment}"
  
  tags = {
    Environment = var.environment
    Project     = "docflow"
    ManagedBy   = "terraform"
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i + length(var.availability_zones))]
  
  # Database subnets
  database_subnets = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i + 2 * length(var.availability_zones))]
  create_database_subnet_group = true

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment == "stage" # Cost saving for stage
  enable_dns_hostnames   = true
  enable_dns_support     = true

  # Tags for EKS
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
  
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }

  tags = local.tags
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "private_subnets" {
  value = module.vpc.private_subnets
}

output "public_subnets" {
  value = module.vpc.public_subnets
}

output "database_subnet_group" {
  value = module.vpc.database_subnet_group_name
}
```

### EKS Module

```hcl
# deploy/terraform/modules/eks/main.tf

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnets" {
  type = list(string)
}

variable "cluster_version" {
  type    = string
  default = "1.28"
}

locals {
  name = "docflow-${var.environment}"
  
  tags = {
    Environment = var.environment
    Project     = "docflow"
    ManagedBy   = "terraform"
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = local.name
  cluster_version = var.cluster_version

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnets

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
      most_recent = true
    }
  }

  # Node groups
  eks_managed_node_groups = {
    # General workloads
    general = {
      name = "${local.name}-general"

      instance_types = var.environment == "prod" ? ["m6i.large"] : ["t3.medium"]
      capacity_type  = var.environment == "prod" ? "ON_DEMAND" : "SPOT"

      min_size     = var.environment == "prod" ? 2 : 1
      max_size     = var.environment == "prod" ? 10 : 3
      desired_size = var.environment == "prod" ? 3 : 1

      labels = {
        workload = "general"
      }
    }

    # GPU nodes for LLM inference (prod only)
    gpu = var.environment == "prod" ? {
      name = "${local.name}-gpu"

      instance_types = ["g4dn.xlarge"]
      capacity_type  = "ON_DEMAND"

      min_size     = 0
      max_size     = 2
      desired_size = 1

      labels = {
        workload = "gpu"
        "nvidia.com/gpu" = "true"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    } : null
  }

  # IRSA for external-secrets
  enable_irsa = true

  tags = local.tags
}

# OIDC provider for IRSA
data "aws_iam_openid_connect_provider" "eks" {
  url = module.eks.cluster_oidc_issuer_url
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  value = module.eks.cluster_certificate_authority_data
}

output "oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}
```

### RDS Module (PostgreSQL + pgvector)

```hcl
# deploy/terraform/modules/rds/main.tf

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "database_subnet_group" {
  type = string
}

variable "allowed_security_groups" {
  type = list(string)
}

locals {
  name = "docflow-${var.environment}"
  
  tags = {
    Environment = var.environment
    Project     = "docflow"
    ManagedBy   = "terraform"
  }
}

# Security group
resource "aws_security_group" "rds" {
  name_prefix = "${local.name}-rds-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_security_groups
  }

  tags = local.tags
}

# Parameter group with pgvector
resource "aws_db_parameter_group" "postgres" {
  family = "postgres15"
  name   = "${local.name}-params"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,pgvector"
  }

  parameter {
    name  = "max_connections"
    value = var.environment == "prod" ? "200" : "100"
  }

  tags = local.tags
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
  instance_class       = var.environment == "prod" ? "db.r6g.large" : "db.t3.medium"

  allocated_storage     = var.environment == "prod" ? 100 : 20
  max_allocated_storage = var.environment == "prod" ? 500 : 50

  db_name  = "docflow"
  username = "docflow"
  port     = 5432

  # High availability for prod
  multi_az = var.environment == "prod"

  db_subnet_group_name   = var.database_subnet_group
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Backups
  backup_retention_period = var.environment == "prod" ? 30 : 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # Encryption
  storage_encrypted = true

  # Performance Insights (prod only)
  performance_insights_enabled = var.environment == "prod"

  # Parameter group
  parameter_group_name = aws_db_parameter_group.postgres.name

  # Deletion protection for prod
  deletion_protection = var.environment == "prod"

  tags = local.tags
}

# Store password in Secrets Manager
resource "aws_secretsmanager_secret" "rds_password" {
  name = "${local.name}/rds-password"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "rds_password" {
  secret_id = aws_secretsmanager_secret.rds_password.id
  secret_string = jsonencode({
    username = module.rds.db_instance_username
    password = module.rds.db_instance_password
    host     = module.rds.db_instance_address
    port     = module.rds.db_instance_port
    database = module.rds.db_instance_name
  })
}

output "endpoint" {
  value = module.rds.db_instance_endpoint
}

output "secret_arn" {
  value = aws_secretsmanager_secret.rds_password.arn
}
```

### Environment Configuration

```hcl
# deploy/terraform/environments/stage/main.tf

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
  }

  backend "s3" {
    bucket         = "docflow-terraform-state"
    key            = "stage/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "docflow-terraform-locks"
    encrypt        = true
  }
}

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

locals {
  environment = "stage"
  region      = "us-east-1"
  azs         = ["us-east-1a", "us-east-1b"]
}

# VPC
module "vpc" {
  source = "../../modules/vpc"
  
  environment        = local.environment
  availability_zones = local.azs
  vpc_cidr           = "10.0.0.0/16"
}

# EKS
module "eks" {
  source = "../../modules/eks"
  
  environment     = local.environment
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnets
  cluster_version = "1.28"
}

# RDS
module "rds" {
  source = "../../modules/rds"
  
  environment             = local.environment
  vpc_id                  = module.vpc.vpc_id
  database_subnet_group   = module.vpc.database_subnet_group
  allowed_security_groups = [module.eks.cluster_security_group_id]
}

# Redis
module "elasticache" {
  source = "../../modules/elasticache"
  
  environment             = local.environment
  vpc_id                  = module.vpc.vpc_id
  private_subnets         = module.vpc.private_subnets
  allowed_security_groups = [module.eks.cluster_security_group_id]
}

# Configure kubectl
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

# Configure Helm
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

# Deploy DocFlow via Helm
resource "helm_release" "docflow" {
  name       = "docflow"
  namespace  = "docflow"
  repository = "https://gitlab.example.com/api/v4/projects/123/packages/helm/stable"
  chart      = "docflow"
  version    = var.docflow_version

  create_namespace = true

  values = [
    templatefile("${path.module}/values.yaml", {
      environment     = local.environment
      rds_secret_arn  = module.rds.secret_arn
      redis_endpoint  = module.elasticache.endpoint
    })
  ]

  depends_on = [module.eks, module.rds, module.elasticache]
}
```

---

## 6. Helm Charts

### Chart Structure

```
deploy/helm/docflow/
├── Chart.yaml
├── values.yaml
├── values-stage.yaml
├── values-prod.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── deployment-api.yaml
│   ├── deployment-agent.yaml
│   ├── service-api.yaml
│   ├── service-agent.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── pdb.yaml
│   ├── serviceaccount.yaml
│   └── jobs/
│       ├── migration.yaml
│       └── index-rebuild.yaml
└── charts/               # Subcharts if needed
```

### Main Values

```yaml
# deploy/helm/docflow/values.yaml

# Common configuration
nameOverride: ""
fullnameOverride: ""

# Environment
environment: local

# Image configuration
image:
  repository: ghcr.io/neutron-os/docflow
  tag: latest
  pullPolicy: IfNotPresent
  pullSecrets: []

# Replica counts
replicaCount:
  api: 2
  agent: 2

# API Server
api:
  resources:
    requests:
      memory: 256Mi
      cpu: 100m
    limits:
      memory: 512Mi
      cpu: 500m
  
  livenessProbe:
    httpGet:
      path: /health
      port: http
    initialDelaySeconds: 10
    periodSeconds: 10
  
  readinessProbe:
    httpGet:
      path: /ready
      port: http
    initialDelaySeconds: 5
    periodSeconds: 5

# Agent Server
agent:
  resources:
    requests:
      memory: 512Mi
      cpu: 200m
    limits:
      memory: 2Gi
      cpu: 1000m
  
  # GPU support (prod)
  gpu:
    enabled: false
    count: 1

# Database
database:
  # External database (RDS)
  external:
    enabled: true
    secretName: docflow-db-credentials
  # Internal PostgreSQL (local dev)
  internal:
    enabled: false

# Redis
redis:
  external:
    enabled: true
    host: ""
    port: 6379
  internal:
    enabled: false

# LLM Configuration
llm:
  provider: local  # local, anthropic, openai
  endpoint: http://ollama:11434
  model: llama3.2
  
  # Fallback configuration
  fallback:
    enabled: false
    provider: anthropic
    secretName: llm-api-keys

# Embedding Configuration
embedding:
  model: nomic-embed-text-v1.5
  endpoint: http://ollama:11434

# Ingress
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: docflow.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: docflow-tls
      hosts:
        - docflow.example.com

# Autoscaling
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

# Pod Disruption Budget
podDisruptionBudget:
  enabled: true
  minAvailable: 1

# Service Account
serviceAccount:
  create: true
  annotations: {}
  # For IRSA (AWS)
  # eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/docflow-role

# Blue/Green deployment
blueGreen:
  enabled: false
  activeColor: blue

# Monitoring
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
  dashboards:
    enabled: true
```

### Blue/Green Deployment

```yaml
# deploy/helm/docflow/templates/deployment-api.yaml
{{- $color := .Values.blueGreen.enabled | ternary .Values.blueGreen.activeColor "" }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "docflow.fullname" . }}-api{{ $color | ternary (printf "-%s" $color) "" }}
  labels:
    {{- include "docflow.labels" . | nindent 4 }}
    app.kubernetes.io/component: api
    {{- if .Values.blueGreen.enabled }}
    docflow.io/color: {{ $color }}
    {{- end }}
spec:
  replicas: {{ .Values.replicaCount.api }}
  selector:
    matchLabels:
      {{- include "docflow.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: api
      {{- if .Values.blueGreen.enabled }}
      docflow.io/color: {{ $color }}
      {{- end }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        {{- include "docflow.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: api
        {{- if .Values.blueGreen.enabled }}
        docflow.io/color: {{ $color }}
        {{- end }}
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
    spec:
      serviceAccountName: {{ include "docflow.serviceAccountName" . }}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: api
          image: "{{ .Values.image.repository }}-api:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          envFrom:
            - configMapRef:
                name: {{ include "docflow.fullname" . }}-config
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.database.external.secretName }}
                  key: url
          livenessProbe:
            {{- toYaml .Values.api.livenessProbe | nindent 12 }}
          readinessProbe:
            {{- toYaml .Values.api.readinessProbe | nindent 12 }}
          resources:
            {{- toYaml .Values.api.resources | nindent 12 }}
```

### Blue/Green Service Switching

```yaml
# deploy/helm/docflow/templates/service-api.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "docflow.fullname" . }}-api
  labels:
    {{- include "docflow.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "docflow.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: api
    {{- if .Values.blueGreen.enabled }}
    # Service points to active color only
    docflow.io/color: {{ .Values.blueGreen.activeColor }}
    {{- end }}
```

---

## 7. CI/CD Pipelines

### GitLab CI (Current)

```yaml
# .gitlab-ci.yml

stages:
  - test
  - build
  - security
  - deploy-stage
  - integration-test
  - deploy-prod

variables:
  DOCKER_REGISTRY: $CI_REGISTRY
  DOCKER_IMAGE: $CI_REGISTRY_IMAGE
  HELM_REPO: $CI_API_V4_URL/projects/$CI_PROJECT_ID/packages/helm/api/stable/charts

# === Test Stage ===
test:
  stage: test
  image: python:3.11
  services:
    - postgres:15
  variables:
    POSTGRES_DB: test
    POSTGRES_USER: test
    POSTGRES_PASSWORD: test
    DATABASE_URL: postgresql://test:test@postgres:5432/test
  before_script:
    - pip install -e ".[dev]"
  script:
    - pytest tests/ --cov=docflow --cov-report=xml
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

lint:
  stage: test
  image: python:3.11
  script:
    - pip install ruff mypy
    - ruff check src/
    - mypy src/docflow

# === Build Stage ===
build-api:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $DOCKER_IMAGE/api:$CI_COMMIT_SHA -f docker/Dockerfile.api .
    - docker push $DOCKER_IMAGE/api:$CI_COMMIT_SHA
    - |
      if [ "$CI_COMMIT_TAG" ]; then
        docker tag $DOCKER_IMAGE/api:$CI_COMMIT_SHA $DOCKER_IMAGE/api:$CI_COMMIT_TAG
        docker push $DOCKER_IMAGE/api:$CI_COMMIT_TAG
      fi
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_TAG

build-agent:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $DOCKER_IMAGE/agent:$CI_COMMIT_SHA -f docker/Dockerfile.agent .
    - docker push $DOCKER_IMAGE/agent:$CI_COMMIT_SHA
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_TAG

build-helm:
  stage: build
  image: alpine/helm:3.13
  script:
    - helm package deploy/helm/docflow --version $CI_COMMIT_SHA
    - |
      curl --request POST \
        --form "chart=@docflow-$CI_COMMIT_SHA.tgz" \
        --user gitlab-ci-token:$CI_JOB_TOKEN \
        $HELM_REPO
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_TAG

# === Security Stage ===
trivy-scan:
  stage: security
  image: aquasec/trivy:latest
  script:
    - trivy image --exit-code 1 --severity HIGH,CRITICAL $DOCKER_IMAGE/api:$CI_COMMIT_SHA
    - trivy image --exit-code 1 --severity HIGH,CRITICAL $DOCKER_IMAGE/agent:$CI_COMMIT_SHA
  allow_failure: true
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# === Deploy Stage ===
deploy-stage:
  stage: deploy-stage
  image: alpine/k8s:1.28
  environment:
    name: stage
    url: https://docflow-stage.example.com
  before_script:
    - aws eks update-kubeconfig --name docflow-stage --region us-east-1
  script:
    - |
      helm upgrade --install docflow $HELM_REPO/docflow-$CI_COMMIT_SHA.tgz \
        --namespace docflow-stage \
        --values deploy/helm/docflow/values-stage.yaml \
        --set image.tag=$CI_COMMIT_SHA \
        --wait --timeout 10m
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# === Integration Tests ===
integration-test:
  stage: integration-test
  image: python:3.11
  environment:
    name: stage
  script:
    - pip install -e ".[dev]"
    - pytest tests/integration/ --env=stage
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# === Production Deploy (Blue/Green) ===
deploy-prod-blue:
  stage: deploy-prod
  image: alpine/k8s:1.28
  environment:
    name: prod-blue
    url: https://docflow.example.com
  before_script:
    - aws eks update-kubeconfig --name docflow-prod --region us-east-1
  script:
    - |
      # Deploy to blue (inactive)
      helm upgrade --install docflow-blue $HELM_REPO/docflow-$CI_COMMIT_SHA.tgz \
        --namespace docflow-prod \
        --values deploy/helm/docflow/values-prod.yaml \
        --set image.tag=$CI_COMMIT_SHA \
        --set blueGreen.enabled=true \
        --set blueGreen.activeColor=blue \
        --wait --timeout 10m
      
      # Run smoke tests against blue
      kubectl run smoke-test --rm -it --restart=Never \
        --namespace docflow-prod \
        --image=$DOCKER_IMAGE/api:$CI_COMMIT_SHA \
        -- pytest tests/smoke/ --env=prod-blue
  rules:
    - if: $CI_COMMIT_TAG
  when: manual

switch-to-blue:
  stage: deploy-prod
  image: alpine/k8s:1.28
  needs: [deploy-prod-blue]
  script:
    - |
      # Update service selector to point to blue
      kubectl patch service docflow-api \
        --namespace docflow-prod \
        -p '{"spec":{"selector":{"docflow.io/color":"blue"}}}'
      
      # Verify traffic is flowing
      sleep 30
      kubectl run verify --rm -it --restart=Never \
        --namespace docflow-prod \
        --image=curlimages/curl \
        -- curl -f http://docflow-api/health
  environment:
    name: production
    url: https://docflow.example.com
  rules:
    - if: $CI_COMMIT_TAG
  when: manual

rollback-to-green:
  stage: deploy-prod
  image: alpine/k8s:1.28
  script:
    - |
      kubectl patch service docflow-api \
        --namespace docflow-prod \
        -p '{"spec":{"selector":{"docflow.io/color":"green"}}}'
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_TAG
  when: manual

# === Release ===
publish-pypi:
  stage: deploy-prod
  image: python:3.11
  script:
    - pip install build twine
    - python -m build
    - TWINE_PASSWORD=${CI_JOB_TOKEN} TWINE_USERNAME=gitlab-ci-token
      python -m twine upload --repository-url ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/pypi dist/*
  rules:
    - if: $CI_COMMIT_TAG
```

### GitHub Actions (For Open Source)

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_DB: test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          
      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test
        run: |
          pytest tests/ --cov=docflow --cov-report=xml
          
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: coverage.xml

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: |
          pip install ruff mypy
          ruff check src/
          mypy src/docflow

  build:
    needs: [test, lint]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      
    steps:
      - uses: actions/checkout@v4
      
      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=ref,event=tag
            type=raw,value=latest,enable={{is_default_branch}}
            
      - name: Build and push API image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.api
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}

  publish-pypi:
    needs: [build]
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # For trusted publishing
      
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Build package
        run: |
          pip install build
          python -m build
          
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

---

## 8. Open Source Preparation

### Content Scrubbing Script

```python
#!/usr/bin/env python3
"""
scrub_for_oss.py

Scrub UT Nuclear Engineering references for open source release.
Replaces with generic "Medical Research" equivalents.
"""

import re
import os
from pathlib import Path
from typing import Dict, List

# Replacement mappings
REPLACEMENTS: Dict[str, str] = {
    # Organizations
    r"UT Nuclear Engineering": "Medical Research Institute",
    r"University of Texas Nuclear Engineering": "Medical Research Institute",
    r"UT Computational NE": "Computational Research Lab",
    r"NETL": "Research Laboratory",
    r"Nuclear Engineering Teaching Laboratory": "Medical Research Laboratory",
    
    # Projects
    r"TRIGA": "Research Reactor",
    r"bubble[_\s]?flow[_\s]?loop": "flow_loop",
    r"Bubble Flow Loop": "Flow Loop",
    r"MSR": "System",
    r"Molten Salt Reactor": "Research System",
    r"MIT Irradiation Loop": "Irradiation System",
    
    # Technical terms (context-dependent)
    r"nuclear\s+engineer": "research engineer",
    r"Nuclear\s+Engineer": "Research Engineer",
    r"reactor\s+physics": "system physics",
    r"neutronics": "particle transport",
    
    # People patterns (anonymize)
    r"@ben\b": "@researcher1",
    r"@alice\b": "@researcher2",
    r"@bob\b": "@researcher3",
    
    # Specific files/paths
    r"triga_": "research_",
    r"msr_": "system_",
    r"netl_": "lab_",
}

# Files to skip
SKIP_PATTERNS = [
    r"\.git/",
    r"node_modules/",
    r"__pycache__/",
    r"\.pyc$",
    r"\.egg-info/",
    r"dist/",
    r"build/",
    r"\.env",
    r"scrub_for_oss\.py",  # Don't scrub this file
]

# File extensions to process
PROCESS_EXTENSIONS = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".json", ".toml",
    ".sql", ".sh", ".ts", ".js", ".html", ".css", ".tf", ".hcl"
}


def should_skip(path: Path) -> bool:
    """Check if file should be skipped"""
    path_str = str(path)
    return any(re.search(pattern, path_str) for pattern in SKIP_PATTERNS)


def should_process(path: Path) -> bool:
    """Check if file should be processed"""
    return path.suffix.lower() in PROCESS_EXTENSIONS


def scrub_content(content: str) -> tuple[str, List[str]]:
    """
    Apply replacements to content.
    Returns (scrubbed_content, list_of_changes)
    """
    changes = []
    result = content
    
    for pattern, replacement in REPLACEMENTS.items():
        matches = list(re.finditer(pattern, result, re.IGNORECASE))
        if matches:
            for match in matches:
                changes.append(f"  {match.group()} -> {replacement}")
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result, changes


def scrub_file(path: Path, dry_run: bool = True) -> List[str]:
    """Scrub a single file"""
    try:
        content = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return []
    
    scrubbed, changes = scrub_content(content)
    
    if changes:
        if not dry_run:
            path.write_text(scrubbed, encoding='utf-8')
        return [f"{path}:"] + changes
    
    return []


def scrub_directory(root: Path, dry_run: bool = True) -> None:
    """Scrub all files in directory"""
    all_changes = []
    
    for path in root.rglob("*"):
        if path.is_file() and not should_skip(path) and should_process(path):
            changes = scrub_file(path, dry_run)
            all_changes.extend(changes)
    
    # Report
    if all_changes:
        print(f"{'[DRY RUN] ' if dry_run else ''}Changes:")
        for change in all_changes:
            print(change)
        print(f"\nTotal: {len([c for c in all_changes if c.startswith('  ')])} replacements")
    else:
        print("No changes needed")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrub content for open source release")
    parser.add_argument("path", type=Path, help="Directory to scrub")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    parser.add_argument("--check", action="store_true", help="Exit with error if changes needed")
    
    args = parser.parse_args()
    
    if not args.path.exists():
        print(f"Error: {args.path} does not exist")
        return 1
    
    dry_run = not args.apply
    scrub_directory(args.path, dry_run=dry_run)
    
    if args.check and dry_run:
        # Re-run to check if any changes would be made
        changes_needed = False
        for path in args.path.rglob("*"):
            if path.is_file() and not should_skip(path) and should_process(path):
                if scrub_file(path, dry_run=True):
                    changes_needed = True
                    break
        
        if changes_needed:
            print("\nError: Unscrubbed content found")
            return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
```

### Pre-Commit Hook

```yaml
# .pre-commit-config.yaml

repos:
  - repo: local
    hooks:
      - id: scrub-check
        name: Check for unscrubbed content
        entry: python scripts/scrub_for_oss.py . --check
        language: python
        pass_filenames: false
        stages: [commit]
```

### License

```
# LICENSE (Apache 2.0)

Copyright 2026 Neutron OS Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### Open Source Checklist

```markdown
# Open Source Release Checklist

## Legal & Compliance
- [ ] Review with UT Technology Transfer office
- [ ] Confirm Apache 2.0 license is acceptable
- [ ] Review contributor license agreement (CLA) requirements
- [ ] Check for any export control concerns

## Content Scrubbing
- [ ] Run scrub script: `python scripts/scrub_for_oss.py . --apply`
- [ ] Manual review of examples/ directory
- [ ] Replace all real names in documentation
- [ ] Review commit history for sensitive content
  - If needed, use `git filter-repo` to clean history
- [ ] Update all screenshots/images

## Documentation
- [ ] Write public README.md
- [ ] Write CONTRIBUTING.md
- [ ] Write SECURITY.md
- [ ] Write CODE_OF_CONDUCT.md
- [ ] Create example projects with generic data
- [ ] Update API documentation

## Repository Setup
- [ ] Create github.com/neutron-os organization
- [ ] Set up branch protection rules
- [ ] Configure GitHub Actions secrets
- [ ] Set up issue templates
- [ ] Set up PR templates
- [ ] Configure CODEOWNERS

## Package Publishing
- [ ] Reserve package name on PyPI
- [ ] Set up trusted publishing
- [ ] Reserve extension name on VS Code Marketplace
- [ ] Set up JetBrains plugin signing

## Announcement
- [ ] Draft blog post
- [ ] Prepare social media announcement
- [ ] Notify relevant communities
```

---

## 9. Quick Reference

### Local Development Commands

```bash
# Start local cluster
cd deploy/k3d && make create-cluster

# Deploy everything
make deploy-all

# View logs
make logs-api
make logs-agent

# Run local tests
make test-local

# Tear down
make delete-cluster
```

### Infrastructure Commands

```bash
# Initialize Terraform
cd deploy/terraform/environments/stage
terraform init

# Plan changes
terraform plan -out=plan.tfplan

# Apply changes
terraform apply plan.tfplan

# Deploy to stage
helm upgrade --install docflow deploy/helm/docflow \
  --namespace docflow-stage \
  --values deploy/helm/docflow/values-stage.yaml
```

### Release Process

```bash
# 1. Tag release
git tag -a v1.0.0 -m "Release 1.0.0"
git push origin v1.0.0

# 2. CI automatically:
#    - Runs tests
#    - Builds images
#    - Pushes to registry
#    - Creates Helm package

# 3. Deploy to stage (automatic)

# 4. Deploy to prod (manual trigger in GitLab)
#    - Blue deployment first
#    - Manual switch after validation
```

### Emergency Rollback

```bash
# Immediate rollback via service switch
kubectl patch service docflow-api \
  --namespace docflow-prod \
  -p '{"spec":{"selector":{"docflow.io/color":"green"}}}'

# Or rollback Helm release
helm rollback docflow 1 --namespace docflow-prod
```

---

## Next Steps

1. **Immediate**: Set up K3D local environment
2. **Week 1**: Configure GitLab CI pipeline  
3. **Week 2**: Set up stage environment on AWS
4. **Week 3**: Deploy to stage, run integration tests
5. **Week 4**: Set up prod with blue/green
6. **Ongoing**: Prepare for open source release

For questions or issues, contact the infrastructure team or open an issue in the repository.
