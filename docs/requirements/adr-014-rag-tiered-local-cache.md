# ADR-014: RAG Tiered Local Cache — DuckDB Packs + Remote-Only Export-Controlled Tier — Neutron OS Nuclear Context

> This architecture decision is made at the Axiom platform level. This document captures nuclear-specific context only.

**Upstream:** [Axiom adr-014-rag-tiered-local-cache.md](https://github.com/…/axiom/docs/requirements/adr-014-rag-tiered-local-cache.md)

---

## Nuclear Context

### Export-Controlled Nuclear Computation Codes

The regulatory constraint driving Tier 4 is specific to nuclear:

Export-controlled nuclear computation codes (**MCNP, SCALE, ORIGEN, KENO**, etc.) and their derivative data products are subject to **EAR and 10 CFR 810**. Their embeddings and chunked text fragments are themselves controlled data. These vectors legally cannot leave an authorized compute environment.

### Tier 4: `rag-export-controlled` — TACC-Resident Corpus

Contains embeddings and chunked content derived from export-controlled nuclear computation codes and their associated data products (cross-section libraries, criticality benchmarks, shielding datasets, etc.).

- **Local store:** None. This tier is permanently TACC-resident.
- **Legal basis:** EAR and 10 CFR 810 restrict export-controlled content to authorized compute environments. The **TACC Lonestar6/Frontera** authorization boundary satisfies this requirement. Moving these vectors outside that boundary — including to a user's laptop, even an authorized user's laptop — would require the user to independently hold and maintain authorization.
- **Access:** Identity-gated via **TACC LDAP/XSEDE credentials**. Queries are proxied through a TACC-resident API endpoint; only query results (plain text chunks with citations) leave the boundary, not vectors.
- **Offline behavior:** Never available outside the TACC boundary. Queries require active TACC session.
- **Enforcement:** The NeutronOS query router MUST NOT cache, persist, or replicate any response payload from this tier outside the TACC boundary. This is a hard architectural constraint, not a configuration option.

### NeutronOS-Specific Naming

| Axiom Generic | NeutronOS Convention |
|--------------|---------------------|
| `~/.axi/rag/` | `~/.neut/rag/` |
| `.axiompack` | `.neutpack` |
| `axi rag export` / `axi rag import` | `neut rag export` / `neut rag import` |
| `axi rag pack install` | `neut rag pack install` |

### Implementation Phases (NeutronOS)

#### Phase 1 — Pre-IAM

| Capability | Status |
|---|---|
| DuckDB + vss local store for `rag-internal` | Implement |
| `neut rag index` — index local documents into Tier 1 | Implement |
| `neut rag query` — fan-out across available tiers | Implement |
| `.neutpack` format and local pack install (`neut rag pack install`) | Implement |
| Tier 4 proxy endpoint on TACC (identity-gated by TACC session) | Implement |
| `neut rag export` / `neut rag import` — manual Tier 1 sync | Implement |

#### Phase 2 — Post-IAM

| Capability | Notes |
|---|---|
| Per-user Tier 4 audit log | IAM provides identity to bind to TACC access records |

### Related

- TACC Lonestar6 authorization boundary documentation (internal, not tracked in repo)
