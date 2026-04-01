# ADR-005: Meeting Intake Pipeline for Nuclear Facility Operations — Neutron OS Nuclear Context

> This architecture decision is made at the Axiom platform level. This document captures nuclear-specific context only.

**Upstream:** [Axiom adr-005-meeting-intake-pipeline.md](https://github.com/…/axiom/docs/requirements/adr-005-meeting-intake-pipeline.md)

---

## Nuclear Context

### Target Audience

This tool is designed for nuclear facility operations teams specifically:

| Facility Type | Example Use Cases |
|---------------|-------------------|
| **University reactors** | Operations meetings, experiment planning, safety committee |
| **Commercial plants** | Outage planning, corrective action tracking, NRC prep |
| **National labs** | Project coordination, safety reviews, experiment design |
| **Regulatory bodies** | Inspection prep, finding tracking, public meeting records |

### Regulatory Traceability

For nuclear facilities, traceability from decision to source discussion has regulatory value. NRC inspection preparation and corrective action tracking are primary use cases that drive the human-in-the-loop review requirement.

### Deployment Constraints

- **Commercial plants** may require air-gapped deployment with local LLM (Llama/Mistral via Ollama)
- **Sensitive facilities** need on-premises-only data residency
- All three deployment modes (cloud, on-premises, air-gapped) must be supported
