# Metrics Framework

> **Last Updated:** February 2026  
> **Scope:** Platform-wide metrics for Neutron OS deployments  
> **Origin:** TRIGA Digital Twin project (generalized)

This framework defines metrics categories for measuring digital twin platform success. Adapt targets to facility-specific baselines.

> **See also:** [Executive PRD Success Metrics](../prd/neutron-os-executive-prd.md#success-metrics-platform-wide) for high-level targets.

---

## North Star Metrics

| Metric | Type | Rationale |
|--------|------|-----------|
| **Complete Operating Days** | Operational | # of days with full pipeline: raw data → simulation → visualization |
| **Weekly Engaged Users** | Adoption | Users who download data OR run query OR use simulator |

---

## 1. Reliability Metrics
*"Can users trust that the system works?"*

| Metric | Definition | Current | Target | Measurement |
|--------|------------|---------|--------|-------------|
| Pipeline Success Rate | % of nightly runs completing without error | Unknown | >98% | Cron exit codes, Slack alerts |
| Data Completeness | % of expected reactor operating days with processed data | Unknown | 100% | Box uploads vs DB records |
| Mean Time to Recovery | Hours from pipeline failure → restored operation | Unknown | <4 hrs | Incident log timestamps |
| Data Integrity Score | % of records passing validation checks | Unknown | >99.5% | Automated QA scripts |

---

## 2. Latency Metrics
*"How fast do users get value?"*

| Metric | Definition | Current | Target (Near) | Target (Future) | Measurement |
|--------|------------|---------|---------------|-----------------|-------------|
| Raw Data Latency | Hours from reactor event → Box upload | Unknown | <8 hrs | <1 hr | Timestamp comparison |
| Processing Latency | Hours from Box upload → DB available | ~24 hrs | <12 hrs | <1 hr | Pipeline timestamps |
| Visualization Latency | Hours from DB update → Plotly regenerated | ~24 hrs | <12 hrs | Real-time | File mod times |
| Query Response Time | Seconds for Text-to-SQL to return | Unknown | <5 sec | <2 sec | Application logs |
| Simulation Turnaround | Hours from state detection → MPACT results | Unknown | <6 hrs | <1 hr | SLURM timestamps |

---

## 3. Adoption Metrics
*"Are people actually using this?"*

| Metric | Definition | Current | Target | Measurement |
|--------|------------|---------|--------|-------------|
| Weekly Active Users | Unique users per week | Unknown | Baseline +25%/semester | Web server logs |
| Feature Utilization | % users engaging each feature | Unknown | >50% use 2+ features | Click tracking |
| Return Rate | % users returning within 30 days | Unknown | >60% | Session analytics |
| Data Downloads | CSV/HDF5 exports per month | Unknown | Track growth | Download logs |
| Session Duration | Average minutes per visit | Unknown | >5 min | Analytics |
| Support Requests | Questions/issues per month | Unknown | Track & categorize | Email/Slack |

---

## 4. Accuracy Metrics
*"Can users trust the outputs?"*

| Metric | Definition | Current | Target | Measurement |
|--------|------------|---------|--------|-------------|
| Critical Rod Height RMSE | Predicted vs measured (cm) | Unknown | <1.0 cm | Comparison script |
| Bias Correction Stability | Std dev of calibration coefficients | Unknown | <5% drift/quarter | Statistical tracking |
| Change Point Precision | % detected states confirmed by operators | Unknown | >90% | Operator review |
| Text-to-SQL Accuracy | % queries returning correct results | Unknown | >85% | Human evaluation |
| RAG Relevance Score | % retrieved docs rated relevant | Unknown | >80% | Thumbs up/down |

---

## 5. Compliance Metrics
*"Are we inspection-ready?"*

| Metric | Definition | Current | Target | Measurement |
|--------|------------|---------|--------|-------------|
| Documentation Coverage | % operating days with complete audit trail | Unknown | 100% | Gap analysis script |
| Record Retention | Years of historical data accessible | Unknown | >10 years | Storage inventory |
| Traceability Score | % predictions linkable to source + code version | Unknown | 100% | Metadata check |
| Report Generation Time | Minutes to produce compliance report | Unknown | <5 min | Manual timing |
| Anomaly Detection Rate | % off-normal conditions flagged | 0% | >80% | Compare vs operator logs |

---

## 6. Education Metrics
*"Are students learning?"*

| Metric | Definition | Current | Target | Measurement |
|--------|------------|---------|--------|-------------|
| Simulator Sessions | Monthly uses of PKE Simulator | Unknown | >100/semester | Application logs |
| Learning Gain | Pre/post assessment improvement | Not measured | >20% | Quiz administration |
| Instructor Adoption | # courses incorporating tools (target: M E 390G, M E 361E, M E 336P) | Unknown | 2+ courses | Faculty survey |
| Student Satisfaction | NPS score | Not measured | >40 | Survey |
| Time to Competency | Simulator hours before passing practical | Not measured | Establish baseline | Correlation analysis |

---

## 7. Medical Isotope Production Metrics
*"Can we deliver isotopes reliably and quickly?"*

| Metric | Definition | Current | Target | Measurement |
|--------|------------|---------|--------|-------------|
| Request-to-Package Time | Hours from isotope order → ops package delivered | Unknown (hours?) | <30 min | Timestamp tracking |
| Request-to-Irradiation Time | Hours from order → reactor begins production | Unknown | <24 hrs | Schedule tracking |
| Production Success Rate | % of isotope runs meeting activity spec | Unknown | >99% | Production logs |
| SLA Compliance | % of orders delivered within promised window | Not tracked | >95% | Order tracking system |
| Manual Intervention Rate | % of orders requiring phone calls/emails | ~100% | <10% | Workflow audit |
| Ops Package Accuracy | % of auto-generated packages accepted without changes | 0% (manual today) | >90% | Operator feedback |

### Current State (As-Is)
1. Hospital calls Dr. Charlton directly with isotope request
2. Dr. Charlton assigns to available student/staff
3. Assignee manually reviews recent ops, runs simulations
4. Criticality data compiled into Word doc with bullet points
5. Word doc delivered via phone call to operators next morning
6. No SLA tracking, no visibility into process

### Ideal State (To-Be)
1. Hospital submits request via portal (or API integration)
2. System auto-checks reactor schedule availability
3. TRIGA DT generates simulation package automatically
4. Ops package delivered to operators digitally with checklist
5. Production tracked with SLA visibility
6. Post-production verification and delivery confirmation

---

## 8. Commercialization Readiness Metrics
*"Can we replicate and sell this?"*

| Metric | Definition | Current | Target | Measurement |
|--------|------------|---------|--------|-------------|
| Deployment Time | Hours to stand up for new reactor | Unknown | <40 hrs | Time tracking |
| Infrastructure Cost | Monthly $ for compute + storage | Unknown | Document baseline | TACC billing |
| Code Portability | % codebase without TACC dependencies | Unknown | >80% | Dependency audit |
| Documentation Completeness | % components with install docs | ~30% | 100% | Doc inventory |
| External Interest | Inbound inquiries from facilities | Unknown | Track all | CRM/email |
| Pilot Candidates | Facilities expressing pilot interest | 0 | 2+ | Outreach tracking |
| **Isotope Revenue Potential** | Est. annual $ if isotope production monetized | $0 | Document model | Market research |
| **Isotope-Capable Reactors** | # of US research reactors that could produce medical isotopes | ~30 | Identify 5 pilots | Industry survey |

---

## Metrics Collection Infrastructure Needed

| Gap | Current State | Required |
|-----|---------------|----------|
| Pipeline observability | Cron logs only | Structured logging, alerting (Sentry, PagerDuty) |
| User analytics | None | Web analytics (Plausible, PostHog) |
| Accuracy tracking | Manual spot checks | Automated comparison jobs → metrics DB |
| User feedback | None | In-app feedback buttons, surveys |
| Cost tracking | Unknown | TACC usage reports, monthly review |

---

## Immediate Actions

1. **Instrument the pipeline** - Add structured logging to establish reliability baseline
2. **Add web analytics** - Deploy lightweight analytics for usage understanding
3. **Document current costs** - Get TACC billing data for infrastructure baseline
4. **Define "operating day"** - Agree on unit of measurement for completeness
5. **Create metrics dashboard** - Single page showing key health indicators
