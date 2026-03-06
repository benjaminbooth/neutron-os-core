#!/usr/bin/env python3
"""
NeutronOS AWS Cost Estimation Tool - Main CLI.

This tool calculates and reports AWS infrastructure costs for NeutronOS Phase 1
based on stakeholder inputs and pre-defined scenarios.

Usage:
    python main.py --scenario minimal
    python main.py --scenario recommended
    python main.py --scenario full_cloud
    python main.py --compare          # Compare all 3 scenarios
    python main.py --custom           # Use custom stakeholder inputs
"""

import argparse
import json
from pathlib import Path

from .data_models import StakeholderResponses, CostBreakdown
from .cost_calculator import CostCalculator
from .scenarios import get_scenario
from .reporter import CostReporter


def load_stakeholder_responses(filepath: str) -> StakeholderResponses:
    """
    Load stakeholder responses from a JSON file.

    Expected format:
    {
        "physics": { "mpact_states_per_run": 50, ... },
        "operations": { "operating_hours_per_week": 80, ... },
        ...
    }
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Deserialize into StakeholderResponses
    responses = StakeholderResponses()

    if "physics" in data:
        responses.physics = StakeholderResponses(**data["physics"]).__dict__
    # ... (would need more sophisticated deserialization for production)

    return responses


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="NeutronOS AWS Cost Estimation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Calculate costs for minimal scenario (PiXie excluded)
  python main.py --scenario minimal

  # Calculate costs for recommended scenario (PiXie Phase 1)
  python main.py --scenario recommended

  # Calculate costs for full cloud scenario (high-availability)
  python main.py --scenario full_cloud

  # Compare all three scenarios side-by-side
  python main.py --compare

  # Load custom stakeholder responses and calculate costs
  python main.py --custom --input responses.json

  # Export results as JSON
  python main.py --compare --output results.json --format json
        """
    )

    parser.add_argument(
        "--scenario",
        choices=["minimal", "recommended", "full_cloud"],
        help="Pre-defined cost scenario to calculate"
    )

    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare all three scenarios side-by-side"
    )

    parser.add_argument(
        "--custom",
        action="store_true",
        help="Use custom stakeholder inputs"
    )

    parser.add_argument(
        "--input",
        type=str,
        help="Path to stakeholder responses JSON file (for --custom)"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Path to output file (if not specified, prints to stdout)"
    )

    parser.add_argument(
        "--format",
        choices=["markdown", "json", "csv", "text"],
        default="markdown",
        help="Output format (default: markdown)"
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Generate detailed report for a single scenario"
    )

    args = parser.parse_args()

    # Determine which scenarios to calculate
    scenarios_to_calculate: list[CostBreakdown] = []

    if args.compare:
        # Compare all three pre-defined scenarios
        scenarios_to_calculate = [
            get_scenario("minimal"),
            get_scenario("recommended"),
            get_scenario("full_cloud"),
        ]
    elif args.scenario:
        # Single pre-defined scenario
        scenarios_to_calculate = [get_scenario(args.scenario)]
    elif args.custom:
        # Custom scenario based on stakeholder inputs
        if not args.input:
            print("Error: --custom requires --input to specify a JSON responses file")
            return 1

        responses = load_stakeholder_responses(args.input)
        calculator = CostCalculator(responses)
        scenario_name = Path(args.input).stem
        breakdown = calculator.calculate_full_breakdown(scenario_name)
        scenarios_to_calculate = [breakdown]
    else:
        # Default: show all scenarios
        print("No scenario specified. Use --scenario, --compare, or --custom.")
        print("Run with --help for more information.")
        return 1

    # Generate report
    report_content = ""

    if args.format == "markdown":
        if args.detailed and len(scenarios_to_calculate) == 1:
            report_content = CostReporter.to_detailed_markdown(scenarios_to_calculate[0])
        else:
            report_content = CostReporter.to_markdown_table(scenarios_to_calculate)
    elif args.format == "json":
        report_content = CostReporter.to_json(scenarios_to_calculate)
    elif args.format == "csv":
        report_content = CostReporter.to_csv(scenarios_to_calculate)
    elif args.format == "text":
        if len(scenarios_to_calculate) == 1:
            report_content = CostReporter.to_plain_text_summary(scenarios_to_calculate[0])
        else:
            # For multiple scenarios, use markdown format
            report_content = CostReporter.to_markdown_table(scenarios_to_calculate)

    # Output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report_content)
        print(f"✓ Report written to {args.output}")
    else:
        print(report_content)

    return 0


if __name__ == "__main__":
    exit(main())
