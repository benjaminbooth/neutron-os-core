"""
NeutronOS AWS Cost Estimation Tool.

Calculates comprehensive AWS infrastructure costs for NeutronOS Phase 1
based on stakeholder inputs and pre-defined scenarios.

Usage:
    from cost_estimation_tool import scenarios, CostCalculator

    # Get a pre-defined scenario
    recommended = scenarios.scenario_recommended()

    # Or calculate custom costs from stakeholder responses
    from data_models import StakeholderResponses
    responses = StakeholderResponses(...)
    calculator = CostCalculator(responses)
    breakdown = calculator.calculate_full_breakdown()
"""

from .data_models import (
    StakeholderResponses,
    CostBreakdown,
    PhysicsInputs,
    OperationsInputs,
    PiXieInputs,
    MLInputs,
    ComplianceInputs,
)
from .cost_calculator import CostCalculator
from .scenarios import get_scenario, scenario_minimal, scenario_recommended, scenario_full_cloud
from .reporter import CostReporter

__version__ = "0.1.0"
__all__ = [
    "StakeholderResponses",
    "CostBreakdown",
    "PhysicsInputs",
    "OperationsInputs",
    "PiXieInputs",
    "MLInputs",
    "ComplianceInputs",
    "CostCalculator",
    "get_scenario",
    "scenario_minimal",
    "scenario_recommended",
    "scenario_full_cloud",
    "CostReporter",
]
