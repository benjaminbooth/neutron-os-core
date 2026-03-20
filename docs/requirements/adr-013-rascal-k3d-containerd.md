# ADR-013: Rascal Server Environment Uses k3d + containerd

**Status:** Proposed
**Date:** 2026-03-20
**Decision Makers:** Ben, Team

## Context

Rascal is a beefy physical server at UT Austin sized for self-hosted LLM experimentation. It provides GPU compute and real disk not available in a developer laptop environment. Rascal sits behind UT VPN (a different VPN profile from any future TACC deployment). Rascal is **not** an export-controlled (EC) authorized computing environment; that role belongs to TACC and is a future concern. Rascal's purpose is to validate the restricted-tier (no-cloud LLM) architecture and serve as a staging environment before any TACC deployment is designed.

**Hardware:** NVIDIA RTX PRO 6000 Blackwell (97GB VRAM), 500GB RAM, 3.3TB `/home`, 19TB `/natura`.

**LLM runtime:** `llama-server` (llama.cpp) runs directly on the host — **not** in-cluster. It currently serves `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` (122B MoE / ~10B active parameters, 256K context window) on port 41883 with TLS and API key authentication. The endpoint is OpenAI-compatible (`/v1`). The GPU is fully allocated to this process; no in-cluster Ollama is deployed.

The k3d cluster (this ADR) hosts everything **except** the LLM: PostgreSQL (pgvector), the neut signal server, and future platform services. The neut gateway reaches llama-server at `https://rascal.austin.utexas.edu:41883/v1` over the host network.

The existing local development environment deploys PostgreSQL, Ollama, and related services via k3d (k3s in Docker) with a Helm chart defined in `infra/environments/local/`. A third environment — a future TACC HPC deployment — is anticipated but not yet designed.

Four capabilities are blocked without a real server environment:

1. **Self-hosted LLM validation** — Qwen on Rascal is the target deployment for the restricted tier (no-cloud) and for Ondrej's first deployment. The end-to-end path (VS Code → Neut → Qwen on Rascal → RAG) has not been exercised on real hardware.
2. **GPU-backed Ollama** — Ollama 0.18.x has a Metal GPU backend bug on macOS that prevents using `nomic-embed-text` locally. GPU embedding development is blocked without real server hardware.
3. **Network-accessible service endpoints** — service endpoints accessible from a developer machine over the network cannot be validated from a local container environment.
4. **PVC provisioning** — real disk behaviour (storage classes, performance, failure modes) cannot be observed in a local container environment.

## Decision

The Rascal EC staging environment will deploy the same Helm chart as the local development environment, using **k3d on containerd** (not Docker). A new Terraform target `infra/environments/rascal/` provides Rascal-specific value overrides.

The k3d cluster on Rascal is named `rascal-ec` to distinguish it from any local development clusters.

## Alternatives Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **k3d + containerd (this ADR)** | Reuses existing Helm chart; containerd is smaller attack surface; no Docker daemon socket; aligns with TACC runtime | One-time k3d + containerd setup on Rascal (~2 hours) | ✅ Selected |
| **k3d + Docker** | Matches existing local dev exactly | Docker daemon socket is a privileged attack surface; diverges from TACC runtime; Docker not present on hardened Rascal | ❌ |
| **Raw systemd services** | No container runtime to install | Entirely different deployment topology; diverges from local and TACC; duplicates all configuration | ❌ |
| **Docker Compose on Rascal** | Simple, familiar | Same Docker daemon concerns; not path-compatible with TACC; diverges from Helm chart | ❌ |
| **Full k8s (kubeadm)** | Closer to production k8s | Substantial operational overhead for a single-node staging machine; not worth it for one server | ❌ |

## Consequences

### Positive

- **Environments stay converged.** Local, Rascal, and TACC are three instantiations of the same Helm chart, not three separate designs. Rascal-specific values are isolated to `infra/environments/rascal/`.
- **Rascal becomes a real staging gate.** Issues discovered on Rascal — storage class behaviour, network routing, Helm chart gaps — get fixed before any TACC deployment is attempted.
- **Ondrej's deployment path is validated.** The VS Code → Neut → Qwen (Rascal) → RAG path exercises exactly what an external operator deployment looks like on real hardware.
- **GPU-backed Ollama unblocks embedding development.** `nomic-embed-text` runs on Rascal GPU, working around the Ollama macOS Metal bug.
- **containerd aligns with TACC.** TACC environments use containerd or Podman, not Docker. Using containerd on Rascal validates that assumption early without requiring TACC access.

### Negative

- Requires installing k3d and containerd on Rascal — one-time setup, estimated ~2 hours.
- Adds `infra/environments/rascal/` directory with Helm values to maintain alongside local and future TACC targets.

## Implementation

### Directory Layout

```
infra/
├── environments/
│   ├── local/          # existing local dev target (unchanged)
│   ├── rascal/         # NEW — Rascal EC staging (this ADR)
│   │   ├── main.tf
│   │   └── values.yaml # Helm overrides: node resources, storage class,
│   │                   #   network policy, GPU requests for Ollama
│   └── tacc/           # future third environment (stub; not yet designed)
```

### Rascal-Specific Value Overrides (`infra/environments/rascal/values.yaml`)

| Parameter | Local value | Rascal override |
|-----------|-------------|-----------------|
| Storage class | `local-path` (k3d default) | Rascal SSD storage class |
| Ollama resource requests | CPU only | GPU resource request added |
| Service endpoints | localhost | UT VPN-accessible endpoints (`vpn_profile = "ut-rascal"`) |
| Node resources | Developer laptop limits | Rascal server limits |

### Cluster Name

```bash
k3d cluster create rascal \
  --runtime containerd \
  ...
```

The cluster name `rascal` must be used consistently in kubeconfig, Terraform state, and CI references to prevent confusion with local clusters.

### Environment Progression

```
infra/environments/local/   (developer laptop, k3d + containerd)
  ↓  same Helm chart, Rascal values override
infra/environments/rascal/  (physical server, k3d + containerd, GPU, Qwen)
  ↓  same Helm chart, TACC values override
infra/environments/tacc/    (future TACC HPC deployment)
```

Issues discovered at each stage are fixed before progressing. Rascal is the mandatory staging gate before any TACC deployment is attempted.

## References

- [k3d documentation](https://k3d.io/)
- [k3d containerd runtime](https://k3d.io/v5.6.0/usage/runtimes/)
- ADR-012 (`adr-012-provider-identity.md`) — provider identity model used by services deployed in this environment
