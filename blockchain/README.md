# Blockchain (Hyperledger Fabric)

Multi-facility immutable audit layer for Neutron OS.

## Overview

Hyperledger Fabric provides:
- Cryptographic immutability for audit trails
- Multi-organization consensus
- Permissioned access (not public blockchain)
- Smart contracts (chaincode) for audit rules

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 HYPERLEDGER FABRIC NETWORK                  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  UT NETL     │  │  Facility 2  │  │  Facility N  │      │
│  │  (TRIGA)     │  │  (Future)    │  │  (Future)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  Channels: audit-channel (all), isotope-channel (subset)   │
└─────────────────────────────────────────────────────────────┘
```

## Structure

```
blockchain/
├── network/
│   ├── configtx.yaml           # Channel configuration
│   ├── crypto-config.yaml      # Organization certificates
│   └── organizations/
│       └── ut-netl/            # First organization
│
├── chaincode/
│   ├── audit/                  # Audit trail chaincode
│   │   └── go/
│   └── log/                    # Log entry chaincode
│       └── go/
│
└── sdk/
    ├── python/                 # Python client
    └── typescript/             # TypeScript client
```

## Chaincode

### Audit Chaincode
- Log all audit events
- Verify inclusion proofs
- Generate evidence manifests

### Log Chaincode
- Immutable operator log entries
- Entry amendments (append-only)
- Signature verification

## Development

For local development, Fabric network runs in Docker containers (exception to no-Docker-Compose rule, as this is Fabric's official dev setup).

Production deployment uses Kubernetes via Hyperledger Bevel.

## Status

**Pending** - Will implement after data platform foundation is established.
