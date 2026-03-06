# NeutronOS AWS Cost Estimation Tool

Comprehensive AWS infrastructure cost calculator for NeutronOS Phase 1 (UT TRIGA digital twin, 2026-2027).

## Overview

This tool estimates all AWS service costs across **9 major categories** plus external services:

1. **Compute** (EKS, Lambda, NAT Gateway): $200–350/mo
2. **Storage** (S3, EBS): $50–150/mo
3. **Database** (RDS, ElastiCache): $100–200/mo
4. **Analytics** (Athena, Glue): $0–60/mo
5. **Networking** (Data Transfer, VPC): $100–300/mo
6. **Security** (KMS, Secrets Manager): $20–50/mo
7. **Monitoring** (CloudWatch): $30–100/mo
8. **Developer Tools** (ECR, CodeBuild): $5–30/mo
9. **Management** (Backup, Config): $5–20/mo
10. **External Services** (Redpanda, Claude API): $300–600/mo

**Total Phase 1 Cost (2026-2027): $612–2,016/mo ($5.5–25K annually)**

## Three Pre-Defined Scenarios

### Minimal ($612/mo)
- PiXie excluded (Phase 2)
- Conservative approach
- Single-AZ, minimal external services
- **Phase 1 Total: ~$10K**

### Recommended ($1,134/mo) ⭐
- PiXie Phase 1 included
- Balanced cost/capability
- Moderate egress assumptions
- **Phase 1 Total: ~$13.6K**

### Full Cloud ($2,016/mo)
- AWS primary, high-availability (multi-AZ, multi-region)
- Heavy external services (premium Redpanda, active Claude RAG)
- Disaster recovery enabled
- **Phase 1 Total: ~$24K**

## Installation

### Requirements
- Python 3.8+
- No external dependencies required for basic operation

### Setup

```bash
# Clone or navigate to this directory
cd Neutron_OS/cost_estimation_tool

# (Optional) Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# (Optional) Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Calculate a Single Scenario

```bash
# Minimal scenario (PiXie excluded)
python main.py --scenario minimal

# Recommended scenario (PiXie Phase 1)
python main.py --scenario recommended

# Full cloud scenario (high-availability)
python main.py --scenario full_cloud
```

### Compare All Three Scenarios

```bash
python main.py --compare
```

### Export as JSON

```bash
python main.py --compare --format json --output costs.json
```

### Export as CSV

```bash
python main.py --compare --format csv --output costs.csv
```

### Generate Detailed Report

```bash
python main.py --scenario recommended --detailed
```

## Usage Examples

### As a Command-Line Tool

```bash
# Generate markdown summary for recommended scenario
python main.py --scenario recommended --format markdown

# Export all scenarios as JSON for dashboard/analysis
python main.py --compare --format json --output results.json

# Generate plain-text summary for printing
python main.py --scenario full_cloud --format text
```

### As a Python Library

```python
from tools.cost_estimation_tool import scenario_recommended, CostReporter

# Get pre-defined scenario
breakdown = scenario_recommended()

# Print summary
print(f"Monthly Cost: ${breakdown.total_monthly:.2f}")
print(f"2026 Cost (9mo): ${breakdown.annual_cost_2026_9mo():,.2f}")
print(f"2027 Cost (12mo): ${breakdown.annual_cost_2027_12mo():,.2f}")

# Generate detailed report
report = CostReporter.to_detailed_markdown(breakdown)
print(report)
```

### Custom Stakeholder Inputs

```python
from tools.cost_estimation_tool import CostCalculator, StakeholderResponses

# Define stakeholder responses (e.g., from data collection worksheet)
responses = StakeholderResponses(
    operations=OperationsInputs(
        operating_hours_per_week=80,
        will_external_collaborators_access=False,
    ),
    pixie=PiXieInputs(
        phase_1_inclusion=True,
        current_daily_data_volume_gb=0.5,
    ),
    compliance=ComplianceInputs(
        regulatory_frameworks=["ITAR"],
        aws_region_requirement="govcloud",
    ),
)

# Calculate costs
calculator = CostCalculator(responses)
breakdown = calculator.calculate_full_breakdown("Custom Scenario")

# Export
from tools.cost_estimation_tool import CostReporter
report = CostReporter.to_markdown_table([breakdown])
```

## Data Models

### StakeholderResponses
Main data class containing all stakeholder inputs:

- **PhysicsInputs**: Cole's MPACT & physics modeling data
- **OperationsInputs**: Nick's operations & production data
- **PiXieInputs**: Max's hardware & data characteristics
- **MLInputs**: Jay's ML/RAG & data engineering
- **ComplianceInputs**: Dr. Clarno's regulatory requirements

### CostBreakdown
Complete cost breakdown with:
- Individual service costs (compute, storage, database, etc.)
- Monthly totals and annual projections
- 20% contingency buffer
- Methods: `to_dict()`, `annual_cost_2026_9mo()`, `annual_cost_2027_12mo()`, `biennial_cost()`

## Key Design Decisions

### Cost Formulas

All formulas follow AWS pricing as of Feb 2026:

```python
# S3 Storage
s3_hot_monthly = (annual_volume_gb / 365 * 2_years) * $0.023/GB/mo
s3_cold_monthly = (annual_volume_gb / 365 * 5_years) * $0.004/GB/mo

# RDS (instance cost only; backups included in management tier)
rds_monthly = instance_type_cost  # $40–150/mo depending on size

# Data Egress (the hidden cost!)
egress_monthly = egress_gb_per_month * $0.09/GB

# Claude API
claude_monthly = (input_tokens_per_month / 1M * $3) + (output_tokens_per_month / 1M * $15)

