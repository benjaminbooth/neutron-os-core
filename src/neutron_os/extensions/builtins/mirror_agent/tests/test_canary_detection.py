"""Canary detection tests — verify the LLM reviewer catches known-bad content.

These tests are the "bombword" red-team layer: they create synthetic files
containing terms that must NEVER appear in the public mirror, then assert
the reviewer flags them. If any canary test passes clean, the gate is broken.

This file itself contains the canary terms only inside strings passed to the
LLM — it does not constitute a leak, since the test file is never the subject
of review and the terms appear in a clearly controlled test context.

Design: each canary covers a different category of sensitive content so that
regressions in one category don't hide behind passes in others.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gateway_with_response(response_text: str):
    """Build a mock gateway that returns a fixed LLM response."""
    gateway = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = response_text
    gateway.complete.return_value = mock_resp
    return gateway


def _real_gateway():
    """Return the real gateway if an LLM is configured, else None."""
    try:
        from neutron_os.infra.gateway import Gateway
        g = Gateway()
        return g if g.active_provider else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Unit canaries — mock gateway, deterministic
# ---------------------------------------------------------------------------

class TestUnitCanaries:
    """Fast canaries using mocked LLM responses.

    These verify that the reviewer correctly interprets REVIEW_NEEDED responses
    for each sensitive content category. They don't hit the real LLM.
    """

    CATEGORIES = [
        (
            "staff_name",
            "Dr. Kevin Clarno is the department head.",
            "VERDICT: REVIEW_NEEDED\nFINDINGS:\n- Staff name: Kevin Clarno\nRECOMMENDATION: Redact.",
        ),
        (
            "internal_hostname",
            "Connect to rsicc-gitlab.tacc.utexas.edu for access.",
            "VERDICT: REVIEW_NEEDED\nFINDINGS:\n- Internal hostname: rsicc-gitlab.tacc.utexas.edu\nRECOMMENDATION: Redact.",
        ),
        (
            "ip_address",
            "Server is at 128.62.248.232, Ubuntu 24.04.",
            "VERDICT: REVIEW_NEEDED\nFINDINGS:\n- Internal IP address: 128.62.248.232\nRECOMMENDATION: Remove.",
        ),
        (
            "budget_figure",
            "AWS budget request: $1,300/month for medium tier.",
            "VERDICT: REVIEW_NEEDED\nFINDINGS:\n- Budget figure: $1,300/month\nRECOMMENDATION: Remove financial details.",
        ),
        (
            "project_codename",
            "The NETL_BackPacks project is tracked in Linear.",
            "VERDICT: REVIEW_NEEDED\nFINDINGS:\n- Internal project codename: NETL_BackPacks\nRECOMMENDATION: Redact.",
        ),
        (
            "student_name",
            "Jeongwon Seo leads the TRIGA Digital Twin.",
            "VERDICT: REVIEW_NEEDED\nFINDINGS:\n- Staff/student name: Jeongwon Seo\nRECOMMENDATION: Redact.",
        ),
        (
            "grant_details",
            "NEUP 2026 grant portfolio — multiple PIs, pre-decisional.",
            "VERDICT: REVIEW_NEEDED\nFINDINGS:\n- Pre-decisional grant reference: NEUP 2026\nRECOMMENDATION: Remove.",
        ),
    ]

    @pytest.mark.parametrize("category,content,llm_response", CATEGORIES)
    def test_canary_flagged(self, category, content, llm_response, tmp_path):
        """Canary content in category '{category}' must be flagged REVIEW_NEEDED."""
        from neutron_os.extensions.builtins.mirror_agent.reviewer import _review_file

        canary = tmp_path / f"canary_{category}.py"
        canary.write_text(f"# Canary test\nSECRET = '{content}'\n")

        gateway = _make_gateway_with_response(llm_response)
        review = _review_file(canary, tmp_path, gateway)

        assert review.verdict == "REVIEW_NEEDED", (
            f"Canary '{category}' was not flagged — gate may be broken.\n"
            f"Content: {content!r}\nFindings: {review.findings}"
        )
        assert len(review.findings) >= 1, (
            f"Canary '{category}' flagged but no findings extracted."
        )


# ---------------------------------------------------------------------------
# Integration canaries — real LLM, skipped if no provider
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIntegrationCanaries:
    """Live canaries that send synthetic sensitive content to the real LLM.

    These run in CI where ANTHROPIC_API_KEY is set, and can be run locally
    with a configured LLM. They validate that the actual model catches leaks,
    not just that we parse structured responses correctly.
    """

    @pytest.fixture(autouse=True)
    def require_llm(self):
        gateway = _real_gateway()
        if gateway is None:
            pytest.skip("No LLM provider configured")
        self.gateway = gateway

    def _assert_flagged(self, content: str, category: str, tmp_path: Path):
        from neutron_os.extensions.builtins.mirror_agent.reviewer import _review_file
        canary = tmp_path / f"canary_{category}.txt"
        canary.write_text(content)
        review = _review_file(canary, tmp_path, self.gateway)
        assert review.verdict == "REVIEW_NEEDED", (
            f"LLM missed canary '{category}': {content!r}\n"
            f"Findings: {review.findings}\nRecommendation: {review.recommendation}"
        )

    def test_catches_internal_hostname(self, tmp_path):
        self._assert_flagged(
            "Primary server: rsicc-gitlab.tacc.utexas.edu — requires VPN.",
            "hostname", tmp_path,
        )

    def test_catches_ip_address(self, tmp_path):
        self._assert_flagged(
            "Host: 128.62.248.232 (Ubuntu 24.04, neut serve running)",
            "ip", tmp_path,
        )

    def test_catches_budget_figure(self, tmp_path):
        self._assert_flagged(
            "Infrastructure cost estimate: $1,300/month (recommended medium tier).",
            "budget", tmp_path,
        )

    def test_catches_full_staff_name(self, tmp_path):
        self._assert_flagged(
            "Contact Dr. Kevin Clarno for budget approval.",
            "staff_name", tmp_path,
        )

    def test_catches_student_name(self, tmp_path):
        self._assert_flagged(
            "Jeongwon Seo built the live TRIGA monitoring dashboard.",
            "student_name", tmp_path,
        )

    def test_catches_internal_project_codename(self, tmp_path):
        self._assert_flagged(
            "The NETL_BackPacks project integrates sensor data from the DAQ system.",
            "codename", tmp_path,
        )

    def test_does_not_flag_generic_nuclear_terms(self, tmp_path):
        """Nuclear physics terminology should not be flagged as sensitive."""
        from neutron_os.extensions.builtins.mirror_agent.reviewer import _review_file
        canary = tmp_path / "physics.py"
        canary.write_text(
            "# Neutron transport simulation\n"
            "# Uses OpenMC for Monte Carlo particle transport\n"
            "CHERENKOV_THRESHOLD_MEV = 0.511\n"
            "NEUTRON_FLUX_UNIT = 'n/cm²/s'\n"
        )
        review = _review_file(canary, tmp_path, self.gateway)
        assert review.verdict == "CLEAR", (
            f"Generic nuclear physics terms incorrectly flagged.\n"
            f"Findings: {review.findings}"
        )
