# ADR-013: Rascal Server Environment Uses k3d + containerd — Neutron OS Nuclear Context

> This architecture decision is made at the Axiom platform level. This document captures nuclear-specific context only.

**Upstream:** [Axiom adr-013-rascal-k3d-containerd.md](https://github.com/…/axiom/docs/requirements/adr-013-rascal-k3d-containerd.md)

---

## Nuclear Context

### Rascal: UT Nuclear Engineering Staging Server

Rascal is a physical server at UT Austin sized for self-hosted LLM experimentation. It sits behind UT VPN (a different VPN profile from any future TACC deployment). Rascal is **not** an export-controlled (EC) authorized computing environment; that role belongs to TACC.

**Hardware:** NVIDIA RTX PRO 6000 Blackwell (97GB VRAM), 500GB RAM, 3.3TB `/home`, 19TB `/natura`.

**LLM runtime:** `llama-server` (llama.cpp) runs directly on the host serving `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` (122B MoE / ~10B active parameters, 256K context window) on port 41883 with TLS and API key authentication. The endpoint is OpenAI-compatible (`/v1`). The GPU is fully allocated to this process; no in-cluster Ollama is deployed.

The k3d cluster hosts everything **except** the LLM: PostgreSQL (pgvector), the neut signal server, and future platform services. The neut gateway reaches llama-server at `https://rascal.austin.utexas.edu:41883/v1` over the host network.

### Blocked Capabilities

1. **Self-hosted LLM validation** — Qwen on Rascal is the target deployment for the restricted tier (no-cloud) and for Ondrej's first deployment. The end-to-end path (VS Code -> Neut -> Qwen on Rascal -> RAG) has not been exercised on real hardware.
2. **GPU-backed Ollama** — Ollama 0.18.x has a Metal GPU backend bug on macOS that prevents using `nomic-embed-text` locally.
3. **Network-accessible service endpoints** — cannot be validated from a local container environment.
4. **PVC provisioning** — real disk behaviour cannot be observed locally.

### Environment Progression (NeutronOS)

```
infra/environments/local/   (developer laptop, k3d + containerd)
  |  same Helm chart, Rascal values override
infra/environments/rascal/  (physical server, k3d + containerd, GPU, Qwen)
  |  same Helm chart, TACC values override
infra/environments/tacc/    (future TACC HPC deployment)
```

Rascal is the mandatory staging gate before any TACC deployment is attempted.

### Rascal-Specific Value Overrides (`infra/environments/rascal/values.yaml`)

| Parameter | Local value | Rascal override |
|-----------|-------------|-----------------|
| Storage class | `local-path` (k3d default) | Rascal SSD storage class |
| Ollama resource requests | CPU only | GPU resource request added |
| Service endpoints | localhost | UT VPN-accessible endpoints (`vpn_profile = "ut-rascal"`) |
| Node resources | Developer laptop limits | Rascal server limits |

### TACC Alignment

containerd (not Docker) aligns with TACC environments which use containerd or Podman. Using containerd on Rascal validates that assumption early without requiring TACC access.