# EKS Compute
eks_monthly = control_plane ($72) + (worker_nodes * $80-90)
```

### Assumptions & Defaults

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| Data volume | 150GB/year | From Jay's estimate (ZOC CSVs + MPACT) |
| Operating hours | 80/week | Typical research facility schedule |
| Data egress | 50GB/month | Moderate: scientists + publications |
| Worker nodes | 2–4 | Auto-scaling based on load |
| Log retention | 30 days | CloudWatch default |
| Contingency | 20% | Standard for blue-sky estimates |

## Connecting to Data Collection

This tool ingests responses from [aws-cost-estimate-data-collection.md](../docs/analysis/aws-cost-estimate-data-collection.md):

- **Section A** → `PhysicsInputs`
- **Section B** → `OperationsInputs`
- **Section C** → `PiXieInputs`
- **Section D** → `MLInputs`
- **Section E** → `ComplianceInputs`

Once stakeholder responses are collected (by Feb 16), populate a JSON file and run:

```bash
python main.py --custom --input responses.json --format markdown --output final_estimate.md
```

## Output Formats

### Markdown (Default)
Produces tables suitable for:
- Embedding in documents
- GitHub wikis
- Executive presentations
- Email reports

### JSON
Structured export for:
- Programmatic analysis
- Dashboard integration
- Version control (diff-friendly)
- Import into spreadsheets

### CSV
Spreadsheet-compatible format for:
- Detailed cost tracking
- Historical comparison
- Advanced filtering/sorting

### Plain Text
Human-readable summary for:
- Quick printouts
- Terminal viewing
- Email body text

## Key Insights from Analysis

1. **Storage is cheap (~$50–150/mo), egress is expensive**
   - S3 storage: $0.023/GB/mo
   - Data transfer: $0.09/GB (4x higher!)
   - A scientist downloading 100GB/month = $9/mo alone

2. **Compute dominates costs**
   - EKS control plane: $72/mo (fixed)
   - Worker nodes: $80–90/mo × 2–4 nodes = $160–360/mo
   - NAT Gateway: $32–64/mo (often forgotten)

3. **External services are 30–50% of total cost**
   - Redpanda Cloud: $150–300/mo (if PiXie)
   - Claude API: $100–400/mo (if active RAG)
   - These outweigh AWS storage costs!

4. **Monitoring/logging varies 3x based on verbosity**
   - Errors-only: ~$30/mo
   - Info-level: ~$60/mo
   - Debug-level: ~$150/mo

5. **Disaster recovery adds 10–15% cost**
   - Multi-AZ NAT Gateway: +$32/mo
   - Cross-region backups: +$20–80/mo
   - Multi-region disaster recovery: +30% overall

## Common Gotchas

❌ **Forgetting data egress:**
- AWS storage looks cheap ($0.023/GB), but data transfer is $0.09/GB
- External downloads can dominate the bill

❌ **Underestimating Redpanda:**
- Base tier: $150/mo (includes 100K events/sec)
- Common assumption: "just ingesting PiXie" → easy underestimate

❌ **Not accounting for backup retention:**
- 7-year retention (regulatory requirement) → Glacier costs add up
- ITAR audit trails must be immutable → storage design impacts cost

❌ **Choosing EC2 instance size wrong:**
- t3.large: $80/mo per node (general compute)
- c5.large: $85/mo per node (compute-optimized)
- Small difference compounds across 2–4 nodes + 12 months

❌ **Logging at debug level by default:**
- Ingestion cost: $0.50/GB
- 100 GB/month (info) = $50
- 300 GB/month (debug) = $150
- 3x difference!

## Testing & Validation

Run the tool with sample inputs to verify calculations:

```bash
# Verify minimal scenario calculation
python main.py --scenario minimal --format text

# Verify all three match documentation
python main.py --compare --format json | grep "total_monthly"
```

Expected outputs:
- Minimal: $612/mo ($5,508 in 2026, $7,344 in 2027)
- Recommended: $1,134/mo ($10,206 in 2026, $13,608 in 2027)
- Full Cloud: $2,016/mo ($18,144 in 2026, $24,192 in 2027)

## Related Documents

- [aws-comprehensive-utility-usage.md](../docs/analysis/aws-comprehensive-utility-usage.md) — Full cost breakdown (source for this tool)
- [aws-cost-estimate-data-collection.md](../docs/analysis/aws-cost-estimate-data-collection.md) — Stakeholder questionnaire
- [aws-cost-estimate-to-approval.md](../docs/analysis/aws-cost-estimate-to-approval.md) — Workflow and deliverables
- [README-COST-ESTIMATE.md](../docs/analysis/README-COST-ESTIMATE.md) — Master reference

## Future Enhancements

- [ ] Load responses from YAML/JSON configuration files
- [ ] Interactive CLI (prompt for inputs)
- [ ] Sensitivity analysis (what if egress doubles?)
- [ ] Historical cost tracking (compare estimates over time)
- [ ] AWS Cost Explorer API integration (actual vs. estimated)
- [ ] Excel export with charts
- [ ] Per-researcher cost breakdown
- [ ] Spot instance support (cheaper but less reliable)

## License

As part of NeutronOS project (UT Computational Nuclear Engineering).

## Contact

For questions about this tool:
- Cost methodology: See [aws-comprehensive-utility-usage.md](../docs/analysis/aws-comprehensive-utility-usage.md)
- Stakeholder inputs: See [aws-cost-estimate-data-collection.md](../docs/analysis/aws-cost-estimate-data-collection.md)
- Project timeline: See [README-COST-ESTIMATE.md](../docs/analysis/README-COST-ESTIMATE.md)
