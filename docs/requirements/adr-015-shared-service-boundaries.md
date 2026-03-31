# ADR-015: Shared Service Boundaries Between Axiom and NeutronOS

**Status:** Accepted
**Date:** 2026-03-31
**Authors:** Benjamin Booth, Claude

## Context

Axiom is a domain-agnostic framework. NeutronOS is a nuclear-domain extension layer
built on axiom. Both depend on shared infrastructure (PostgreSQL, LLM providers,
object storage, observability) but must remain independently deployable and evolvable.

This ADR codifies the ownership model for shared services and the contract between
axiom (framework) and NeutronOS (domain layer).

## Decision

### Adopt First, Provision Second

The axiom installer (`axi infra`) MUST prefer discovering and reusing existing
shared resources over provisioning new instances. For every managed dependency
(PostgreSQL, LLM runtime, object storage), the installer follows this sequence:

1. **Discover** — probe for existing instances (localhost, local network, config)
2. **Verify** — check against minimum operating criteria defined by axiom
3. **Upgrade** — if below minimum but fixable, request permission, upgrade non-destructively
4. **Provision** — only if nothing suitable found, install fresh

The installer MUST have or request sufficient permissions to verify and upgrade
existing resources (e.g., `CREATE EXTENSION` on PostgreSQL, model pull on Ollama).
If permissions are insufficient, it reports the specific gap and remediation steps
rather than failing silently or forcing a parallel install.

NeutronOS may raise minimum criteria (e.g., require specific pgvector version for
export-controlled embeddings, or a minimum model context window for nuclear
document synthesis) but may never lower axiom's floors.

### Ownership Model

Every shared resource has exactly **one owner** and **zero or more consumers**.
The owner controls schema, lifecycle, and configuration. Consumers connect via
environment variables and must tolerate the resource being absent (graceful degradation).

| Resource | Owner | Consumers | Connection Contract |
|----------|-------|-----------|-------------------|
| PostgreSQL server | Infrastructure (Helm/Terraform) | axiom, NeutronOS | `*_DB_URL` env var per database |
| axiom database (`axiom_db`) | axiom (Alembic migrations) | axiom extensions only | `AXIOM_DB_URL` |
| NeutronOS database (`neut_db`) | NeutronOS (Alembic migrations) | NeutronOS extensions only | `NEUT_DB_URL` |
| LLM gateway | axiom (`axiom.infra.gateway`) | All extensions | `llm-providers.toml` + provider identity |
| LLM runtime (local SLM/LLM) | axiom (`axiom.infra.llm_runtime`) | axiom gateway | Managed by axiom installer; BYOI fallback via `localEndpoint` |
| Object storage (SeaweedFS/S3) | Infrastructure (Helm/Terraform) | RAG pack server, media library | `AXIOM_S3_ENDPOINT` env var |
| Keystore | axiom (`axiom.infra.keystore`) | All services | K8s Secrets API; cloud SM/KV via CSI driver |
| Observability (log sinks) | axiom (`axiom.infra.log_sinks`) | All extensions | `runtime/config/logging.toml` |
| IAM (auth + authz) | axiom (`axiom.infra.iam`) | All services | OAuth 2.0/OIDC + OpenFGA; single-user mode requires no config |
| Data platform (Iceberg + dbt + Dagster) | axiom (`axiom.data`) | NeutronOS extensions | Capability manifest declares data platform requirements |
| Streaming (Kafka) | Infrastructure (Helm) | axiom data platform, NeutronOS | Kafka wire protocol; disabled at Minimal/Small sizes |

### Infrastructure-as-Code Layering

All infrastructure is defined as code using two layers:

- **Terraform** provisions the platform: Kubernetes cluster (K3D locally, EKS /
  GKE / AKS in cloud), managed databases, object storage, networking, IAM.
  Reusable modules live in axiom's `infra/terraform/modules/`. NeutronOS imports
  these modules in its own `infra/terraform/environments/` and adds
  domain-specific resources (e.g., compliance audit buckets).

