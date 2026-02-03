# Platform Comparison: Why Not "Just Use Databricks"?

**Version:** 1.0 DRAFT  
**Date:** January 2026  
**Purpose:** Address stakeholder questions about build vs. buy for data platform

---

## The Question

> "Why are we building a custom data platform? Can't we just pay Databricks (or Snowflake, or AWS) to maintain this for us?"

This is a fair question. Managed platforms have real advantages: less operational burden, automatic scaling, enterprise support. This document explains why, for nuclear digital twins specifically, an open lakehouse architecture is the better choice.

---

## Executive Summary

| Factor | Verdict |
|--------|---------|
| **Data sovereignty** | ✅ Open lakehouse wins (you control where data lives + portable format) |
| **Cost trajectory** | ✅ Open lakehouse wins (TACC allocation vs. DBU pricing) |
| **Customization depth** | ✅ Open lakehouse wins (DT integration requires deep hooks) |
| **Operational burden** | ⚠️ Databricks wins (but manageable with modern tooling) |
| **Time to first value** | ✅ **Tie** (data puddle MVP delivers dashboards immediately) |
| **Skills transfer** | ✅ Open lakehouse wins (industry-standard patterns) |
| **Lock-in risk** | ✅ Open lakehouse wins (portable Iceberg format) |

**Recommendation:** Build on open lakehouse (Iceberg + DuckDB + dbt) for long-term strategic advantage. Accept modest additional operational complexity in exchange for data control, cost predictability, and customization flexibility.

---

## Detailed Comparison

### 1. Data Sovereignty & Nuclear Compliance

**The constraint:** Nuclear reactor data—even from research reactors—has export control and sensitivity considerations. Data cannot freely move to cloud regions, cross international boundaries, or be accessible to foreign nationals without proper controls.

| Platform | Data Residency | Format Lock-in |
|----------|---------------|----------------|
| **Databricks** | Your cloud account, but Databricks control plane has access | Delta Lake (Databricks-controlled evolution) |
| **Snowflake** | Snowflake-managed infrastructure; you choose region | Proprietary internal format |
| **Open Lakehouse** | Your choice: TACC, local, AWS, Azure—you decide | Apache Iceberg (open standard, portable) |

**The real differentiator isn't "local vs. cloud"—it's control and portability.**

We may well end up storing data in Azure or AWS. The advantage of open lakehouse is:
- **You choose** where data lives (and can change your mind later)
- **Open format** (Iceberg) means data is portable—not locked to any vendor
- **No control plane dependency**—queries don't route through vendor infrastructure

With Databricks/Snowflake, moving to a different platform means migrating data out of proprietary formats. With Iceberg on S3/Azure Blob, any engine can read the tables.

### 2. Cost Analysis

#### Databricks Pricing Model

Databricks charges in "DBUs" (Databricks Units) based on compute consumption:

| Workload Type | DBU Rate | Typical Usage | Monthly Cost |
|---------------|----------|---------------|--------------|
| SQL Warehouse (serverless) | $0.70/DBU | 1000 DBU/month | $700 |
| Jobs (batch) | $0.15/DBU | 2000 DBU/month | $300 |
| ML Training | $0.40/DBU | 500 DBU/month | $200 |
| **Subtotal** | | | **$1,200/month** |
| + Cloud infrastructure (S3, networking) | | | +$300/month |
| **Total** | | | **~$1,500/month** |

**Projected 3-year cost:** ~$54,000 (assumes modest growth)

#### Open Lakehouse on TACC

| Resource | Cost |
|----------|------|
| TACC Lonestar6 allocation | $0 (research allocation) |
| Local K8s cluster (Phase 2+) | ~$5,000 hardware (one-time) |
| Operational time | Included in grad student FTE |

**Projected 3-year cost:** ~$5,000 infrastructure + labor already budgeted

#### The Hidden Cost: Scale

Databricks pricing scales with usage. As data volumes grow and more users query the system:

| Year | Data Volume | Query Load | Estimated Databricks Cost |
|------|-------------|------------|---------------------------|
| 1 | 100 GB | Light | $1,200/month |
| 2 | 1 TB | Moderate | $2,500/month |
| 3 | 10 TB | Heavy (multi-facility) | $6,000/month |

Open lakehouse cost remains ~flat (compute is batch, not pay-per-query).

### 3. Customization Depth

Digital twin integration requires deep hooks into the data layer:

| Requirement | Databricks | Open Lakehouse |
|-------------|-----------|----------------|
| Custom ingestion from reactor DAQ | ✅ Possible (Python notebooks) | ✅ Native (direct Iceberg writes) |
| Sub-100ms query latency for DT | ⚠️ Serverless has cold start | ✅ DuckDB in-process |
| Custom UDFs for physics calculations | ✅ Possible (with restrictions) | ✅ Full control |
| Integration with HPC simulation codes | ⚠️ Complex (data movement) | ✅ Direct (same filesystem) |
| Blockchain audit integration | ⚠️ Custom connector needed | ✅ Direct API access |

**The digital twin use case is non-standard.** Managed platforms optimize for BI dashboards and batch ML training—not real-time physics simulation with custom inference loops.

