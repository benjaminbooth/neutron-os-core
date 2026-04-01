# RAG Community Corpus & Federated Knowledge — Neutron OS Nuclear Extensions

> The core specification is provided by the Axiom platform. This document defines nuclear-domain extensions only.

**Upstream:** [Axiom RAG Community Corpus Spec](https://github.com/…/axiom/docs/tech-specs/spec-rag-community.md)

---

## Nuclear Extensions

### Founding Federation Members

The three founding federation members are nuclear research reactor facilities:

- **UT-Austin NETL** (TRIGA Mark II)
- **OSU TRIGA** (TRIGA Mark II)
- **INL NRAD** (TRIGA Mark II)

### Nuclear Domain Packs

| Pack | Default `access_tier` | Primary content sources |
|------|---|---|
| `procedures` | `public` / `restricted` | NRC regulations, DOE standards, IAEA safety guides, facility procedures |
| `simulation-codes` | `public` / `classified` | MCNP6, SCALE, OpenMC documentation; classified content via RED path only |
| `nuclear-data` | `public` | ENDF/JEFF cross-section libraries |
| `reduced-order-models` | `public` / `classified` | ROM cards, validation datasets |
| `research` | `public` | Published papers, experiment reports |
| `medical-isotope` | `public` | Radioisotope production procedures, QA/QC |
| `training` | `public` | Training reactor operations, lab procedures |
| `regulation-compliance` | `public` | 10 CFR parts, DOE orders, facility license conditions |

### Nuclear-Specific Domain Tags

Federation fact propositions use nuclear domain tags such as `reactor_operations` (vs. Axiom's generic `system_operations`).

### Relationship to INL Federated Learning LDRD

The INL multi-site LDRD trains ML models across UT-Austin TRIGA, OSU TRIGA, and INL NRAD reactors using Flower AI. NeutronOS community corpus federation is the knowledge-layer complement. See upstream spec section 11 for the full comparison table.
