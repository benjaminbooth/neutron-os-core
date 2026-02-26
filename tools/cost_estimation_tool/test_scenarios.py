#!/usr/bin/env python3
"""
Test script to validate cost estimations against expected values.

Verifies that the three pre-defined scenarios produce costs matching
the comprehensive utility analysis document.
"""

from .scenarios import scenario_minimal, scenario_recommended, scenario_full_cloud
from .reporter import CostReporter


def test_scenario_minimal():
    """Validate minimal scenario: $612/mo."""
    breakdown = scenario_minimal()

    expected_monthly = 612.0
    actual_monthly = breakdown.total_monthly
    tolerance = 10.0  # Allow ±$10 variance

    print("Testing Minimal Scenario...")
    print(f"  Expected: ${expected_monthly:.2f}/mo")
    print(f"  Actual:   ${actual_monthly:.2f}/mo")
    print(f"  Match: {abs(actual_monthly - expected_monthly) < tolerance}")

    # Detailed breakdown
    print(f"  - AWS Subtotal: ${breakdown.aws_subtotal_monthly:.2f}")
    print(f"  - External Subtotal: ${breakdown.external_subtotal_monthly:.2f}")
    print(f"  - Contingency: ${breakdown.contingency_monthly:.2f}")

    # Annual costs
    print(f"  - 2026 (9mo): ${breakdown.annual_cost_2026_9mo():,.2f}")
    print(f"  - 2027 (12mo): ${breakdown.annual_cost_2027_12mo():,.2f}")
    print(f"  - Phase 1 Total: ${breakdown.biennial_cost():,.2f}")
    print()

    assert abs(actual_monthly - expected_monthly) < tolerance, \
        f"Minimal scenario cost mismatch: expected ${expected_monthly}, got ${actual_monthly}"


def test_scenario_recommended():
    """Validate recommended scenario: $1,134/mo."""
    breakdown = scenario_recommended()

    expected_monthly = 1134.0
    actual_monthly = breakdown.total_monthly
    tolerance = 20.0  # Allow ±$20 variance

    print("Testing Recommended Scenario...")
    print(f"  Expected: ${expected_monthly:.2f}/mo")
    print(f"  Actual:   ${actual_monthly:.2f}/mo")
    print(f"  Match: {abs(actual_monthly - expected_monthly) < tolerance}")

    # Detailed breakdown
    print(f"  - AWS Subtotal: ${breakdown.aws_subtotal_monthly:.2f}")
    print(f"  - External Subtotal: ${breakdown.external_subtotal_monthly:.2f}")
    print(f"  - Contingency: ${breakdown.contingency_monthly:.2f}")

    # Annual costs
    print(f"  - 2026 (9mo): ${breakdown.annual_cost_2026_9mo():,.2f}")
    print(f"  - 2027 (12mo): ${breakdown.annual_cost_2027_12mo():,.2f}")
    print(f"  - Phase 1 Total: ${breakdown.biennial_cost():,.2f}")
    print()

    assert abs(actual_monthly - expected_monthly) < tolerance, \
        f"Recommended scenario cost mismatch: expected ${expected_monthly}, got ${actual_monthly}"


def test_scenario_full_cloud():
    """Validate full cloud scenario: $2,016/mo."""
    breakdown = scenario_full_cloud()

    expected_monthly = 2016.0
    actual_monthly = breakdown.total_monthly
    tolerance = 30.0  # Allow ±$30 variance

    print("Testing Full Cloud Scenario...")
    print(f"  Expected: ${expected_monthly:.2f}/mo")
    print(f"  Actual:   ${actual_monthly:.2f}/mo")
    print(f"  Match: {abs(actual_monthly - expected_monthly) < tolerance}")

    # Detailed breakdown
    print(f"  - AWS Subtotal: ${breakdown.aws_subtotal_monthly:.2f}")
    print(f"  - External Subtotal: ${breakdown.external_subtotal_monthly:.2f}")
    print(f"  - Contingency: ${breakdown.contingency_monthly:.2f}")

    # Annual costs
    print(f"  - 2026 (9mo): ${breakdown.annual_cost_2026_9mo():,.2f}")
    print(f"  - 2027 (12mo): ${breakdown.annual_cost_2027_12mo():,.2f}")
    print(f"  - Phase 1 Total: ${breakdown.biennial_cost():,.2f}")
    print()

    assert abs(actual_monthly - expected_monthly) < tolerance, \
        f"Full cloud scenario cost mismatch: expected ${expected_monthly}, got ${actual_monthly}"


