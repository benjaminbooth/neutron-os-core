# Executive Technical Specification — Neutron OS Nuclear Extensions

> The core specification is provided by the Axiom platform. This document defines nuclear-domain extensions only.

**Upstream:** [Axiom Executive Technical Specification](https://github.com/…/axiom/docs/tech-specs/spec-executive.md)

---

## Nuclear Extensions

### Platform Identity

**NeutronOS** is the nuclear energy domain product built on the Axiom platform.

| Property | Value |
|----------|-------|
| Tagline | The intelligence platform for nuclear facilities |
| CLI | `neut` |
| Version | 1.0 (v0.4.0 active development) |

### Nuclear Agent Specializations

Axiom agents are available in NeutronOS with nuclear-domain specializations:

| Archetype | CLI Noun | Nuclear Specialization |
|-----------|----------|----------------------|
| **Signal** | `neut signal` | Nuclear signal sources (ops log events, reactor alarms, HP surveys) |
| **Assistant** | `neut chat` | Nuclear RAG corpus, reactor-aware context |
| **Steward** | `neut mo` | NRC retention policies (7-year archive) |
| **Diagnostics** | `neut doctor` | Nuclear system health checks |
| **Publisher** | `neut pub` | NRC evidence packages, regulatory reports |

### Planned Nuclear Agent Specializations

| Archetype | CLI Noun | Nuclear Specialization |
|-----------|----------|----------------------|
| **Analyst** | `neut analyze` | Reactor anomaly detection, fuel burnup trending, sensor drift analysis |
| **Planner** | `neut plan` | Experiment scheduling, irradiation planning, isotope production coordination |
| **Compliance** | `neut comply` | NRC 30-min check enforcement, training currency tracking, license condition monitoring |
| **Reviewer** | `neut review` | Ops log review, experiment authorization workflow, shift handoff validation |
| **Coach** | `neut coach` | Operator training, reactor procedure walkthroughs, competency assessment |

### Nuclear Tool Specializations

| Tool | CLI Noun | Nuclear Specialization |
|------|----------|----------------------|
| **rag** | `neut rag` | Nuclear knowledge corpus, EC-compliant |
| **demo** | `neut demo` | TRIGA-specific walkthrough ("Jay's Story") |
| **model** | `neut model` | MCNP/VERA/SAM decks, trained ROMs |
| **simulate** | `neut sim` | ROM execution, Shadow runs, SLURM job submission to TACC |
| **data** | `neut data` | Nuclear Bronze/Silver/Gold schemas, reactor time-series queries |
| **export** | `neut export` | NRC evidence packages, compliance reports, data extracts |
| **audit** | `neut audit` | HMAC-chain verification for ops logs, NRC audit trail queries |
| **eval** | `neut eval` | ROM accuracy benchmarking, sensor reconciliation validation |
| **notify** | `neut notify` | 30-min check gap alerts, training expiry warnings, compliance notifications |

### Nuclear Infrastructure

NeutronOS consumes the Axiom platform for all infrastructure services and extends with:

- **NRC-mandatory 7-year Cold tier** and indefinite Archive for safety basis documents
- **Nuclear Bronze/Silver/Gold schemas** (reactor time-series, ops log entries, experiments, fuel burnup, xenon dynamics, compliance summaries)
- **Retention policy:** `policy = "regulatory"` for NRC-regulated deployments

### Nuclear Deployment Targets

| Environment | Stack | Status |
|-------------|-------|--------|
| **Private endpoint** | vLLM on Rascal (UT VPN) | Running |
| **TACC endpoint** | vLLM on TACC (Apptainer) | Proposed |

### Model Corral — Nuclear Model Types

High-fidelity input decks (MCNP, VERA, SAM, Griffin), trained ROMs (WASM, ONNX), validation datasets, CoreForge configurations.

### Digital Twin Hosting — Nuclear Use Cases

1. Real-time display (<100ms, ROM-1)
2. Live activation / control loop (<100ms, ROM-1)
3. Comms & Viz / interactive (5-20s, ROM-2)
4. Experiment planning (<5 min, ROM-3)
5. Operational planning (minutes, ROM-4)
6. Analysis & V&V (offline, Shadow)

**Autonomy Target:** NAL-2 (Advisory) — operator suggestions without automated execution. Progression to higher autonomy levels (NAL-3+) requires validated "progression proofs."

### Platform Positioning — Nuclear Specific

| Factor | NeutronOS Rationale |
|--------|-------------------|
| **Nuclear compliance** | Export control complexity requires on-premise, air-gappable deployment |
| **Cost trajectory** | Fixed TACC allocation; marginal cost ~$0 |
| **Customization** | Full access for digital twin integration |