### 4. Operational Complexity

This is where Databricks genuinely wins:

| Task | Databricks | Open Lakehouse |
|------|-----------|----------------|
| Cluster management | Automatic | Manual (K8s, Helm) |
| Version upgrades | Automatic | Manual |
| Security patches | Automatic | Manual |
| Performance tuning | Automatic (mostly) | Manual |
| Monitoring | Built-in | Prometheus + Grafana |

**However:** Modern infrastructure-as-code (Terraform, Helm, ArgoCD) has dramatically reduced operational burden. The "ops tax" for open lakehouse is real but manageable—and it's a one-time learning curve, not ongoing toil.

### 5. Skills Transfer

| Platform | Skills Learned |
|----------|---------------|
| **Databricks** | Databricks-specific APIs, Delta Lake proprietary features, Unity Catalog |
| **Open Lakehouse** | Apache Iceberg (industry standard), dbt (industry standard), SQL (universal), Kubernetes (universal) |

Students and researchers learning open lakehouse patterns gain skills transferable to any employer. Databricks expertise is valuable but narrower.

### 6. Lock-In Risk

| Scenario | Databricks | Open Lakehouse |
|----------|-----------|----------------|
| Switch to different platform | Migrate Delta tables (complex) | Iceberg tables portable to any engine |
| Vendor price increase | Limited negotiating power | No vendor dependency |
| Vendor deprecates feature | Forced migration | Community maintains alternatives |
| Project ends, data archival | Export required | Data already in open formats |

**Iceberg is the key differentiator.** It's an open table format supported by Databricks, Snowflake, AWS, Google, and every major vendor. Data stored in Iceberg is not locked to any platform.

---

## The "Just Pay Someone" Argument

The deeper question is: **Should a research group be in the business of running data infrastructure?**

Arguments for managed platform:
- Research time is more valuable than infrastructure time
- Grad students should focus on science, not DevOps
- Operational incidents distract from research

Arguments for building capability:
- Data infrastructure *is* the research (for a digital twin platform)
- Understanding the stack deeply enables novel research directions
- Managed platforms constrain what's possible
- Skills built are transferable and valuable

**Our position:** Neutron OS *is* the research artifact. The platform architecture, the data models, the integration patterns—these are contributions to the field, not just means to an end. Building this capability is core to the project's value proposition.

---

## When Databricks Would Be Right

To be fair, Databricks would be the better choice if:

- Data had no sensitivity constraints (could live anywhere)
- Budget was unlimited and time was the only constraint
- Use case was standard BI/ML without custom physics integration
- Team had zero infrastructure experience and no desire to learn
- Project was short-term with no long-term maintenance plan

None of these apply to Neutron OS.

---

## Hybrid Approaches

If stakeholders remain concerned, hybrid options exist:

### Option A: Databricks for Analytics, Local for DT
- Use Databricks SQL for dashboards and ad-hoc queries
- Keep digital twin simulation layer on local infrastructure
- Sync aggregated data to Databricks for visualization

**Downside:** Data lives in two places; sync complexity; cost of Databricks + local.

### Option B: Start Databricks, Migrate Later
- Use Databricks for rapid prototyping
- Migrate to open lakehouse once patterns are proven

**Downside:** Migration cost is high; better to start right.

### Option C: Databricks on GovCloud
- Use Databricks in AWS GovCloud for data residency compliance
- Accept higher cost for operational simplicity

**Downside:** GovCloud pricing is 2-3x commercial; still have customization limits.

**Recommendation:** None of these hybrids are better than building open lakehouse from the start. The operational complexity is manageable, and the benefits compound over time.

---

## Conclusion

For nuclear digital twin research:

| Criterion | Winner | Margin |
|-----------|--------|--------|
| Data sovereignty | Open Lakehouse | Large |
| 3-year cost | Open Lakehouse | Moderate |
| Customization | Open Lakehouse | Large |
| Operational burden | Databricks | Small |
| Skills transfer | Open Lakehouse | Moderate |
| Lock-in risk | Open Lakehouse | Large |

**Decision:** Proceed with open lakehouse architecture (Iceberg + DuckDB + dbt + Dagster).

The "just pay Databricks" path optimizes for short-term convenience at the cost of long-term flexibility, cost control, and research depth. For a multi-year platform that will serve multiple facilities and advance the state of nuclear digital twins, building the capability is the right investment.

---

## Appendix: Technology Mapping

If you're familiar with Databricks, here's how open lakehouse components map:

| Databricks Component | Open Lakehouse Equivalent |
|---------------------|---------------------------|
| Delta Lake | Apache Iceberg |
| Databricks SQL | DuckDB (embedded) / Trino (distributed) |
| Databricks Workflows | Dagster |
| Delta Live Tables | dbt |
| Unity Catalog | OpenMetadata / Nessie |
| MLflow | MLflow (same, it's open source) |
| Databricks Notebooks | Jupyter / VS Code |

The stack is different, but the *patterns* are identical: medallion architecture, declarative transforms, observable pipelines, governed data access.
