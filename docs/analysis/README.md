# Analysis Index: Sm-153 Medical Isotope Incident

**Date:** February 10, 2026  
**Incident:** Samarium-153 production yielded 130 mCi vs. 150 mCi target  
**Reported by:** William Charlton, UT NETL TRIGA Facility  
**Analysis prepared for:** TRIGA Digital Twin, Neutron OS PRD team, Medical Isotope Program leadership  

---

## Quick Navigation

### For Executives / Facility Directors
- **Start here:** [Executive Summary](./Sm153_Executive_Summary.md) (5 min read)
- **Then:** [Architecture Impact](./Neutron_OS_Architecture_Impact.md) — shows how this reshapes Neutron OS (10 min read)

### For PRD/Product Managers
- **Start here:** [PRD Change Summary](./PRD_Change_Summary.md) — see exactly what needs to change in each document
- **Then:** [Full Technical Analysis](./Sm153_Incident_Analysis_PRD_Implications.md) — detailed requirements & scenarios

### For Engineers/Analysts
- **Start here:** [Full Technical Analysis](./Sm153_Incident_Analysis_PRD_Implications.md) — complete with data models, dbt tests, acceptance criteria
- **Then:** [Architecture Impact](./Neutron_OS_Architecture_Impact.md) — understand system-level implications
- **Reference:** [PRD Change Summary](./PRD_Change_Summary.md) — for specific document updates

