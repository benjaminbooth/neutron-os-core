"""Sense & Synthesis Pipeline for NeutronOS.

The full product development feedback loop:
  Sense → Synthesize → Create → Publish → Sense

Extracts design signals, clusters by PRD, synthesizes updates,
and tracks loop health metrics to increase velocity over time.
"""

from .models import Signal, Extraction, Changelog, ChangelogEntry, SignalManifest
from .extractors import CalendarExtractor, NotesExtractor, FeedbackExtractor
from .clustering import PRDClusterer, SignalCluster
from .synthesis import PRDUpdater, PRDUpdateDraft, BriefingGenerator, DesignBriefing
from .loop import (
    LoopStage,
    FeedbackType,
    SubscriberRole,
    ArtifactType,
    Subscription,
    LoopIteration,
    LoopHealthMetrics,
    LoopTracker,
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "Signal",
    "Extraction",
    "Changelog",
    "ChangelogEntry",
    "SignalManifest",
    # Extractors
    "CalendarExtractor",
    "NotesExtractor",
    "FeedbackExtractor",
    # Clustering
    "PRDClusterer",
    "SignalCluster",
    # Synthesis
    "PRDUpdater",
    "PRDUpdateDraft",
    "BriefingGenerator",
    "DesignBriefing",
    # Loop Tracking
    "LoopStage",
    "FeedbackType",
    "SubscriberRole",
    "ArtifactType",
    "Subscription",
    "LoopIteration",
    "LoopHealthMetrics",
    "LoopTracker",
]
