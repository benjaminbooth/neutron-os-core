"""
Output reporting for cost estimates.

Formats CostBreakdown objects as:
- Markdown tables
- JSON
- CSV
- Plain text summaries
"""

import json
import csv
from io import StringIO
from typing import List
from .data_models import CostBreakdown


class CostReporter:
    """Generates reports from cost breakdowns."""

    @staticmethod
    def to_markdown_table(breakdowns: List[CostBreakdown]) -> str:
        """
        Format cost breakdowns as markdown table.

        Shows all 9 service categories + external services.
        """
        lines = [
            "# NeutronOS AWS Cost Estimate",
            "",
            "## Monthly Cost Breakdown (by Service Category)",
            "",
        ]

        # Create header with scenario names
        header = "| Service Category | " + " | ".join(b.scenario_name for b in breakdowns) + " |"
        lines.append(header)
        lines.append("|---|" + "|".join(["---"] * len(breakdowns)) + "|")

        # Compute
        compute_row = "| **Compute (EKS, Lambda)** | " + " | ".join(
            f"${b.compute.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(compute_row)

        # Storage
        storage_row = "| **Storage (S3, EBS)** | " + " | ".join(
            f"${b.storage.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(storage_row)

        # Database
        database_row = "| **Database (RDS)** | " + " | ".join(
            f"${b.database.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(database_row)

        # Analytics
        analytics_row = "| **Analytics (Athena)** | " + " | ".join(
            f"${b.analytics.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(analytics_row)

        # Networking
        networking_row = "| **Networking (Data Transfer, NAT)** | " + " | ".join(
            f"${b.networking.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(networking_row)

        # Security
        security_row = "| **Security (KMS, Secrets)** | " + " | ".join(
            f"${b.security.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(security_row)

        # Monitoring
        monitoring_row = "| **Monitoring (CloudWatch)** | " + " | ".join(
            f"${b.monitoring.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(monitoring_row)

        # Developer Tools
        devtools_row = "| **Developer Tools (ECR)** | " + " | ".join(
            f"${b.developer_tools.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(devtools_row)

        # Management
        management_row = "| **Management (Backup)** | " + " | ".join(
            f"${b.management.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(management_row)

        # Subtotal AWS
        aws_subtotal_row = "| **AWS Services Subtotal** | " + " | ".join(
            f"${b.aws_subtotal_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(aws_subtotal_row)

        # External Services
        external_row = "| **External Services (Redpanda, Claude)** | " + " | ".join(
            f"${b.external_services.total_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(external_row)

        # Subtotal before contingency
        subtotal_row = "| **Subtotal (AWS + External)** | " + " | ".join(
            f"${b.subtotal_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(subtotal_row)

        # Contingency
        contingency_row = "| **Contingency (20%)** | " + " | ".join(
            f"${b.contingency_monthly:.0f}" for b in breakdowns
        ) + " |"
        lines.append(contingency_row)

        # Total
        total_row = "| **TOTAL MONTHLY** | " + " | ".join(
            f"**${b.total_monthly:.0f}**" for b in breakdowns
        ) + " |"
        lines.append(total_row)

        lines.append("")

        # Annual summaries
        lines.append("## Annual & Biennial Costs")
        lines.append("")

        annual_table = "| Timeframe | " + " | ".join(b.scenario_name for b in breakdowns) + " |"
        lines.append(annual_table)
        lines.append("|---|" + "|".join(["---"] * len(breakdowns)) + "|")

        cost_2026 = "| 2026 (9 months, Feb-Dec) | " + " | ".join(
            f"${b.annual_cost_2026_9mo():,.0f}" for b in breakdowns
        ) + " |"
        lines.append(cost_2026)

        cost_2027 = "| 2027 (12 months) | " + " | ".join(
            f"${b.annual_cost_2027_12mo():,.0f}" for b in breakdowns
        ) + " |"
        lines.append(cost_2027)

        cost_total = "| **Phase 1 Total (2026-2027)** | " + " | ".join(
            f"**${b.biennial_cost():,.0f}**" for b in breakdowns
        ) + " |"
        lines.append(cost_total)

        return "\n".join(lines)

    @staticmethod
    def to_detailed_markdown(breakdown: CostBreakdown) -> str:
        """
        Generate detailed markdown report for a single scenario.

        Includes full line-item breakdown for each service category.
        """
        lines = [
            f"# Cost Estimate: {breakdown.scenario_name}",
            "",
            "**Generated:** Phase 1 (2026-2027)",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"- **Monthly Cost:** ${breakdown.total_monthly:,.2f}",
            f"- **2026 Cost (9 months):** ${breakdown.annual_cost_2026_9mo():,.2f}",
            f"- **2027 Cost (12 months):** ${breakdown.annual_cost_2027_12mo():,.2f}",
            f"- **Phase 1 Total:** ${breakdown.biennial_cost():,.2f}",
            "",
            "---",
            "",
            "## Service-by-Service Breakdown",
            "",
        ]

        # Compute
        lines.extend([
            "### 1. COMPUTE ($" + f"{breakdown.compute.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| EKS Control Plane | ${breakdown.compute.eks_control_plane_monthly:.2f} |",
            f"| EKS Worker Nodes ({breakdown.compute.num_worker_nodes} nodes) | ${breakdown.compute.eks_worker_nodes_monthly * breakdown.compute.num_worker_nodes:.2f} |",
            f"| Load Balancer | ${breakdown.compute.load_balancer_monthly:.2f} |",
            f"| EBS Storage | ${breakdown.compute.ebs_storage_monthly:.2f} |",
            # NAT Gateway costs are shown under Networking
            f"| VPC Endpoints | ${breakdown.compute.vpc_endpoints_monthly:.2f} |",
            f"| Lambda | ${breakdown.compute.lambda_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.compute.total_monthly:.2f}** |",
            "",
        ])

        # Storage
        lines.extend([
            "### 2. STORAGE ($" + f"{breakdown.storage.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| S3 Standard (hot, 2yr) | ${breakdown.storage.s3_standard_monthly:.2f} |",
            f"| S3 Glacier (cold, 7yr) | ${breakdown.storage.s3_glacier_monthly:.2f} |",
            f"| EBS Volumes | ${breakdown.storage.ebs_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.storage.total_monthly:.2f}** |",
            "",
        ])

        # Database
        lines.extend([
            "### 3. DATABASE ($" + f"{breakdown.database.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| RDS PostgreSQL | ${breakdown.database.rds_postgresql_monthly:.2f} |",
            f"| ElastiCache | ${breakdown.database.elasticache_monthly:.2f} |",
            f"| DynamoDB | ${breakdown.database.dynamodb_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.database.total_monthly:.2f}** |",
            "",
        ])

        # Analytics
        lines.extend([
            "### 4. ANALYTICS ($" + f"{breakdown.analytics.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| Athena | ${breakdown.analytics.athena_monthly:.2f} |",
            f"| Glue | ${breakdown.analytics.glue_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.analytics.total_monthly:.2f}** |",
            "",
        ])

        # Networking
        lines.extend([
            "### 5. NETWORKING ($" + f"{breakdown.networking.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| Data Egress (Internet) | ${breakdown.networking.data_egress_monthly:.2f} |",
            f"| NAT Gateway ({getattr(breakdown.networking, 'nat_gateway_count', 1)}) | ${breakdown.networking.nat_gateway_monthly * getattr(breakdown.networking, 'nat_gateway_count', 1):.2f} |",
            f"| VPC Endpoints | ${breakdown.networking.vpc_endpoints_monthly:.2f} |",
            f"| Cross-Region Transfer | ${breakdown.networking.cross_region_transfer_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.networking.total_monthly:.2f}** |",
            "",
        ])

        # Security
        lines.extend([
            "### 6. SECURITY ($" + f"{breakdown.security.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| KMS (Encryption) | ${breakdown.security.kms_monthly:.2f} |",
            f"| Secrets Manager | ${breakdown.security.secrets_manager_monthly:.2f} |",
            f"| AWS Config | ${breakdown.security.aws_config_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.security.total_monthly:.2f}** |",
            "",
        ])

        # Monitoring
        lines.extend([
            "### 7. MONITORING ($" + f"{breakdown.monitoring.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| CloudWatch Logs | ${breakdown.monitoring.cloudwatch_logs_monthly:.2f} |",
            f"| CloudWatch Metrics | ${breakdown.monitoring.cloudwatch_metrics_monthly:.2f} |",
            f"| CloudWatch Alarms | ${breakdown.monitoring.cloudwatch_alarms_monthly:.2f} |",
            f"| X-Ray | ${breakdown.monitoring.xray_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.monitoring.total_monthly:.2f}** |",
            "",
        ])

        # Developer Tools
        lines.extend([
            "### 8. DEVELOPER TOOLS ($" + f"{breakdown.developer_tools.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| ECR (Container Registry) | ${breakdown.developer_tools.ecr_monthly:.2f} |",
            f"| CodeBuild | ${breakdown.developer_tools.codebuild_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.developer_tools.total_monthly:.2f}** |",
            "",
        ])

        # Management
        lines.extend([
            "### 9. MANAGEMENT ($" + f"{breakdown.management.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| AWS Backup | ${breakdown.management.aws_backup_monthly:.2f} |",
            f"| Cost Explorer | ${breakdown.management.cost_explorer_monthly:.2f} |",
            f"| Service Quotas | ${breakdown.management.service_quotas_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.management.total_monthly:.2f}** |",
            "",
        ])

        # External Services
        lines.extend([
            "### 10. EXTERNAL SERVICES ($" + f"{breakdown.external_services.total_monthly:.0f}/mo)",
            "",
            "| Component | Monthly Cost |",
            "|---|---|",
            f"| Redpanda Cloud (Streaming) | ${breakdown.external_services.redpanda_cloud_monthly:.2f} |",
            f"| Claude API (RAG) | ${breakdown.external_services.claude_api_monthly:.2f} |",
            f"| OpenAI Embeddings | ${breakdown.external_services.openai_embeddings_monthly:.2f} |",
            f"| **Subtotal** | **${breakdown.external_services.total_monthly:.2f}** |",
            "",
        ])

        # Summary
        lines.extend([
            "---",
            "",
            "## Cost Summary",
            "",
            "| Item | Amount |",
            "|---|---|",
            f"| AWS Services Subtotal | ${breakdown.aws_subtotal_monthly:,.2f} |",
            f"| External Services Subtotal | ${breakdown.external_subtotal_monthly:,.2f} |",
            # Pre-waiver subtotal = post-waiver subtotal + egress waiver (if any)
            f"| Pre-Waiver Subtotal | ${breakdown.subtotal_monthly + getattr(breakdown, 'egress_waiver_monthly', 0.0):,.2f} |",
            f"| Egress Waiver | ${getattr(breakdown, 'egress_waiver_monthly', 0.0):,.2f} |",
            f"| POC Credit | ${getattr(breakdown, 'poc_credit_monthly', 0.0):,.2f} |",
            f"| **Subtotal** | **${breakdown.subtotal_monthly:,.2f}** |",
            f"| Contingency (20%) | ${breakdown.contingency_monthly:,.2f} |",
            f"| **TOTAL MONTHLY** | **${breakdown.total_monthly:,.2f}** |",
            "",
            "### Annual Projections",
            "",
            f"- **2026** (9 months, Feb-Dec): ${breakdown.annual_cost_2026_9mo():,.2f}",
            f"- **2027** (12 months): ${breakdown.annual_cost_2027_12mo():,.2f}",
            f"- **Phase 1 Total**: ${breakdown.biennial_cost():,.2f}",
        ])

        return "\n".join(lines)

    @staticmethod
    def to_json(breakdowns: List[CostBreakdown]) -> str:
        """Export cost breakdowns as JSON."""
        data = {
            "scenarios": [b.to_dict() for b in breakdowns],
            "metadata": {
                "project": "NeutronOS Phase 1",
                "phase": "2026-2027",
                "num_scenarios": len(breakdowns),
            }
        }
        return json.dumps(data, indent=2)

    @staticmethod
    def to_csv(breakdowns: List[CostBreakdown]) -> str:
        """Export cost breakdowns as CSV."""
        output = StringIO()
        writer = csv.writer(output)

        # Header
        header = ["Service Category"] + [b.scenario_name for b in breakdowns]
        writer.writerow(header)

        # Data rows
        categories = [
            ("Compute", lambda b: b.compute.total_monthly),
            ("Storage", lambda b: b.storage.total_monthly),
            ("Database", lambda b: b.database.total_monthly),
            ("Analytics", lambda b: b.analytics.total_monthly),
            ("Networking", lambda b: b.networking.total_monthly),
            ("Security", lambda b: b.security.total_monthly),
            ("Monitoring", lambda b: b.monitoring.total_monthly),
            ("Developer Tools", lambda b: b.developer_tools.total_monthly),
            ("Management", lambda b: b.management.total_monthly),
            ("External Services", lambda b: b.external_services.total_monthly),
            ("AWS Subtotal", lambda b: b.aws_subtotal_monthly),
            ("External Subtotal", lambda b: b.external_subtotal_monthly),
            ("Subtotal", lambda b: b.subtotal_monthly),
            ("Contingency (20%)", lambda b: b.contingency_monthly),
            ("TOTAL MONTHLY", lambda b: b.total_monthly),
            ("2026 (9mo)", lambda b: b.annual_cost_2026_9mo()),
            ("2027 (12mo)", lambda b: b.annual_cost_2027_12mo()),
            ("Phase 1 Total", lambda b: b.biennial_cost()),
        ]

        for category_name, cost_getter in categories:
            row = [category_name] + [f"${cost_getter(b):.2f}" for b in breakdowns]
            writer.writerow(row)

        # Add explicit machine-readable total_monthly row for downstream tools/tests
        total_row = ["total_monthly"] + [f"{b.total_monthly:.2f}" for b in breakdowns]
        writer.writerow(total_row)

        return output.getvalue()

    @staticmethod
    def to_plain_text_summary(breakdown: CostBreakdown) -> str:
        """Generate a plain-text summary."""
        return f"""
{'='*60}
NEUTROSOS PHASE 1 COST ESTIMATE: {breakdown.scenario_name}
{'='*60}

MONTHLY COSTS BY SERVICE CATEGORY
{'─'*60}
Compute (EKS, Lambda)            ${breakdown.compute.total_monthly:>12,.2f}
Storage (S3, EBS)                ${breakdown.storage.total_monthly:>12,.2f}
Database (RDS)                   ${breakdown.database.total_monthly:>12,.2f}
Analytics (Athena)               ${breakdown.analytics.total_monthly:>12,.2f}
Networking (Data Transfer, NAT)  ${breakdown.networking.total_monthly:>12,.2f}
Security (KMS, Secrets)          ${breakdown.security.total_monthly:>12,.2f}
Monitoring (CloudWatch)          ${breakdown.monitoring.total_monthly:>12,.2f}
Developer Tools (ECR)            ${breakdown.developer_tools.total_monthly:>12,.2f}
Management (Backup)              ${breakdown.management.total_monthly:>12,.2f}
{'─'*60}
AWS Services Subtotal            ${breakdown.aws_subtotal_monthly:>12,.2f}

External Services (Redpanda, Claude) ${breakdown.external_services.total_monthly:>8,.2f}

Subtotal                         ${breakdown.subtotal_monthly:>12,.2f}
Contingency (20%)                ${breakdown.contingency_monthly:>12,.2f}
{'='*60}
TOTAL MONTHLY                    ${breakdown.total_monthly:>12,.2f}
{'='*60}

ANNUAL & BIENNIAL PROJECTIONS
{'─'*60}
2026 (Feb-Dec, 9 months):        ${breakdown.annual_cost_2026_9mo():>12,.2f}
2027 (Full year, 12 months):     ${breakdown.annual_cost_2027_12mo():>12,.2f}
Phase 1 Total (2026-2027):       ${breakdown.biennial_cost():>12,.2f}
{'='*60}
"""