- **Helm** deploys workloads into the cluster Terraform created: application
  pods, services, configmaps, secrets. The unified Helm chart works identically
  on K3D and cloud-managed Kubernetes.

Terraform outputs (e.g., RDS endpoint) feed Helm values (e.g.,
`externalDatabase.host`), bridging the two layers automatically.

### Database Isolation Rules

1. **One PostgreSQL server, separate databases.** axiom and NeutronOS MUST NOT share
   a database. Each has its own Alembic migration chain and connection URL.

2. **No cross-database foreign keys.** Extensions communicate via events and APIs,
   never via shared tables or direct SQL joins.

3. **Each extension owns its tables.** The `eve_agent` extension (axiom) owns
   `signals`, `media`, `participants`, `people`. NeutronOS audit extensions own
   `routing_events`, `classification_events`, etc. No other extension may write
   to another extension's tables.

4. **pgvector is axiom's concern.** Only axiom extensions use vector embeddings.
   NeutronOS extensions that need vector search should use axiom's RAG
   infrastructure rather than creating parallel pgvector schemas.

### LLM Gateway Contract

1. The LLM gateway (`axiom.infra.gateway`) is the **sole entry point** for all LLM
   calls from any extension in either repo.

2. Provider configuration lives in `llm-providers.toml` (runtime config, gitignored).
   The gateway resolves provider selection, handles VPN-gated routing, and enforces
   export control tiers.

3. **The LLM runtime is an axiom-managed dependency.** The axiom installer
   (`axi infra`) agentically discovers the operating environment (GPU availability,
   VRAM, network topology, existing LLM endpoints) and provisions the appropriate
   runtime (Ollama, llama-server, or cloud API). Operators may bring their own
   infrastructure via `localEndpoint` override, but the default path is fully managed.

4. See axiom's `prd-managed-infrastructure.md` and `spec-managed-infrastructure.md` for the full lifecycle.
   NeutronOS inherits this capability — no NeutronOS-specific LLM provisioning needed.

### Container Image Strategy

1. **Base image** (`axiom-base:py3.12`): python:3.12-slim + system deps + locked
   Python deps. Rebuilt only when `pyproject.toml` changes.

2. **NeutronOS app images** (signal, api): FROM axiom-base, add NeutronOS source,
   `pip install -e .`. Rebuilt on every code change (~seconds with cached base).

3. **CI images**: Use the same base image for test/build jobs to eliminate
   dependency installation time in pipelines.

4. **LLM image**: Separate lifecycle entirely. Ollama/llama-server images are
   pulled from upstream, not built by our CI.

### Extension Contract

Any NeutronOS extension that needs a database MUST:
1. Declare its own SQLAlchemy `Base` and models in its extension directory
2. Maintain its own Alembic migration chain
3. Use `NEUT_DB_URL` (or a dedicated URL if isolation is needed)
4. Never import models from axiom extensions — use the event bus or API calls

Any NeutronOS extension that needs an LLM MUST:
1. Use `axiom.infra.gateway` — never call LLM APIs directly
2. Declare its provider requirements in its `neut-extension.toml`
3. Respect export control tiers from the gateway's routing decisions

## Consequences

- NeutronOS extensions can be developed, tested, and deployed independently of axiom
- Database migrations never conflict between axiom and NeutronOS
- LLM provider changes (new model, endpoint swap) require zero NeutronOS code changes
- Infrastructure team can upgrade PostgreSQL or swap LLM runtime without coordinating
  with NeutronOS extension developers
- The base image strategy eliminates ~30-60s of dependency installation per CI job
  and per container build

## NeutronOS-Specific TODOs

- [ ] Wire `NEUT_DB_URL` into Helm values → configmap → pod env
- [ ] Complete Alembic infrastructure (`env.py`, `alembic.ini`) for audit tables
- [ ] Add `helm upgrade` CD job to GitLab CI for dev environment
- [ ] Define NeutronOS operator guide (audience: nuclear facility IT staff)
