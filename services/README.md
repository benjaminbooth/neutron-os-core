# Services

Backend services for Neutron OS.

## Status

**Stub** - Will be implemented in later phases.

## Planned Services

| Service | Purpose | Technology |
|---------|---------|------------|
| `neutron-api` | REST API gateway | FastAPI |
| `neutron-gateway` | BFF for frontend | FastAPI |
| `neutron-log` | Unified Log service | FastAPI + Fabric |
| `neutron-auth` | Auth proxy | Keycloak adapter |

## Structure (Planned)

```
services/
├── neutron-api/
│   ├── pyproject.toml
│   ├── neutron_api/
│   │   ├── routes/
│   │   ├── middleware/
│   │   └── schemas/
│   └── tests/
│
├── neutron-gateway/
│   └── ...
│
└── neutron-log/
    └── ...
```
