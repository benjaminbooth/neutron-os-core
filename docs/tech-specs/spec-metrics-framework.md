# Product Metrics Framework — Neutron OS Nuclear Extensions

> The core specification is provided by the Axiom platform. This document defines nuclear-domain extensions only.

**Upstream:** [Axiom Product Metrics Framework](https://github.com/…/axiom/docs/tech-specs/spec-metrics-framework.md)

---

## Nuclear Extensions

### Domain-Specific Metric Substitutions

The following Axiom metrics are instantiated with nuclear-specific terminology in NeutronOS deployments:

| Axiom Metric | NeutronOS Instantiation |
|-------------|------------------------|
| Complete Operating Days (system) | Complete Operating Days (reactor) |
| Raw Data Latency (system event) | Raw Data Latency (reactor event) |
| Deployment Time (new system) | Deployment Time (new reactor) |
| Infrastructure Cost (PrivateCloud) | Infrastructure Cost (TACC) |
| Code Portability (PrivateCloud deps) | Code Portability (TACC deps) |
| Isotope-Capable Systems | Isotope-Capable Reactors |

### Nuclear-Specific Metrics

#### Medical Isotope Production (Section 8)

The isotope production metrics reference nuclear-specific workflow:

- **Ideal State:** TRIGA DT generates simulation package automatically (vs. generic "facility DT")
- **Current State:** Dr. Charlton assigns isotope requests to students; criticality data compiled into Word docs

#### Education Metrics (Section 7)

Target courses are nuclear engineering specific: M E 390G, M E 361E, M E 336P.

#### Commercialization (Section 9)

- Infrastructure cost baseline measured via **TACC billing** (not generic "PrivateCloud billing")
- `neut doctor --metrics` (not `axiom doctor --metrics`) for baseline establishment
