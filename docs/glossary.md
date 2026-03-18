# NeutronOS Glossary

> **Purpose:** Disambiguate terms that carry different meanings across nuclear engineering, software engineering, machine learning, and digital twin communities. When NeutronOS docs use these terms, this is what they mean.

**Last Updated:** 2026-03-17

---

## Model Ecosystem

The word "model" is heavily overloaded. In NeutronOS, it appears in at least five distinct contexts:

| Term | NeutronOS Meaning | Not To Be Confused With |
|------|-------------------|------------------------|
| **Model** (in `neut model`) | A physics simulation input deck or trained ROM registered in the Model Corral | ML model, LLM, data model, domain model |
| **Input Deck** | Source files for a deterministic physics code (MCNP `.i`, VERA XML, SAM YAML, OpenMC Python) | Not executable on its own — requires the physics code runtime |
| **Physics Code** | The simulation engine that executes an input deck (MCNP, MPACT, VERA, SAM, Griffin, RELAP, OpenMC, BISON) | Not a "model" — it's the tool that runs models |
| **High-Fidelity Model** | A physics code + input deck combination that produces reference-quality results. Computationally expensive (hours to days). Also called "Shadow" when run continuously | Surrogate, ROM |
| **Shadow** | A calibrated high-fidelity simulation running in parallel with the physical reactor, producing reference data for comparison and ROM training | Not real-time — Shadow runs offline or near-offline |
| **ROM** (Reduced Order Model) | A trained approximation of a high-fidelity model, fast enough for real-time or interactive use. See ROM Tiers below | Not the physics code itself; trained *from* physics code outputs |
| **Surrogate** | Synonym for ROM in NeutronOS. A trained model that approximates physics behavior | In some communities, "surrogate" implies a specific ML technique — we use it broadly |
| **LLM** | Large Language Model — the AI models that power NeutronOS agents (Neut, EVE, etc.) | Completely unrelated to physics models. Never called just "model" in NeutronOS |
| **Data Model** | Database schema or data structure (e.g., the ops log data model, the Iceberg table schema) | Context makes this clear — always qualified as "data model" |

### ROM Tiers

NeutronOS defines four ROM tiers based on latency and fidelity, plus the Shadow reference tier:

| Tier | Latency | Fidelity | Use Case | Example |
|------|---------|----------|----------|---------|
| **ROM-1** | <100ms | Lowest | Real-time display, live activation, control loops | Neural net trained on steady-state parameters |
| **ROM-2** | 5–20s | Medium | Interactive exploration, decision-support GUIs | Physics-informed neural network |
| **ROM-3** | <5 min | High | Experiment planning, parameter optimization | Gaussian process with UQ |
| **ROM-4** | Minutes | Higher | Shift planning, week-ahead fuel management | Full transient surrogate |
| **Shadow** | Hours–Days | Reference | V&V, benchmarking, ROM training data generation | VERA/MCNP full simulation |

See [Digital Twin Architecture](tech-specs/spec-digital-twin-architecture.md) for the complete specification.

### Model Corral

"Model Corral" is the **brand name** for NeutronOS's physics model registry. The CLI noun is `neut model` (not `neut corral`) — consistent with the convention of using generic nouns for CLI commands. The name reflects the reality of nuclear simulation: models wander across institutions, get forked without tracking, and accumulate ad-hoc modifications. The Corral brings them into a managed space.

See [Model Corral PRD](requirements/prd-model-corral.md).

---

## Digital Twin Ecosystem

| Term | NeutronOS Meaning |
|------|-------------------|
| **Digital Twin** | The complete system: real-time state estimation, Shadow reference, ROM tiers, drift detection, and validation — not just a 3D visualization |
| **Digital Twin Hosting** | NeutronOS's infrastructure for executing models: job scheduling, WASM runtime, run tracking, result storage |
| **State Estimation** | Inferring the current reactor state from sensor data using a ROM |
| **Shadow Run** | Executing the high-fidelity model against recorded reactor data to produce reference results |
| **Drift Detection** | Monitoring whether ROM predictions diverge from Shadow reference over time |
| **Calibration** | Adjusting model parameters to minimize discrepancy between Shadow predictions and reactor measurements |
| **Model Lineage** | The provenance chain: physics code → input deck → Shadow runs → training data → ROM → deployed WASM module |

---

## NeutronOS Platform

| Term | Meaning |
|------|---------|
| **Extension** | Any deployable capability in NeutronOS — agents, tools, utilities. Everything is an extension |
| **Provider** | A swappable implementation behind an extension point (e.g., OneDrive storage provider, pandoc generation provider). Not "plugin" |
| **Agent** | An extension with LLM autonomy, named after WALL-E characters: Neut, EVE, M-O, PR-T, D-FIB |
| **Signal** | A raw input to EVE's intelligence pipeline — voice memo, meeting transcript, chat message, code commit, document change |
| **Intelligence** | The structured output of EVE's signal processing — extracted entities, decisions, action items, correlated across sources |
| **Endpoint** | A destination for published content (OneDrive, Box, S3, local filesystem). Not an API endpoint unless qualified |
| **Connection** | A configured authentication relationship with an external service (Teams, OneDrive, GitHub, GitLab) |
| **Medallion Pattern** | Data architecture: Bronze (raw) → Silver (validated) → Gold (business-ready). See [Data Architecture](tech-specs/spec-data-architecture.md) |
| **Export Control (EC)** | Regulatory classification of information that restricts sharing. NeutronOS routes EC-sensitive queries to private LLM endpoints |

---

## Nuclear Operations

| Term | Meaning in NeutronOS Context |
|------|------------------------------|
| **Console Check** | 30-minute surveillance reading of reactor parameters. Must be logged for NRC compliance |
| **ROC** | Reactor Operations Committee — approves experiment requests and operational changes |
| **Shift Handoff** | Transfer of operational responsibility between shifts, documented in the ops log |
| **Compliance Evidence** | Automatically generated records proving regulatory requirements were met |
| **Chain of Custody** | Documented handling history for experiment samples, from irradiation through analysis |

---

## Naming Conventions

| Convention | Rule | Example |
|------------|------|---------|
| **CLI nouns** | Generic English nouns, not brand names | `neut model` (not `neut corral`), `neut pub` (not `neut prt`) |
| **Agent names** | WALL-E characters, used in docs and AGENT.md files | EVE, M-O, PR-T, D-FIB, Neut |
| **Module brand names** | Used in prose and PRD titles, not CLI | "Model Corral", "Signal Pipeline", "Publisher" |
| **Extension directories** | Snake case, agents suffixed with `_agent` | `eve_agent/`, `model_corral/`, `prt_agent/` |
| **Doc filenames** | Hyphen-separated, type-prefixed | `prd-model-corral.md`, `spec-digital-twin-architecture.md` |

---

*This glossary is the authoritative source for NeutronOS terminology. When a term appears ambiguous in any document, add it here.*
