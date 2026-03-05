# OKRs & Goals

> **Last Updated:** December 2025  
> **Planning Horizon:** Q1-Q4 2026

---

## Objective 1: Trusted Automated Operations
> Users trust the pipeline runs reliably without intervention

| Key Result | Target | Timeline | Owner |
|------------|--------|----------|-------|
| Pipeline success rate >98% | 98% | Q1 | TBD |
| Mean time to recovery <4 hours | 4 hrs | Q1 | TBD |
| Zero manual interventions for routine operations | 0 | Q2 | TBD |
| Automated alerting for pipeline failures | Implemented | Q1 | TBD |

### Supporting Initiatives
- [ ] Add structured logging to Shadowcaster
- [ ] Configure Slack/email alerts for failures
- [ ] Create runbook for common failure modes
- [ ] Implement automatic retry logic

---

## Objective 2: Near-Real-Time Insights
> Reduce time from reactor event to actionable data

| Key Result | Target | Timeline | Owner |
|------------|--------|----------|-------|
| Processing latency <12 hours | 12 hrs | Q1 | TBD |
| Automated Box upload from facility | Implemented | Q2 | TBD |
| Document current latency baseline | Complete | Q1 | TBD |
| Streaming architecture proof-of-concept | Demo | Q3 | TBD |

### Supporting Initiatives
- [ ] Instrument pipeline with timestamps at each stage
- [ ] Work with NETL to automate ZOC → Box upload
- [ ] Evaluate real-time data streaming options (gRPC, Kafka)
- [ ] Benchmark TACC job queue wait times

---

## Objective 3: Validated Simulation Accuracy
> Predictions trusted for V&V and decision-making

| Key Result | Target | Timeline | Owner |
|------------|--------|----------|-------|
| Critical rod height RMSE <1.0 cm | 1.0 cm | Q2 | TBD |
| Published validation dataset (citable) | 1 dataset | Q2 | TBD |
| Bias correction model documented with UQ | Complete | Q2 | TBD |
| Automated accuracy tracking dashboard | Implemented | Q2 | TBD |

### Supporting Initiatives
- [ ] Create automated RMSE calculation script
- [ ] Document bias correction methodology
- [ ] Prepare dataset for Zenodo/OSTI publication
- [ ] Add uncertainty quantification to predictions

---

## Objective 4: Active User Community
> Researchers and students regularly use the platform

| Key Result | Target | Timeline | Owner |
|------------|--------|----------|-------|
| Establish baseline WAU metric | Measured | Q1 | TBD |
| 25% WAU growth | +25% | Q2 | TBD |
| 2+ courses incorporating tools | 2 courses | Q3 | TBD |
| User satisfaction survey conducted | Complete | Q2 | TBD |

### Supporting Initiatives
- [ ] Deploy web analytics (Plausible or PostHog)
- [ ] Meet with M E 390G (Nuclear Engineering Laboratory) instructors about integration - this course directly uses TRIGA
- [ ] Explore M E 361E (Nuclear Reactor Operations) and M E 336P (Concepts in Nuclear Engineering) for simulator use
- [ ] Create tutorial documentation for new users
- [ ] Implement in-app feedback mechanism

---

## Objective 5: Compliance Automation
> Inspection-ready documentation on demand

| Key Result | Target | Timeline | Owner |
|------------|--------|----------|-------|
| 100% documentation coverage for 2026 operations | 100% | Q1 | TBD |
| Automated compliance report generator | Shipped | Q2 | TBD |
| Anomaly detection system prototype | Demo | Q3 | TBD |
| Validation with facility management | Complete | Q2 | TBD |

### Supporting Initiatives
- [ ] Audit existing data for gaps
- [ ] Define compliance report format with facility
- [ ] Research anomaly detection approaches
- [ ] Interview operators about off-normal identification

---

## Objective 6: Medical Isotope Production Automation
> Reduce isotope request-to-delivery time and eliminate manual coordination

| Key Result | Target | Timeline | Owner |
|------------|--------|----------|-------|
| Document current isotope workflow (as-is) | Complete | Q1 | TBD |
| Request-to-package time <30 minutes | 30 min | Q3 | TBD |
| Automated ops package generation | Prototype | Q2 | TBD |
| Zero phone calls required for routine orders | 0 | Q4 | TBD |
| SLA tracking implemented | Complete | Q3 | TBD |

