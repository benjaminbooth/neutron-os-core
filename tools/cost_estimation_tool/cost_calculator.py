"""
Cost calculator for NeutronOS AWS infrastructure.

Implements formulas from aws-comprehensive-utility-usage.md.
Each method calculates costs for one service category based on stakeholder inputs.
"""

from .data_models import (
    StakeholderResponses,
    ComputeCosts,
    StorageCosts,
    DatabaseCosts,
    AnalyticsCosts,
    NetworkingCosts,
    SecurityCosts,
    MonitoringCosts,
    DeveloperToolsCosts,
    ManagementCosts,
    ExternalServicesCosts,
    CostBreakdown,
)


class CostCalculator:
    """Calculates AWS and external service costs based on stakeholder inputs."""

    def __init__(self, responses: StakeholderResponses):
        """Initialize with stakeholder responses."""
        self.responses = responses

    def calculate_compute_costs(self) -> ComputeCosts:
        """
        Section 1: COMPUTE ($200-400/mo).

        Components:
        - EKS control plane: $72/mo (fixed)
        - EC2 worker nodes: $30-80/mo per node (depends on instance type)
        - Load balancer: $16/mo
        - EBS storage: $10/mo
        - NAT Gateway: $32/mo per AZ
        - VPC Endpoints: $7/mo
        - Lambda: $5-20/mo
        """
        # Determine number of worker nodes based on operational needs
        num_nodes = 2  # Default
        if self.responses.operations.operating_hours_per_week:
            if self.responses.operations.operating_hours_per_week > 100:
                num_nodes = 4  # High utilization → more nodes
            elif self.responses.operations.operating_hours_per_week > 50:
                num_nodes = 3

        costs = ComputeCosts(
            eks_control_plane_monthly=72.0,
            eks_worker_nodes_monthly=80.0,  # t3.large compute
            num_worker_nodes=num_nodes,
            load_balancer_monthly=16.0,
            ebs_storage_monthly=10.0,
            vpc_endpoints_monthly=7.0,
            lambda_monthly=10.0,
        )
        return costs

    def calculate_storage_costs(self) -> StorageCosts:
        """
        Section 2: STORAGE ($50-150/mo).

        Components:
        - S3 Standard (hot, 2yr retention): $0.023/GB/mo
        - S3 Glacier (cold, 7yr retention): $0.004/GB/mo
        - EBS (node disks): $10/mo

        Formula:
        S3 Standard = (daily_volume_gb / 365) × 2 years × $0.023/GB/mo
        S3 Glacier = (daily_volume_gb / 365) × 5 years × $0.004/GB/mo
        """
        # Baseline: 150GB/year from data collection
        annual_volume_gb = 150.0

        # Adjust if PiXie included
        if self.responses.pixie.phase_1_inclusion and self.responses.pixie.current_daily_data_volume_gb:
            pixie_annual_gb = self.responses.pixie.current_daily_data_volume_gb * 365
            annual_volume_gb += pixie_annual_gb

        # S3 Standard (hot data, 2-year retention)
        # Average storage: annual_volume_gb / 365 × 2 years × $0.023/GB/mo
        daily_avg_gb = annual_volume_gb / 365
        s3_standard_monthly = (daily_avg_gb * 2) * 0.023

        # S3 Glacier (cold archive, 5-year retention after hot period)
        # Average storage: annual_volume_gb / 365 × 5 years × $0.004/GB/mo
        s3_glacier_monthly = (daily_avg_gb * 5) * 0.004

        costs = StorageCosts(
            s3_standard_monthly=s3_standard_monthly,
            s3_glacier_monthly=s3_glacier_monthly,
            ebs_monthly=20.0,
        )
        return costs

    def calculate_database_costs(self) -> DatabaseCosts:
        """
        Section 3: DATABASE ($100-200/mo).

        Components:
        - RDS PostgreSQL: $40-100/mo (depends on instance size)
        - ElastiCache (optional): $0-50/mo
        - DynamoDB (skip Phase 1): $0

        Instance sizing based on data volume and query patterns.
        """
        # Determine RDS instance size
        # db.t3.micro: $40/mo (dev/test)
        # db.t3.small: $75/mo (small production)
        # db.t3.medium: $100/mo (medium production)

        rds_monthly = 75.0  # Default to small for Phase 1

        if self.responses.operations.operating_hours_per_week:
            if self.responses.operations.operating_hours_per_week > 100:
                rds_monthly = 100.0
            elif self.responses.operations.operating_hours_per_week < 20:
                rds_monthly = 40.0

        # ElastiCache (optional): skip unless dashboard performance is critical
        elasticache_monthly = 0.0  # Skip for Phase 1

        costs = DatabaseCosts(
            rds_postgresql_monthly=rds_monthly,
            elasticache_monthly=elasticache_monthly,
            dynamodb_monthly=0.0,
        )
        return costs

    def calculate_analytics_costs(self) -> AnalyticsCosts:
        """
        Section 4: ANALYTICS & BIG DATA ($5-30/mo).

        Components:
        - Athena: $0.005/GB scanned
        - Glue: skip (using dbt instead)

        Cost depends on query patterns.
        """
        # Athena cost: assume 10-50 ad-hoc queries per month
        # Each query scans ~1GB on average
        queries_per_month = 20  # Conservative estimate
        avg_scan_gb_per_query = 1.0
        athena_cost_per_gb = 0.005

        athena_monthly = (queries_per_month * avg_scan_gb_per_query) * athena_cost_per_gb

        costs = AnalyticsCosts(
            athena_monthly=athena_monthly,
            glue_monthly=0.0,  # Skip; using dbt
        )
        return costs

    def calculate_networking_costs(self) -> NetworkingCosts:
        """
        Section 5: NETWORKING ($100-300/mo).

        THE BIGGEST VARIABLE AND OFTEN OVERLOOKED!

        Components:
        - Data egress (internet): $0.09/GB (varies widely)
        - Cross-region transfer: $0.02/GB
        - NAT Gateway: $32-64/mo
        - VPC Endpoints: $7-30/mo

        Egress patterns heavily depend on whether researchers download data.
        """
        # Data egress scenarios:
        # Scenario A (minimal): data stays in AWS, ~$5-10/mo
        # Scenario B (moderate): 10 researchers × 10GB/mo = ~$20-50/mo
        # Scenario C (heavy): external collaboration = ~$100-200/mo

        data_egress_gb_per_month = 50.0  # Default: moderate scenario

        # Adjust based on external collaborator access
        if self.responses.operations.will_external_collaborators_access:
            data_egress_gb_per_month = 200.0

        # Adjust based on PiXie data characteristics
        if (self.responses.pixie.phase_1_inclusion and
            self.responses.pixie.current_daily_data_volume_gb):
            # PiXie data: assume some egress for analysis/QA
            data_egress_gb_per_month += self.responses.pixie.current_daily_data_volume_gb * 20

        egress_cost = data_egress_gb_per_month * 0.09  # $0.09/GB

        # Cross-region transfer (if multi-region enabled)
        cross_region_gb_per_month = 0.0
        if self.responses.compliance.multi_region_disaster_recovery:
            cross_region_gb_per_month = 150.0  # Daily backups to 2nd region

        cross_region_cost = cross_region_gb_per_month * 0.02

        # NAT Gateway count depends on HA strategy
        nat_gateway_count = 1
        if self.responses.compliance.multi_region_disaster_recovery:
            nat_gateway_count = 2

        costs = NetworkingCosts(
            data_egress_monthly=egress_cost,
            nat_gateway_monthly=32.0,
            nat_gateway_count=nat_gateway_count,
            vpc_endpoints_monthly=7.0,
            cross_region_transfer_monthly=cross_region_cost,
        )
        return costs

    def calculate_security_costs(self) -> SecurityCosts:
        """
        Section 6: SECURITY & COMPLIANCE ($20-50/mo).

        Components:
        - KMS (encryption keys): $1/key/mo + $0.03/10K API calls
        - Secrets Manager: $0.40/secret/mo
        - AWS Config (compliance): $0-20/mo (if ITAR required)
        """
        # Assume 2-3 KMS keys (S3, RDS, EBS)
        num_kms_keys = 3
        kms_monthly = (num_kms_keys * 1.0) + 2.0  # Keys + API calls

        # Assume 5-10 secrets (DB password, Claude API key, etc.)
        num_secrets = 7
        secrets_manager_monthly = num_secrets * 0.40

        # AWS Config for compliance monitoring (if ITAR)
        aws_config_monthly = 0.0
        if self.responses.compliance.regulatory_frameworks:
            if "ITAR" in self.responses.compliance.regulatory_frameworks:
                aws_config_monthly = 15.0  # Enable compliance tracking

        costs = SecurityCosts(
            kms_monthly=kms_monthly,
            secrets_manager_monthly=secrets_manager_monthly,
            aws_config_monthly=aws_config_monthly,
        )
        return costs

    def calculate_monitoring_costs(self) -> MonitoringCosts:
        """
        Section 7: MONITORING & OBSERVABILITY ($30-100/mo).

        Components:
        - CloudWatch logs: $0.50/GB ingested + $0.03/GB stored
        - CloudWatch metrics: $0.30/custom metric
        - CloudWatch alarms: $0.10/alarm
        - X-Ray: skip Phase 1

        Log costs heavily depend on logging verbosity (errors vs. debug).
        """
        # CloudWatch logs depend on verbosity
        # Errors only: ~30 GB/month
        # Info level: ~100 GB/month
        # Debug level: ~300 GB/month

        log_volume_gb = 100.0  # Default: info level

        if self.responses.ml.debug_logging:
            log_volume_gb = 200.0

        # Log ingestion cost
        ingestion_cost = log_volume_gb * 0.50

        # Log storage cost (30-day retention default)
        storage_cost = log_volume_gb * 0.03

        # Metrics and alarms
        custom_metrics = 10
        metrics_cost = custom_metrics * 0.30

        num_alarms = 20
        alarms_cost = num_alarms * 0.10

        costs = MonitoringCosts(
            cloudwatch_logs_monthly=ingestion_cost + storage_cost,
            cloudwatch_metrics_monthly=metrics_cost,
            cloudwatch_alarms_monthly=alarms_cost,
            xray_monthly=0.0,  # Skip Phase 1
        )
        return costs

    def calculate_developer_tools_costs(self) -> DeveloperToolsCosts:
        """
        Section 8: DEVELOPER TOOLS ($5-30/mo).

        Components:
        - ECR (Docker registry): $0.10/GB/mo
        - CodeBuild: skip (use GitHub Actions)
        """
        # ECR storage: assume 50GB of container images
        ecr_storage_gb = 50.0
        ecr_monthly = ecr_storage_gb * 0.10

        costs = DeveloperToolsCosts(
            ecr_monthly=ecr_monthly,
            codebuild_monthly=0.0,  # Skip; use GitHub Actions
        )
        return costs

    def calculate_management_costs(self) -> ManagementCosts:
        """
        Section 9: MANAGEMENT & GOVERNANCE ($5-20/mo).

        Components:
        - AWS Backup: $0.05/GB/mo
        - Cost Explorer: free
        - Service Quotas: free
        """
        # AWS Backup: assume backups of RDS + EBS
        # Conservative: 100GB backup storage
        backup_storage_gb = 100.0
        backup_monthly = backup_storage_gb * 0.05

        costs = ManagementCosts(
            aws_backup_monthly=backup_monthly,
            cost_explorer_monthly=0.0,  # Free
            service_quotas_monthly=0.0,  # Free
        )
        return costs

    def calculate_external_services_costs(self) -> ExternalServicesCosts:
        """
        Section 10: EXTERNAL SERVICES ($300-500/mo).

        Components:
        - Redpanda Cloud: $150-300/mo if PiXie Phase 1
        - Claude API: $100-400/mo depending on usage
        - OpenAI Embeddings: $0-20/mo (minimal)

        These are often forgotten but can be 30-50% of total cost!
        """
        # Redpanda Cloud (event streaming)
        redpanda_monthly = 0.0
        if self.responses.pixie.phase_1_inclusion:
            redpanda_monthly = 200.0  # Base tier + modest overages

        # Claude API
        # Cost = (input_tokens × $0.003) + (output_tokens × $0.015) per 1M
        # Usage depends on RAG query volume

        queries_per_day = self.responses.ml.expected_claude_queries_per_day or 10.0
        queries_per_month = queries_per_day * 30

        # Conservative: 5K input tokens per query, 500 output tokens
        input_tokens_per_month = queries_per_month * 5000
        output_tokens_per_month = queries_per_month * 500

        input_cost = (input_tokens_per_month / 1_000_000) * 3.0
        output_cost = (output_tokens_per_month / 1_000_000) * 15.0
        claude_api_monthly = input_cost + output_cost

        # OpenAI Embeddings (minimal)
        openai_monthly = 0.0  # Using pgvector locally

        costs = ExternalServicesCosts(
            redpanda_cloud_monthly=redpanda_monthly,
            claude_api_monthly=claude_api_monthly,
            openai_embeddings_monthly=openai_monthly,
        )
        return costs

    def calculate_full_breakdown(
        self,
        scenario_name: str = "Custom",
        poc_credit_percent: float = 0.0,
        apply_egress_waiver: bool = False,
    ) -> CostBreakdown:
        """
        Calculate complete cost breakdown across all 9 service categories + external.

        Optional parameters:
        - `poc_credit_percent`: percentage discount to apply to the final total (e.g. 10.0 for 10%).
        - `apply_egress_waiver`: when True, apply UT's egress-waiver rule (waive egress up to 15% of the bill).

        Returns:
            CostBreakdown with all monthly costs and derived annual/biennial totals.
        """
        breakdown = CostBreakdown(
            scenario_name=scenario_name,
            compute=self.calculate_compute_costs(),
            storage=self.calculate_storage_costs(),
            database=self.calculate_database_costs(),
            analytics=self.calculate_analytics_costs(),
            networking=self.calculate_networking_costs(),
            security=self.calculate_security_costs(),
            monitoring=self.calculate_monitoring_costs(),
            developer_tools=self.calculate_developer_tools_costs(),
            management=self.calculate_management_costs(),
            external_services=self.calculate_external_services_costs(),
        )

        # Apply UT egress waiver guidance: waived egress charges up to 15% of the bill.
        # This is optional and disabled by default to preserve previous behaviour.
        if apply_egress_waiver:
            pre_waiver_subtotal = breakdown.subtotal_monthly
            waiver_cap = pre_waiver_subtotal * 0.15
            waived_amount = min(breakdown.networking.data_egress_monthly, waiver_cap)
            # Record waived amount
            breakdown.egress_waiver_monthly = waived_amount
            # Reduce networking egress and derived totals
            breakdown.networking.data_egress_monthly = max(
                0.0, breakdown.networking.data_egress_monthly - waived_amount
            )
            # Recompute networking and AWS subtotals
            breakdown.networking.total_monthly = (
                breakdown.networking.data_egress_monthly
                + (breakdown.networking.nat_gateway_monthly * breakdown.networking.nat_gateway_count)
                + breakdown.networking.vpc_endpoints_monthly
                + breakdown.networking.cross_region_transfer_monthly
            )
            breakdown.aws_subtotal_monthly = (
                breakdown.compute.total_monthly
                + breakdown.storage.total_monthly
                + breakdown.database.total_monthly
                + breakdown.analytics.total_monthly
                + breakdown.networking.total_monthly
                + breakdown.security.total_monthly
                + breakdown.monitoring.total_monthly
                + breakdown.developer_tools.total_monthly
                + breakdown.management.total_monthly
            )
            breakdown.subtotal_monthly = breakdown.aws_subtotal_monthly + breakdown.external_subtotal_monthly
            breakdown.contingency_monthly = breakdown.subtotal_monthly * breakdown.contingency_percentage
            breakdown.total_monthly = breakdown.subtotal_monthly + breakdown.contingency_monthly

        # Apply optional POC credit (deduct percentage from final total)
        if poc_credit_percent and poc_credit_percent > 0.0:
            credit = breakdown.total_monthly * (poc_credit_percent / 100.0)
            breakdown.poc_credit_monthly = credit
            breakdown.total_monthly = max(0.0, breakdown.total_monthly - credit)

        return breakdown
