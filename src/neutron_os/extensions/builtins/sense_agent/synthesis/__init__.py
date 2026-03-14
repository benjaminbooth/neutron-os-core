"""Synthesis module - transforms signal clusters into actionable outputs."""

from .prd_updater import PRDUpdater, PRDUpdateDraft
from .briefing_generator import BriefingGenerator, DesignBriefing

__all__ = [
    "PRDUpdater",
    "PRDUpdateDraft",
    "BriefingGenerator",
    "DesignBriefing",
]
