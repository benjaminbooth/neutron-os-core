# Neutron OS

**Nuclear Energy Unified Technology for Research, Operations & Networks**

A polyglot platform providing infrastructure, data lakehouse, immutable audit layer, and shared services for nuclear research and operations.

## Overview

Neutron OS is the foundational platform that supports:
- **TRIGA Digital Twin** - UT NETL reactor operations and research
- **MSR Digital Twin** - Molten salt reactor simulations
- **MIT Irradiation Loop** - Experiment analysis
- **OffGas Digital Twin** - Off-gas system modeling
- **Future facilities** - Multi-facility blockchain network ready

## Key Features

- **Data Lakehouse** - Apache Iceberg + DuckDB + Superset (Bronze/Silver/Gold tiers)
- **Immutable Audit** - Hyperledger Fabric for multi-facility consensus
- **Test-Driven Analytics** - Superset scenarios drive data model design
- **Meeting Intake** - LangGraph + Anthropic pipeline for requirements extraction
- **Polyglot Build** - Bazel supporting Python, TypeScript, C, Go, Mojo

## Repository Structure

```
Neutron_OS/
├── docs/                 # Architecture, PRDs, specs, scenarios
├── infra/                # Terraform, Helm, K3D (paused until hosting decision)
├── data/                 # Iceberg schemas, dbt, Dagster, Superset
├── blockchain/           # Hyperledger Fabric network and chaincode
├── packages/             # Shared libraries (schemas, Python, TS)
├── tools/                # Meeting intake, dev utilities
├── services/             # Backend services (stub)
├── plugins/              # Reactor-specific plugins (stub)
└── frontend/             # React + Vite + TS app (stub)
```

## Infrastructure Standards

| ✅ Use | ❌ Avoid |
|--------|----------|
| Terraform | Vendor-specific IaC |
| Kubernetes (K3D local) | Docker-Compose |
| Helm | Manual manifests |
| Bazel | Single-language build tools |
| S3-compatible storage | Provider-locked storage |

## Quick Start

```bash
# Prerequisites: Bazel, K3D, Helm, Terraform

# Local development cluster (once infra is ready)
cd infra/k3d && k3d cluster create --config cluster-config.yaml

# Run tests
bazel test //...
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, git practices, and .gitignore conventions.

## Related Repositories

- [TRIGA_Digital_Twin](../TRIGA_Digital_Twin) - NETL reactor portal and simulations
- [MSR_Digital_Twin_Open](../MSR_Digital_Twin_Open) - Molten salt reactor analysis
- [MIT_Irradiation_Loop_Digital_Twin](../MIT_Irradiation_Loop_Digital_Twin) - Irradiation experiments

## License

Apache 2.0
