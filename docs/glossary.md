# NeutronOS Glossary

> **Purpose:** Disambiguate terms that carry different meanings across nuclear engineering, software engineering, machine learning, and digital twin communities. When NeutronOS docs use these terms, this is what they mean.

**Last Updated:** 2026-03-18

---

## Model Ecosystem

The word "model" is heavily overloaded. In NeutronOS, it appears in at least five distinct contexts:

| Term | NeutronOS Meaning | Not To Be Confused With |
|------|-------------------|------------------------|
| **Model** (in `neut model`) | A physics simulation input deck or trained ROM registered in the Model Corral | ML model, LLM, data model, domain model |
| **Input Deck** | Source files for a deterministic physics code (MCNP `.i`, VERA XML, SAM YAML, OpenMC Python) | Not executable on its own — requires the physics code runtime |
| **Physics Code** | The simulation engine that executes an input deck (MCNP, MPACT, VERA, SAM, Griffin, RELAP, OpenMC, BISON) | Not a "model" — it's the tool that runs models |
| **VERA** | Virtual Environment for Reactor Applications — the high-fidelity code used for NeutronOS Shadow runs. Licensed from Veracity |
| **Veracity** | The company that develops and licenses VERA. NeutronOS has an open contract for code changes to support NETL and MSR digital twins |
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
| **Nightly Shadow** | The VERA Shadow that runs each night and emails operators the predicted initial critical rod height for the next day |
| **Drift Detection** | Monitoring whether ROM predictions diverge from Shadow reference over time |
| **Model Lineage** | The provenance chain: physics code → input deck → Shadow runs → training data → ROM → deployed WASM module |

### Calibration

Calibration adjusts model parameters to minimize discrepancy between Shadow predictions and reactor measurements. Dr. Clarno identifies three calibration targets:

| Target | Description |
|--------|-------------|
| **Nuclear Data Cross Sections** | Distributed with estimated uncertainties and covariances. Key values: recoverable energy per fission, U-238 capture in the 6.7 eV resonance — "get those right and most everything else works out" |
| **Initial Isotopes** | Fuel composition at some reference date (e.g., 5 cycles ago) |
| **Geometry** | Physical dimensions of materials that may not be precisely known |

### Data Quality and Measurement Uncertainty

ROM accuracy is bounded by input data quality. Key considerations (per Dr. Clarno):

| Term | Meaning |
|------|---------|
| **Measurement Uncertainty** | The noise band around sensor readings. If ROM predictions fall within measurement error, the DT "looks very accurate" but may not add real-time value |
| **Time Synchronization** | Rod position, neutron power, and Cherenkov power must be time-aligned to correlate physics-based changes vs. noise |
| **Physics vs. Noise** | A real rod movement induces a predictable power response. Correlated spikes in Cherenkov and neutron detectors indicate physics; uncorrelated fluctuations are noise |
| **Data Cleaning** | Pre-processing to remove noise before ROM inference. Assigned to Sam in stakeholder RACI |

**Practical implication:** Before expecting ROM value, must validate that rod position, neutron detector power, and Cherenkov power are time-synchronized and physically correlated.

### ROM Failure Modes

"Failure" means different things depending on the ROM tier and use case (per Dr. Clarno):

| Use Case | Failure Mode | Consequence | Response |
|----------|--------------|-------------|----------|
| **ROM-1 for Semi-Autonomous Control** | ROM gives wrong answer, actuates incorrect rod position | Physical control rods still in place; can scram to maintain safety | Take offline, investigate |
| **ROM-1 for Real-Time Display** | ROM goes dark or shows bad predictions | Operators ignore it; no safety consequence | Highlight discrepancy, log for analysis |
| **ROM-2/3/4** | Predictions don't match measurements | No immediate consequence; need to diagnose source | Queue for investigation: was it input, code, output, system instrumentation, data cleaning? |

**Key insight:** For most ROM applications, failure has no safety consequence because the physical reactor controls remain in place. The exception is NAL-3+ where ROMs actuate control systems — but those require extensive validation before deployment.

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

## Agent Autonomy (RACI)

NeutronOS agents operate under a configurable autonomy model. Trust is **three-dimensional**: specific to a user + agent + action combination.

| Term | Meaning |
|------|---------|
| **RACI** | Autonomy framework: **R**esponsible (human does work), **A**pprove (agent works, human approves), **C**onsulted (agent pauses at decisions), **I**nformed (agent acts, notifies after) |
| **Trust Slider** | Per-agent coarse-grained control with 5 positions: Locked Down → Cautious → Balanced → Autonomous → Full Trust |
| **NSG-005** | Nuclear Safety Guardrail requiring human approval for all safety-related actions. Cannot be overridden by RACI settings |
| **Emergency Mode** | Override states triggered by `neut raci`: `all-propose-only` (approve everything), `all-log-intent-only` (silent logging), `all-freeze` (complete stop) |
| **Intent Log** | File (`runtime/logs/intent.jsonl`) where agents log what they *would* have done when in `all-log-intent-only` mode |
| **Trust Signals** | Metrics tracked per-agent: approval rate, reversions, explicit feedback — used to suggest RACI adjustments |

See [Agents PRD — RACI Framework](requirements/prd-agents.md#raci-based-human-in-the-loop-framework).

---

## Nuclear Autonomy Levels (NAL)

A progression framework for reactor control automation, analogous to SAE Levels 0-5 for autonomous vehicles.

| Level | Name | Description |
|-------|------|-------------|
| **NAL-0** | No Automation | Manual operation only |
| **NAL-1** | Information | DT displays predictions alongside sensor data |
| **NAL-2** | Advisory | DT suggests actions; human reviews and executes |
| **NAL-3** | Conditional Assist | DT executes routine actions with operator approval |
| **NAL-4** | High Automation | DT handles normal operations autonomously |
| **NAL-5** | Full Automation | DT handles all operations (long-term research goal) |

**Current target:** NAL-2 (Advisory). Progression requires validation proofs at each level.

See [Digital Twin Hosting PRD — Nuclear Autonomy Levels](requirements/prd-digital-twin-hosting.md#nuclear-autonomy-levels-nal).

---

## Nuclear Operations

| Term | Meaning in NeutronOS Context |
|------|------------------------------|
| **Console Check** | 30-minute surveillance reading of reactor parameters. Must be logged for NRC compliance |
| **ROC** | Reactor Operations Committee — approves experiment requests and operational changes |
| **Shift Handoff** | Transfer of operational responsibility between shifts, documented in the ops log |
| **Compliance Evidence** | Automatically generated records proving regulatory requirements were met |
| **Chain of Custody** | Documented handling history for experiment samples, from irradiation through analysis |

### Reactor Type Applicability

Digital twin applicability varies by reactor category (per Dr. Clarno):

| Reactor Type | DT Applicability | Rationale |
|--------------|------------------|-----------|
| **Research & Test Reactors** | Primary target | Obvious value, but R&D components often cut when budgets overrun |
| **Advanced Reactors** | Must engage early | Need to work from beginning of design to specify instrumentation. Must translate capability to revenue/savings/speed |
| **Existing Commercial** | Not realistic | Instrumentation is old, processes frozen, $1-2M/day revenue means "don't mess with anything" |

**Industry partner strategy:** Find teams certain they're building a suite of reactors who understand the value of deeply instrumenting the first few.

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