def test_comparison():
    """Test the comparison report generation."""
    print("Testing comparison report generation...")

    scenarios = [
        scenario_minimal(),
        scenario_recommended(),
        scenario_full_cloud(),
    ]

    # Generate markdown table
    markdown_report = CostReporter.to_markdown_table(scenarios)
    assert "Minimal" in markdown_report, "Markdown report missing Minimal scenario"
    assert "Recommended" in markdown_report, "Markdown report missing Recommended scenario"
    assert "Full Cloud" in markdown_report, "Markdown report missing Full Cloud scenario"

    print("  ✓ Markdown report generated successfully")

    # Generate JSON
    json_report = CostReporter.to_json(scenarios)
    assert '"scenarios"' in json_report, "JSON report missing scenarios field"
    assert 'Minimal' in json_report, "JSON report missing Minimal scenario"

    print("  ✓ JSON report generated successfully")

    # Generate CSV
    csv_report = CostReporter.to_csv(scenarios)
    assert "Minimal" in csv_report, "CSV report missing Minimal scenario"
    assert "total_monthly" in csv_report.lower(), "CSV report missing total_monthly"

    print("  ✓ CSV report generated successfully")
    print()


def test_service_cost_ranges():
    """Verify that service costs fall within expected ranges."""
    print("Testing service cost ranges...")

    minimal = scenario_minimal()
    recommended = scenario_recommended()
    full = scenario_full_cloud()

    # Compute should be $200-350/mo
    compute_costs = [minimal.compute.total_monthly, recommended.compute.total_monthly, full.compute.total_monthly]
    assert all(200 <= c <= 350 for c in compute_costs), f"Compute costs out of range: {compute_costs}"
    print(f"  ✓ Compute costs in expected range: {[f'${c:.0f}' for c in compute_costs]}")

    # Storage should be $50-150/mo
    storage_costs = [minimal.storage.total_monthly, recommended.storage.total_monthly, full.storage.total_monthly]
    assert all(50 <= s <= 150 for s in storage_costs), f"Storage costs out of range: {storage_costs}"
    print(f"  ✓ Storage costs in expected range: {[f'${s:.0f}' for s in storage_costs]}")

    # Database should be $40-150/mo
    db_costs = [minimal.database.total_monthly, recommended.database.total_monthly, full.database.total_monthly]
    assert all(40 <= d <= 150 for d in db_costs), f"Database costs out of range: {db_costs}"
    print(f"  ✓ Database costs in expected range: {[f'${d:.0f}' for d in db_costs]}")

    # Networking should be $100-300/mo
    net_costs = [minimal.networking.total_monthly, recommended.networking.total_monthly, full.networking.total_monthly]
    assert all(100 <= n <= 300 for n in net_costs), f"Networking costs out of range: {net_costs}"
    print(f"  ✓ Networking costs in expected range: {[f'${n:.0f}' for n in net_costs]}")

    print()


def test_annual_calculations():
    """Verify annual cost calculations."""
    print("Testing annual cost calculations...")

    breakdown = scenario_recommended()

    # 2026: 9 months (Feb-Dec)
    annual_2026 = breakdown.annual_cost_2026_9mo()
    expected_2026 = breakdown.total_monthly * 9
    assert abs(annual_2026 - expected_2026) < 0.01, f"2026 cost mismatch: {annual_2026} vs {expected_2026}"
    print(f"  ✓ 2026 (9mo) calculation correct: ${annual_2026:,.2f}")

    # 2027: 12 months
    annual_2027 = breakdown.annual_cost_2027_12mo()
    expected_2027 = breakdown.total_monthly * 12
    assert abs(annual_2027 - expected_2027) < 0.01, f"2027 cost mismatch: {annual_2027} vs {expected_2027}"
    print(f"  ✓ 2027 (12mo) calculation correct: ${annual_2027:,.2f}")

    # Biennial total
    biennial = breakdown.biennial_cost()
    expected_biennial = annual_2026 + annual_2027
    assert abs(biennial - expected_biennial) < 0.01, f"Biennial cost mismatch: {biennial} vs {expected_biennial}"
    print(f"  ✓ Phase 1 total (2026-2027) correct: ${biennial:,.2f}")

    print()


def main():
    """Run all tests."""
    print("=" * 70)
    print("NeutronOS AWS Cost Estimation Tool - Validation Tests")
    print("=" * 70)
    print()

    try:
        test_scenario_minimal()
        test_scenario_recommended()
        test_scenario_full_cloud()
        test_comparison()
        test_service_cost_ranges()
        test_annual_calculations()

        print("=" * 70)
        print("✓ All tests passed!")
        print("=" * 70)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
