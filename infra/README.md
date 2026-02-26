# Infrastructure

Infrastructure-as-Code for NeutronOS deployment.

## Status

**🟢 ACTIVE** - Local development infrastructure ready. Cloud pending hosting decision.

## Standards

| ✅ Use | ❌ Avoid |
|--------|----------|
| Terraform | CloudFormation, ARM, Pulumi |
| Kubernetes | Docker Swarm, Nomad |
| Helm | Raw manifests only |
| K3D (local) | Docker-Compose, Minikube |
| S3-compatible | Provider-locked storage |
| pgvector | Separate vector DBs |

## Structure

```
infra/
├── README.md              # This file
├── terraform/
│   └── modules/           # Reusable Terraform modules
│       └── rds-pgvector/  # PostgreSQL + pgvector for Sense RAG
│
├── helm/
│   └── charts/
│       └── neutron-os/    # Unified NeutronOS Helm chart
│           ├── Chart.yaml
│           ├── values.yaml
│           ├── values-local.yaml   # K3D overrides
│           └── templates/
│               ├── _helpers.tpl
│               ├── sense-deployment.yaml
│               ├── service.yaml
│               └── configmap.yaml
│
└── k3d/                   # (future) K3D cluster config
    └── cluster-config.yaml
```

## Quick Start (Local Development)

### Option A: Automated Setup (Recommended)

```bash
# From repo root
neut setup
# Follow prompts; select "yes" for infrastructure setup
```

This uses `tools/agents/setup/infra.py` to:
- Start Docker if not running
- Create K3D cluster "neut"
- Deploy PostgreSQL with pgvector
- Wait for pods to be ready

### Option B: Manual Helm Install

```bash
# Create K3D cluster
k3d cluster create neut --port "8765:8765@loadbalancer"

# Install NeutronOS chart
cd infra/helm/charts/neutron-os
helm install neut . -f values-local.yaml

# Verify
kubectl get pods -n default
```

### Accessing Services

```bash
# Port-forward Sense server
kubectl port-forward svc/neut-sense 8765:8765

# Port-forward PostgreSQL (for debugging)
kubectl port-forward svc/neut-postgresql 5432:5432

# Access Sense
curl http://localhost:8765/status
```

## Terraform Modules

### rds-pgvector

PostgreSQL RDS instance with pgvector extension for Sense RAG.

```hcl
module "database" {
  source = "./modules/rds-pgvector"
  
  name        = "neutron-os"
  environment = "prod"
  vpc_id      = module.vpc.vpc_id
  subnet_group_name = module.vpc.database_subnet_group_name
  
  instance_class    = "db.t3.medium"
  allocated_storage = 50
  multi_az          = true
}
```

**Outputs:**
- `connection_string` - Full PostgreSQL connection URL
- `endpoint` - RDS endpoint
- `security_group_id` - For allowing ingress

## Helm Chart: neutron-os

Unified chart for all NeutronOS services.

### Components

| Component | Port | Description |
|-----------|------|-------------|
| `sense` | 8765 | Signal processing, RAG, Media Library, WebSocket |
| `api` | 8000 | REST gateway (future) |
| `postgresql` | 5432 | pgvector database (bundled or external) |

### Values Files

| File | Use Case |
|------|----------|
| `values.yaml` | Default/production |
| `values-local.yaml` | K3D local development |
| `values-stage.yaml` | Staging environment (future) |

### Key Configuration

```yaml
# Use bundled PostgreSQL (local)
postgresql:
  enabled: true

# Use external RDS (production)
postgresql:
  enabled: false
externalDatabase:
  host: "neutron-os-prod.xxx.rds.amazonaws.com"
  existingSecret: "db-credentials"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     K3D Cluster "neut"                      │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │   Sense Pod     │    │      PostgreSQL StatefulSet     │ │
│  │                 │    │                                 │ │
│  │  - RAG queries  │───▶│  - pgvector embeddings         │ │
│  │  - Media index  │    │  - Signal storage              │ │
│  │  - WebSocket    │    │  - Media index                 │ │
│  │                 │    │                                 │ │
│  │  Port: 8765     │    │  Port: 5432                    │ │
│  └─────────────────┘    └─────────────────────────────────┘ │
│          │                                                  │
└──────────│──────────────────────────────────────────────────┘
           │
           ▼
    localhost:8765
    (port-forward or LoadBalancer)
```

## Pending Decisions

1. **Cloud Hosting** - TACC? AWS? Azure? Hybrid?
2. **Storage Backend** - SeaweedFS? MinIO? S3?
3. **Auth** - Keycloak? Auth0? Internal?

## Related Documentation

- [Intelligence Amplification Pillar](../docs/strategy/intelligence-amplification-pillar.md)
- [Design Loop Architecture](../docs/specs/design-loop-architecture.md)
- [Setup Infrastructure Code](../tools/agents/setup/infra.py)
