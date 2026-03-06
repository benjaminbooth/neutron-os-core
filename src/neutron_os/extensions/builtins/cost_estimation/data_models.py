"""
Data models for NeutronOS AWS cost estimation.

Defines input structures (stakeholder responses) and output structures
(cost breakdowns, scenarios) following the comprehensive utility analysis.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum


class LogLevel(str, Enum):
    """CloudWatch logging level."""
    ERRORS_ONLY = "errors_only"
    INFO = "info"
    DEBUG = "debug"


class LogRetention(str, Enum):
    """CloudWatch log retention period."""
    SEVEN_DAYS = "7_days"
    THIRTY_DAYS = "30_days"
    ONE_YEAR = "1_year"


class HA_Strategy(str, Enum):
    """High availability strategy."""
    SINGLE_AZ = "single_az"
    MULTI_AZ = "multi_az"
    MULTI_REGION = "multi_region"


class Scenario(str, Enum):
    """Pre-defined cost scenarios."""
    MINIMAL = "minimal"
    RECOMMENDED = "recommended"
    FULL_CLOUD = "full_cloud"
    CUSTOM = "custom"


@dataclass
class PhysicsInputs:
    """Section A: MPACT & Physics (from Cole)."""
    mpact_states_per_run: Optional[int] = None
    mpact_wall_clock_minutes: Optional[float] = None
    mpact_compute_location: Optional[str] = None  # "TACC" or "AWS"
    mpact_archive_size_gb: Optional[float] = None
    bias_correction_retraining_frequency: Optional[str] = None  # e.g., "monthly", "quarterly"
    bias_correction_training_data_gb: Optional[float] = None
    uq_methodology: Optional[str] = None  # "Monte Carlo", "Latin Hypercube", etc.


@dataclass
class OperationsInputs:
    """Section B: Operations & Production (from Nick)."""
    operating_hours_per_week: Optional[float] = None
    isotope_types: Optional[List[str]] = None  # e.g., ["Tc-99m", "Mo-99"]
    production_rate_per_week: Optional[float] = None  # GBq or other units
    isotope_modeling_approach: Optional[str] = None
    prediction_validation_frequency: Optional[str] = None  # e.g., "daily", "weekly"
    prediction_validation_methodology: Optional[str] = None
    data_volume_150gb_breakdown: Optional[Dict[str, float]] = None  # e.g., {"CSV": 50, "HDF5": 100}
    will_external_collaborators_access: Optional[bool] = None


@dataclass
class PiXieInputs:
    """Section C: PiXie Hardware (from Max)."""
    phase_1_inclusion: Optional[bool] = None  # BLOCKING GATE
    current_daily_data_volume_gb: Optional[float] = None
    data_format: Optional[str] = None  # e.g., "CSV", "NetCDF", "HDF5"
    operating_schedule_hours_per_day: Optional[float] = None
    peak_data_rate_mb_per_sec: Optional[float] = None


@dataclass
class MLInputs:
    """Section D: ML & Data Engineering (from Jay)."""
    rag_document_count: Optional[int] = None
    rag_corpus_size_mb: Optional[float] = None
    embedding_strategy: Optional[str] = None  # "Claude", "OpenAI", "Local Ollama"
    training_data_volume_gb: Optional[float] = None
    training_frequency: Optional[str] = None  # e.g., "monthly", "quarterly"
    expected_claude_queries_per_day: Optional[float] = None
    shadowcasting_approach: Optional[str] = None
    debug_logging: Optional[bool] = field(default=False)


@dataclass
class ComplianceInputs:
    """Section E: Compliance & Approval (from Dr. Clarno)."""
    regulatory_frameworks: Optional[List[str]] = None  # e.g., ["ITAR", "NRC"]
    aws_region_requirement: Optional[str] = None  # "standard" or "govcloud"
    audit_trail_retention_years: Optional[int] = None
    tacc_allocation_status: Optional[str] = None
    multi_region_disaster_recovery: Optional[bool] = None
    aws_support_level: Optional[str] = None  # "developer", "business", "enterprise"


@dataclass
class StakeholderResponses:
    """Complete set of stakeholder responses."""
    physics: PhysicsInputs = field(default_factory=PhysicsInputs)
    operations: OperationsInputs = field(default_factory=OperationsInputs)
    pixie: PiXieInputs = field(default_factory=PiXieInputs)
    ml: MLInputs = field(default_factory=MLInputs)
    compliance: ComplianceInputs = field(default_factory=ComplianceInputs)


@dataclass
class ComputeCosts:
    """Breakdown of compute costs (Section 1)."""
    eks_control_plane_monthly: float = 72.0
    eks_worker_nodes_monthly: float = 100.0  # per node
    num_worker_nodes: int = 2
    load_balancer_monthly: float = 16.0
    ebs_storage_monthly: float = 10.0
    # NAT Gateway costs moved to NetworkingCosts to avoid double-counting
    vpc_endpoints_monthly: float = 7.0
    lambda_monthly: float = 10.0
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total compute cost."""
        self.total_monthly = (
            self.eks_control_plane_monthly
            + (self.eks_worker_nodes_monthly * self.num_worker_nodes)
            + self.load_balancer_monthly
            + self.ebs_storage_monthly
            # NAT Gateway costs are accounted for in NetworkingCosts
            + self.vpc_endpoints_monthly
            + self.lambda_monthly
        )


