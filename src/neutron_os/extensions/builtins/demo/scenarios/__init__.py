"""Demo scenarios for NeutronOS."""

from __future__ import annotations

from .collaborator import build_scenario as build_collaborator

SCENARIOS = {
    "collaborator": build_collaborator,
}


def list_scenarios() -> list[dict[str, str]]:
    """Return available scenarios with their metadata."""
    result = []
    for slug, builder in SCENARIOS.items():
        scenario = builder()
        result.append({
            "slug": slug,
            "name": scenario.name,
            "tagline": scenario.tagline,
            "acts": str(len(scenario.acts)),
        })
    return result
