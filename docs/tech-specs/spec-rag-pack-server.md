# RAG Pack Server & Generation Pipeline — Neutron OS Nuclear Extensions

> The core specification is provided by the Axiom platform. This document defines nuclear-domain extensions only.

**Upstream:** [Axiom RAG Pack Server Spec](https://github.com/…/axiom/docs/tech-specs/spec-rag-pack-server.md)

---

## Nuclear Extensions

### Deployment Profiles

NeutronOS instantiates the three Axiom deployment profiles with nuclear-specific infrastructure:

| Axiom Profile | NeutronOS Instance | Infrastructure |
|--------------|-------------------|---------------|
| Private-Server (restricted) | **Rascal** | UT Austin physical server, VPN-gated, k3d cluster |
| PrivateCloud (export-controlled) | **TACC** | Texas Advanced Computing Center HPC allocation, EAR/10 CFR 810 controls |
| Community CDN (future) | Same | S3/R2, public domain packs from `community_facts` |

### Pack Format

NeutronOS uses `.neutpack` as the pack file extension (vs. Axiom's `.axiompack`).

### First Pack

The first generated pack is `netl-triga` — NETL TRIGA facility procedures, safety analysis, and operational history.

### Helm Values Files

- `values-rascal.yaml` — Rascal k3d SeaweedFS configuration (bucket: `neut-packs`)
- `values-tacc.yaml` — TACC allocation SeaweedFS (200Gi persistence for EC corpora)