@dataclass
class StorageCosts:
    """Breakdown of storage costs (Section 2)."""
    s3_standard_monthly: float = 4.0  # hot data, 2yr
    s3_glacier_monthly: float = 2.0  # cold archive, 7yr
    ebs_monthly: float = 20.0
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total storage cost."""
        self.total_monthly = (
            self.s3_standard_monthly
            + self.s3_glacier_monthly
            + self.ebs_monthly
        )


@dataclass
class DatabaseCosts:
    """Breakdown of database costs (Section 3)."""
    rds_postgresql_monthly: float = 40.0
    elasticache_monthly: float = 0.0
    dynamodb_monthly: float = 0.0
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total database cost."""
        self.total_monthly = (
            self.rds_postgresql_monthly
            + self.elasticache_monthly
            + self.dynamodb_monthly
        )


@dataclass
class AnalyticsCosts:
    """Breakdown of analytics costs (Section 4)."""
    athena_monthly: float = 10.0
    glue_monthly: float = 0.0  # Skip for Phase 1
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total analytics cost."""
        self.total_monthly = self.athena_monthly + self.glue_monthly


@dataclass
class NetworkingCosts:
    """Breakdown of networking costs (Section 5)."""
    data_egress_monthly: float = 50.0  # Most variable; depends on download patterns
    nat_gateway_monthly: float = 32.0
    nat_gateway_count: int = 1
    vpc_endpoints_monthly: float = 7.0
    cross_region_transfer_monthly: float = 0.0
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total networking cost."""
        self.total_monthly = (
            self.data_egress_monthly
            + (self.nat_gateway_monthly * self.nat_gateway_count)
            + self.vpc_endpoints_monthly
            + self.cross_region_transfer_monthly
        )


@dataclass
class SecurityCosts:
    """Breakdown of security costs (Section 6)."""
    kms_monthly: float = 5.0
    secrets_manager_monthly: float = 2.0
    aws_config_monthly: float = 0.0
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total security cost."""
        self.total_monthly = (
            self.kms_monthly
            + self.secrets_manager_monthly
            + self.aws_config_monthly
        )


@dataclass
class MonitoringCosts:
    """Breakdown of monitoring costs (Section 7)."""
    cloudwatch_logs_monthly: float = 30.0
    cloudwatch_metrics_monthly: float = 5.0
    cloudwatch_alarms_monthly: float = 2.0
    xray_monthly: float = 0.0
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total monitoring cost."""
        self.total_monthly = (
            self.cloudwatch_logs_monthly
            + self.cloudwatch_metrics_monthly
            + self.cloudwatch_alarms_monthly
            + self.xray_monthly
        )


@dataclass
class DeveloperToolsCosts:
    """Breakdown of developer tools costs (Section 8)."""
    ecr_monthly: float = 5.0
    codebuild_monthly: float = 0.0  # Skip; use GitHub Actions
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total developer tools cost."""
        self.total_monthly = self.ecr_monthly + self.codebuild_monthly


@dataclass
class ManagementCosts:
    """Breakdown of management costs (Section 9)."""
    aws_backup_monthly: float = 5.0
    cost_explorer_monthly: float = 0.0  # Free
    service_quotas_monthly: float = 0.0  # Free
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total management cost."""
        self.total_monthly = (
            self.aws_backup_monthly
            + self.cost_explorer_monthly
            + self.service_quotas_monthly
        )