### For Dashboard/UX Design
- **Start here:** [Full Technical Analysis - Scenarios Section](./Sm153_Incident_Analysis_PRD_Implications.md#recommended-new-scenarios) (goto "Recommended New Scenarios")
- **Includes:** 3 complete scenario designs with chart specs, filters, user journeys, mockups

### For Data Engineering
- **Start here:** [Full Technical Analysis - Data Platform Section](./Sm153_Incident_Analysis_PRD_Implications.md#updated-data-platform-requirements)
- **Tables needed:** xenon estimation, yield prediction history, model error tracking
- **Timeline:** 8 weeks to MVP

---

## Document Map

```
docs/analysis/
├── 📋 README (this file)
│
├── 🎯 Sm153_Executive_Summary.md
│   └─ FOR: Executives, facility director, quick stakeholder decisions
│   └─ TIME: 5-10 min
│   └─ DELIVERABLE: Yes/No on P0 prioritization, timeline, risks
│
├── 📊 Sm153_Incident_Analysis_PRD_Implications.md  
│   └─ FOR: Product managers, engineers, analysts
│   └─ TIME: 30-40 min (detailed read)
│   └─ CONTAINS:
│      ├─ What happened & what DT should have shown (3 scenarios)
│      ├─ Gap analysis: Medical Isotope PRD, Analytics Dashboards, Data Platform
│      ├─ 3 new dashboard scenarios (full spec)
│      ├─ Data models (Bronze/Silver/Gold tables)
│      ├─ Implementation roadmap (3 phases, 6-12 months)
│      ├─ Xenon model validation strategy
│      ├─ Success metrics & acceptance criteria
│      └─ References to relevant PRD sections
│
├── 🔧 PRD_Change_Summary.md
│   └─ FOR: PRD maintainers, change control
│   └─ TIME: 15-20 min (to apply changes)
│   └─ CONTAINS:
│      ├─ Line-by-line changes to medical-isotope-prd.md
│      ├─ Changes to analytics-dashboards-prd.md
│      ├─ New sections to data-platform-prd.md
│      ├─ New scenario files to create
│      └─ Validation checklist before submitting
│
└─ 🏗️ Neutron_OS_Architecture_Impact.md
   └─ FOR: System architects, future planning
   └─ TIME: 15-20 min (conceptual understanding)
   └─ CONTAINS:
      ├─ Current architecture (what was missing: DT integration, medical isotope scenarios)
      ├─ Post-incident architecture (what gets added)
      ├─ Data flows: pre-production planning, real-time monitoring, post-production analysis
      ├─ How this supports NEUP Medical Isotopes proposal
      ├─ Expected user workflows (after deployment)
      ├─ Organizational alignment & buy-in strategy
      └─ Risks & mitigation
```

---

## The Incident at a Glance

### What Happened
- **Date:** February 10, 2026 (Monday)
- **Isotope:** Sm-153 for medical patient treatment
- **Target activity:** 150 mCi (at 10 AM calibration)
- **Actual activity:** 130 mCi
- **Shortfall:** 20 mCi (13% below target)
- **Patient impact:** Barely sufficient; treatment nearly delayed

### Suspected Root Causes
1. **Xenon buildup** — Core accumulated xenon over weekend; not fully decayed by Monday
2. **Temperature drop** — Fuel temp dropped 373°C → 367°C at constant 950 kW (anomaly)
3. **Lower-than-expected flux** — In the CT irradiation position specifically

### Why This Matters

**The system design is incomplete:**
- ❌ No **pre-production forecast** of yield given xenon state (before committing batch)
- ❌ No **real-time anomaly alerts** during production (temperature drop unnoticed until analysis)
- ❌ No **automated root cause analysis** (why was fluence low?)

This is exactly what NEUP proposal aims to deliver: "DT-driven semi-autonomous operations with operator-facing confidence communication."

---

## Proposed Solution

### Three New Capabilities (P0 Priority)

**1. Pre-Production Planning Dashboard**
- Production manager decides Monday vs. defer to Wednesday
- Digital shadow predicts yield: "143 ± 8 mCi (YELLOW: risky)"
- What-if: "If we wait 12h for xenon decay: 150 ± 5 mCi (GREEN)"
- Decision: informed by data, rationale logged

**2. Real-Time Monitoring Dashboard**
- Operator monitors power, fuel temperature, running activity prediction
- Alert: "Fuel temp 2°C below baseline → activity predicting 140 mCi vs. 150 mCi target"
- Recommendation: "Extend 15 min or increase power by 50 kW to recover +2 mCi"
- Decision point: operator approves extension; system logs rationale

**3. Post-Production Yield Analysis Dashboard**
- Automatic RCA: "Predicted 143 mCi, actual 130 mCi, error decomposition:"
  - Xenon model: -3 mCi
  - Position flux: -4 mCi  
  - Other: -10 mCi
- Identifies which model needs refinement (xenon? flux? other?)
- Flags: "Confidence intervals may be too optimistic; widen from ±8 to ±12 mCi"

### Timeline

- **Q1 2026 (8 weeks):** MVP deployment with pre-production planning + monitoring
- **Q2 2026 (2-3 months):** Enhanced models, what-if scenarios, RCA automation
- **Q3-Q4 2026:** Integration with Scheduling System for auto-optimization

### Investment Required

- **Engineering:** 1 FTE (DT model development + dashboard design) @ 8-12 weeks
- **Data Engineering:** 0.5 FTE (ingestion pipeline, Gold tables) @ 8 weeks
- **Validation:** 0.5 FTE (historical data analysis, model training) @ ongoing
- **Facility Support:** Part-time (data access, operator feedback)

### Success Metrics

- Zero yield shortfalls >10% in medical isotope batches (currently ~5% occurrence)
- Prediction accuracy ±10% on 95% of batches (MVP); ±5% by Q2
- Operator adoption >90% within 1 month of deployment
- Decision time reduced from 2h to 15 minutes

---

## Key Questions for Stakeholders

**For Bill Charlton (Facility Director):**
1. Is the Feb 10 xenon buildup assessment correct? (vs. other causes?)
2. How many Sm-153 production runs exist in past 12 months? (for model training)
3. Is CT position flux known to be lower than design basis? (high-fidelity calcs needed?)

**For Production Manager:**
1. In real-time, can operators extend irradiation or increase power if warned of shortfall?
2. What % of orders are "must succeed" vs. "can reschedule"?
3. How much lead time needed for customer communication if rescheduling?

**For Medical Isotope Program:**
1. Can this be prioritized as P0 given patient-facing impact?
2. Should all isotopes (Sm, I-131, Mo-99) be covered in MVP, or just Sm initially?
3. What regulatory review needed before changing production procedures?

**For NEUP Team:**
1. Should Feb 10 incident be featured in final report as validation of DT approach?
2. Does this accelerate the timeline from NEUP proposal milestones?

---

## How to Use These Documents

### For Decision-Making
1. Read [Executive Summary](./Sm153_Executive_Summary.md) (5 min)
2. Review [Architecture Impact](./Neutron_OS_Architecture_Impact.md) "Risks & Mitigation" section (10 min)
3. **Decision:** Approve P0 prioritization, allocate resources, set 8-week MVP deadline

### For PRD Implementation
1. Read [PRD Change Summary](./PRD_Change_Summary.md) (15 min)
2. Apply changes to `medical-isotope-prd.md`, `analytics-dashboards-prd.md`, `data-platform-prd.md`
3. Create 3 new scenario files in `docs/scenarios/superset/`
4. Run validation checklist before merging

### For Design/Development
1. Read [Full Technical Analysis - Scenarios](./Sm153_Incident_Analysis_PRD_Implications.md#recommended-new-scenarios) (30 min)
2. Extract dashboard specs into Figma/design tool
3. Create Superset dashboard prototypes
4. Get production manager and operator reviews (UX validation)

### For Data Engineering
1. Read [Full Technical Analysis - Data Platform](./Sm153_Incident_Analysis_PRD_Implications.md#updated-data-platform-requirements) (20 min)
2. Design Bronze/Silver/Gold table schemas
3. Build ingestion pipelines (dbt models)
4. Plan testing strategy (dbt tests provided in full analysis)

---

## Cross-References to Existing Docs

- **Related PRDs:**
  - [Medical Isotope Production PRD](../prd/medical-isotope-prd.md) — MI-020, MI-023 requirements
  - [Analytics Dashboards PRD](../prd/analytics-dashboards-prd.md) — Priority 4 Digital Twin dashboards
  - [Data Platform PRD](../prd/data-platform-prd.md) — Xenon state, yield prediction tables
  - [Executive PRD](../prd/neutron-os-executive-prd.md) — System architecture, anomaly detection

- **Related Scenarios:**
  - [Reactor Performance Analytics](../scenarios/superset/reactor-performance-analytics/scenario.md) — xenon/power/burnup modeling (foundation)
  - [New Medical Isotope Scenarios](../scenarios/superset/) — to be created based on this analysis

- **Related NEUP Docs:**
  - `docs/proposals/NEUP_2026/MedicalIsotopes.docx` — proposal chapter on DT validation for medical isotope production

---

## What Happens Next

### Immediate (This Week)
- [ ] Facility director reviews [Executive Summary](./Sm153_Executive_Summary.md)
- [ ] Bill Charlton confirms root cause assessment with DCS data review
- [ ] Team decides: P0 prioritization? GO or HOLD?

### Short-Term (Weeks 1-2)
- [ ] If GO: Schedule kickoff with engineering, data, design teams
- [ ] Validate xenon model assumptions (fuel temp correlation study)
- [ ] Identify and extract historical Sm production data (20+ runs needed for model training)
- [ ] Begin PRD changes per [PRD Change Summary](./PRD_Change_Summary.md)

### Medium-Term (Weeks 3-8)
- [ ] Implement MVP: xenon estimation → yield prediction → pre-production dashboard
- [ ] Real-time monitoring dashboard design and build
- [ ] Field testing with production manager and operators
- [ ] Retrospective validation on historical batches

### Long-Term (Q2-Q4 2026)
- [ ] Enhanced models (isotope-specific, position-specific flux)
- [ ] Post-production RCA automation
- [ ] Integration with Scheduling System for multi-batch optimization
- [ ] NEUP final report including Feb 10 case study

---

## Contact & Questions

- **PRD Owner:** [Neutron OS PM]
- **Medical Isotope Lead:** [Bill Charlton / Facility Director]
- **TRIGA DT Lead:** [DT project manager]
- **Data Engineering:** [Data team lead]

---

## Document Status

| Document | Status | Last Updated | Reviewer |
|----------|--------|--------------|----------|
| Executive Summary | Draft | Feb 10, 2026 | Pending |
| Incident Analysis | Draft | Feb 10, 2026 | Pending |
| PRD Change Summary | Draft | Feb 10, 2026 | Pending |
| Architecture Impact | Draft | Feb 10, 2026 | Pending |

**Ready for:** Facility director review, PRD team discussion, engineering kickoff

---

**Next Action:** Share [Executive Summary](./Sm153_Executive_Summary.md) with stakeholders for decision on P0 prioritization.