### Supporting Initiatives
- [ ] Shadow Dr. Charlton on 2-3 isotope request calls
- [ ] Map current workflow end-to-end with timestamps
- [ ] Interview Houston-area hospital contacts about pain points
- [ ] Design isotope request portal/API
- [ ] Integrate simulation auto-generation for isotope production configs
- [ ] Create operator-facing production checklist generator

### Current State Problem
Today, when a Houston cancer clinic needs isotopes:
1. Hospital calls Dr. Charlton (NETL Director) directly
2. Dr. Charlton assigns work to available student/professor
3. Assignee manually reviews recent reactor ops
4. Assignee runs new simulations for criticality data
5. Results compiled into Word doc with bullet points
6. Word doc delivered via phone to operators next morning

**This is why UT's head of Nuclear Engineering takes isotope calls** - there's no system to handle it otherwise.

**This is why more reactors don't produce isotopes** - the coordination overhead is prohibitive without automation.

---

## Objective 7: Commercialization Foundation
> Demonstrate replicable value for other facilities

| Key Result | Target | Timeline | Owner |
|------------|--------|----------|-------|
| Full architecture documentation | Complete | Q1 | TBD |
| Infrastructure cost model documented | Complete | Q1 | TBD |
| 2 facilities expressing pilot interest | 2 | Q4 | TBD |
| Deployment playbook for new reactor | Draft | Q4 | TBD |
| **Isotope production revenue model documented** | Complete | Q2 | TBD |
| **3 research reactors assessed for isotope capability** | 3 | Q3 | TBD |

### Supporting Initiatives
- [ ] Create architecture diagram documentation
- [ ] Analyze TACC billing for cost breakdown
- [ ] Identify potential pilot reactor facilities
- [ ] Abstract TACC-specific dependencies
- [ ] Research medical isotope market size and pricing
- [ ] Identify US research reactors with isotope production capability

---

## Quarterly Roadmap Summary

### Q1 2026: Foundation + Isotope Discovery
- Establish metrics baselines
- Instrument pipeline for observability
- Document architecture and costs
- Achieve >98% pipeline reliability
- **Document current isotope workflow end-to-end**
- **Shadow Dr. Charlton on 2-3 isotope request calls**
- **Identify Houston hospital contacts**

### Q2 2026: Quality + Isotope Prototype
- Improve simulation accuracy (<1.0 cm RMSE)
- Publish validation dataset
- Ship compliance report generator
- Conduct user satisfaction survey
- **Prototype isotope request form (even Google Form)**
- **Auto-generate first ops package from digital inputs**
- **Interview 3+ isotope customers**

### Q3 2026: Growth + Isotope SLA
- Deploy streaming PoC
- Integrate with 2+ courses
- Launch anomaly detection prototype
- 25% WAU growth achieved
- **Implement SLA tracking for isotope orders**
- **Request-to-package time <30 minutes**
- **Research ARPA-E MEITNER funding alignment**

### Q4 2026: Scale + Isotope Expansion
- Engage pilot facility candidates
- Draft deployment playbook
- Demonstrate full automation
- Year-end metrics review
- **Assess 3 additional reactors for isotope capability**
- **Document isotope production revenue model**
- **Evaluate spin-out vs university licensing path**

---

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| TACC infrastructure changes | Pipeline breaks | Document dependencies, test on alternate systems |
| Key personnel departure | Knowledge loss | Comprehensive documentation, cross-training |
| NETL facility schedule | No data to process | Coordinate with operators, handle gaps gracefully |
| MPACT version changes | Simulation mismatch | Pin versions, test upgrades |
| VPN access barriers | User adoption blocked | Work with TACC on alternatives |

---

## Review Schedule

| Cadence | Activity |
|---------|----------|
| Weekly | Check pipeline health, review alerts |
| Monthly | Metrics dashboard review, progress on KRs |
| Quarterly | OKR scoring, goal adjustment, stakeholder update |
| Annually | Strategy review, next year planning |
