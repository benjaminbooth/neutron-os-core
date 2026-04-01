# ADR-015: Shared Service Boundaries Between Axiom and NeutronOS — Neutron OS Nuclear Context

> This architecture decision is made at the Axiom platform level. This document captures nuclear-specific context only.

**Upstream:** [Axiom adr-015-shared-service-boundaries.md](https://github.com/…/axiom/docs/requirements/adr-015-shared-service-boundaries.md)

---

## Nuclear Context

### NeutronOS as Domain Extension Layer

NeutronOS is a nuclear-domain extension layer built on Axiom. Both depend on shared infrastructure (PostgreSQL, LLM providers, object storage, observability) but remain independently deployable and evolvable.

NeutronOS may raise minimum criteria beyond Axiom's floors:
- Require specific pgvector version for **export-controlled embeddings**
- Require a minimum model context window for **nuclear document synthesis**
- Never lower Axiom's floors

### NeutronOS Ownership

| Resource | Owner | Connection Contract |
|----------|-------|-------------------|
| NeutronOS database (`neut_db`) | NeutronOS (Alembic migrations) | `NEUT_DB_URL` |
| NeutronOS audit tables | NeutronOS extensions (`routing_events`, `classification_events`, etc.) | Via `neut_db` |

### Database Isolation

- Axiom and NeutronOS MUST NOT share a database — each has its own Alembic migration chain
- The `eve_agent` extension (Axiom) owns `signals`, `media`, `participants`, `people`
- NeutronOS audit extensions own `routing_events`, `classification_events`, etc.
- NeutronOS extensions that need vector search use Axiom's RAG infrastructure, not parallel pgvector schemas

### Extension Contract (NeutronOS-Specific)

Any NeutronOS extension that needs a database MUST:
1. Declare its own SQLAlchemy `Base` and models in its extension directory
2. Maintain its own Alembic migration chain
3. Use `NEUT_DB_URL` (or a dedicated URL if isolation is needed)
4. Never import models from Axiom extensions — use the event bus or API calls

Any NeutronOS extension that needs an LLM MUST:
1. Use `axiom.infra.gateway` — never call LLM APIs directly
2. Declare its provider requirements in its `neut-extension.toml`
3. Respect **export control tiers** from the gateway's routing decisions

### Container Image Strategy

NeutronOS app images (signal, api): `FROM axiom-base`, add NeutronOS source, `pip install -e .`. Rebuilt on every code change (~seconds with cached base).

### Infrastructure-as-Code Layering

NeutronOS imports Axiom's reusable Terraform modules (`axiom/infra/terraform/modules/`) in its own `infra/terraform/environments/` and adds domain-specific resources (e.g., compliance audit buckets).

### NeutronOS-Specific TODOs

- [ ] Wire `NEUT_DB_URL` into Helm values -> configmap -> pod env
- [ ] Complete Alembic infrastructure (`env.py`, `alembic.ini`) for audit tables
- [ ] Add `helm upgrade` CD job to GitLab CI for dev environment
- [ ] Define NeutronOS operator guide (audience: nuclear facility IT staff)