@dataclass
class ExternalServicesCosts:
    """Breakdown of external services costs (Section 10)."""
    redpanda_cloud_monthly: float = 0.0  # $150–300 if PiXie Phase 1
    claude_api_monthly: float = 100.0  # $100–400 depending on usage
    openai_embeddings_monthly: float = 0.0  # Minimal; $0–20
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate total external services cost."""
        self.total_monthly = (
            self.redpanda_cloud_monthly
            + self.claude_api_monthly
            + self.openai_embeddings_monthly
        )


@dataclass
class CostBreakdown:
    """Complete monthly cost breakdown across all 9 service categories + external."""
    scenario_name: str
    compute: ComputeCosts
    storage: StorageCosts
    database: DatabaseCosts
    analytics: AnalyticsCosts
    networking: NetworkingCosts
    security: SecurityCosts
    monitoring: MonitoringCosts
    developer_tools: DeveloperToolsCosts
    management: ManagementCosts
    external_services: ExternalServicesCosts
    contingency_percentage: float = 0.20  # 20% contingency

    # Optional policy adjustments (set by caller after construction)
    egress_waiver_monthly: float = field(default=0.0, init=False)
    poc_credit_monthly: float = field(default=0.0, init=False)

    # Calculated fields
    aws_subtotal_monthly: float = field(default=0.0, init=False)
    external_subtotal_monthly: float = field(default=0.0, init=False)
    subtotal_monthly: float = field(default=0.0, init=False)
    contingency_monthly: float = field(default=0.0, init=False)
    total_monthly: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Calculate all derived costs."""
        # AWS services subtotal
        self.aws_subtotal_monthly = (
            self.compute.total_monthly
            + self.storage.total_monthly
            + self.database.total_monthly
            + self.analytics.total_monthly
            + self.networking.total_monthly
            + self.security.total_monthly
            + self.monitoring.total_monthly
            + self.developer_tools.total_monthly
            + self.management.total_monthly
        )

        # External services subtotal
        self.external_subtotal_monthly = self.external_services.total_monthly

        # Total before contingency
        self.subtotal_monthly = self.aws_subtotal_monthly + self.external_subtotal_monthly

        # Contingency (20%)
        self.contingency_monthly = self.subtotal_monthly * self.contingency_percentage

        # Total after contingency
        self.total_monthly = self.subtotal_monthly + self.contingency_monthly

    def annual_cost_2026_9mo(self) -> float:
        """Calculate cost for 2026 (9 months, Feb-Dec)."""
        return self.total_monthly * 9

    def annual_cost_2027_12mo(self) -> float:
        """Calculate cost for 2027 (full year)."""
        return self.total_monthly * 12

    def biennial_cost(self) -> float:
        """Calculate total cost for Phase 1 (9mo + 12mo)."""
        return self.annual_cost_2026_9mo() + self.annual_cost_2027_12mo()

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        return {
            "scenario_name": self.scenario_name,
            "compute": {
                "eks_control_plane": self.compute.eks_control_plane_monthly,
                "eks_worker_nodes": self.compute.eks_worker_nodes_monthly * self.compute.num_worker_nodes,
                "load_balancer": self.compute.load_balancer_monthly,
                    # NAT gateway costs are reported under networking
                "vpc_endpoints": self.compute.vpc_endpoints_monthly,
                "subtotal": self.compute.total_monthly,
            },
            "storage": {
                "s3_standard": self.storage.s3_standard_monthly,
                "s3_glacier": self.storage.s3_glacier_monthly,
                "ebs": self.storage.ebs_monthly,
                "subtotal": self.storage.total_monthly,
            },
            "database": {
                "rds_postgresql": self.database.rds_postgresql_monthly,
                "elasticache": self.database.elasticache_monthly,
                "dynamodb": self.database.dynamodb_monthly,
                "subtotal": self.database.total_monthly,
            },
            "analytics": {
                "athena": self.analytics.athena_monthly,
                "glue": self.analytics.glue_monthly,
                "subtotal": self.analytics.total_monthly,
            },
            "networking": {
                "data_egress": self.networking.data_egress_monthly,
                "nat_gateway": self.networking.nat_gateway_monthly * self.networking.nat_gateway_count,
                "vpc_endpoints": self.networking.vpc_endpoints_monthly,
                "subtotal": self.networking.total_monthly,
            },
            "security": {
                "kms": self.security.kms_monthly,
                "secrets_manager": self.security.secrets_manager_monthly,
                "aws_config": self.security.aws_config_monthly,
                "subtotal": self.security.total_monthly,
            },
            "monitoring": {
                "cloudwatch_logs": self.monitoring.cloudwatch_logs_monthly,
                "cloudwatch_metrics": self.monitoring.cloudwatch_metrics_monthly,
                "cloudwatch_alarms": self.monitoring.cloudwatch_alarms_monthly,
                "xray": self.monitoring.xray_monthly,
                "subtotal": self.monitoring.total_monthly,
            },
            "developer_tools": {
                "ecr": self.developer_tools.ecr_monthly,
                "codebuild": self.developer_tools.codebuild_monthly,
                "subtotal": self.developer_tools.total_monthly,
            },
            "management": {
                "aws_backup": self.management.aws_backup_monthly,
                "cost_explorer": self.management.cost_explorer_monthly,
                "service_quotas": self.management.service_quotas_monthly,
                "subtotal": self.management.total_monthly,
            },
            "external_services": {
                "redpanda_cloud": self.external_services.redpanda_cloud_monthly,
                "claude_api": self.external_services.claude_api_monthly,
                "openai_embeddings": self.external_services.openai_embeddings_monthly,
                "subtotal": self.external_services.total_monthly,
            },
            "aws_subtotal": self.aws_subtotal_monthly,
            "external_subtotal": self.external_subtotal_monthly,
            "subtotal": self.subtotal_monthly,
            "contingency": self.contingency_monthly,
            "total_monthly": self.total_monthly,
            "annual_2026_9mo": self.annual_cost_2026_9mo(),
            "annual_2027_12mo": self.annual_cost_2027_12mo(),
            "biennial_total": self.biennial_cost(),
        }
