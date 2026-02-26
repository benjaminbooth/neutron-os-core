"""Synthesizer — merges extracted signals into changelog drafts.

Takes all Signal objects from all extractors, groups by initiative and
signal_type, and produces:
1. drafts/changelog_YYYY-MM-DD.md — tab-separated paste-ready format
2. drafts/weekly_summary_YYYY-MM-DD.md — prose summary

Signal staleness tracking:
- Signals are hashed and tracked in signal_manifest.json
- By default, only unreported signals are included in changelogs
- Use include_all=True to see all signals (e.g., for full audit)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tools.agents.sense.models import Signal, Changelog, ChangelogEntry, SignalManifest, DATE_FORMAT_ISO


# Drafts directory: tools/agents/drafts/
_AGENTS_DIR = Path(__file__).resolve().parent.parent
DRAFTS_DIR = _AGENTS_DIR / "drafts"


class Synthesizer:
    """Merge signals into human-reviewable changelog drafts."""

    def __init__(self, drafts_dir: Path | None = None):
        self.drafts_dir = drafts_dir or DRAFTS_DIR
        self.manifest = SignalManifest()
        self._last_synthesized_signals: list[Signal] = []  # Track for marking as reported

    def synthesize(
        self,
        signals: list[Signal],
        date: str | None = None,
        include_all: bool = False,
    ) -> Changelog:
        """Group signals by initiative/type and build a Changelog.

        Args:
            signals: All signals to consider.
            date: Changelog date (default: today).
            include_all: If True, include already-reported signals (marked with †).
                        If False (default), only include new/unreported signals.

        Returns:
            Changelog with filtered entries.
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime(DATE_FORMAT_ISO)

        # Filter out already-reported signals unless include_all is True
        total_signals = len(signals)
        if include_all:
            filtered_signals = signals
            skipped = 0
        else:
            filtered_signals = self.manifest.filter_unreported(signals)
            skipped = total_signals - len(filtered_signals)

        # Track which signals we're including so we can mark them as reported
        self._last_synthesized_signals = filtered_signals.copy()
        self._last_changelog_date = date

        # Group signals by initiative
        by_initiative: dict[str, dict[str, list[Signal]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for signal in filtered_signals:
            initiatives = signal.initiatives if signal.initiatives else ["Uncategorized"]
            for init_name in initiatives:
                by_initiative[init_name][signal.signal_type].append(signal)

        # Build changelog entries
        entries = []
        for initiative in sorted(by_initiative.keys()):
            type_groups = by_initiative[initiative]
            for signal_type in sorted(type_groups.keys()):
                type_signals = type_groups[signal_type]
                for signal in type_signals:
                    entries.append(ChangelogEntry(
                        initiative=initiative,
                        signal_type=signal_type,
                        detail=signal.detail,
                        people=signal.people,
                        sources=[signal.source],
                        confidence=signal.confidence,
                    ))

        # Build summary
        new_count = len(filtered_signals)
        init_count = len(by_initiative)
        people_set = set()
        for s in filtered_signals:
            people_set.update(s.people)

        if skipped > 0:
            summary = (
                f"Week of {date}: {new_count} new signals across {init_count} initiatives, "
                f"involving {len(people_set)} people. ({skipped} previously reported signals omitted)"
            )
        else:
            summary = (
                f"Week of {date}: {new_count} signals across {init_count} initiatives, "
                f"involving {len(people_set)} people."
            )

        return Changelog(date=date, entries=entries, summary=summary)

    def mark_as_reported(self) -> int:
        """Mark all signals from the last synthesize() as reported.

        Call this after successfully writing the changelog to prevent
        the same signals from appearing in future changelogs.

        Returns:
            Number of signals marked as reported.
        """
        if not self._last_synthesized_signals:
            return 0

        self.manifest.mark_batch_reported(
            self._last_synthesized_signals,
            self._last_changelog_date,
        )
        count = len(self._last_synthesized_signals)
        self._last_synthesized_signals = []  # Clear after marking
        return count

    def get_reported_count(self) -> int:
        """Return total number of signals that have been reported."""
        return self.manifest.get_reported_count()

    def write_changelog(self, changelog: Changelog) -> Path:
        """Write changelog to drafts/ in tab-separated format."""
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        path = self.drafts_dir / f"changelog_{changelog.date}.md"

        lines = [
            f"# Changelog — {changelog.date}",
            "",
            f"> {changelog.summary}",
            "",
            "| Initiative | Type | Detail | People | Source | Confidence |",
            "|-----------|------|--------|--------|--------|------------|",
        ]

        for entry in changelog.entries:
            people_str = ", ".join(entry.people) if entry.people else "—"
            sources_str = ", ".join(entry.sources) if entry.sources else "—"
            detail_clean = entry.detail.replace("|", "/").replace("\n", " ")
            lines.append(
                f"| {entry.initiative} | {entry.signal_type} | "
                f"{detail_clean} | {people_str} | {sources_str} | "
                f"{entry.confidence:.1f} |"
            )

        lines.append("")
        lines.append(f"*Generated: {changelog.generated_at}*")
        lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_weekly_summary(self, changelog: Changelog) -> Path:
        """Write a prose weekly summary to drafts/."""
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        path = self.drafts_dir / f"weekly_summary_{changelog.date}.md"

        # Group entries by initiative for prose
        by_initiative: dict[str, list[ChangelogEntry]] = defaultdict(list)
        for entry in changelog.entries:
            by_initiative[entry.initiative].append(entry)

        lines = [
            f"# Weekly Summary — {changelog.date}",
            "",
            changelog.summary,
            "",
        ]

        for initiative in sorted(by_initiative.keys()):
            entries = by_initiative[initiative]
            lines.append(f"## {initiative}")
            lines.append("")

            # Group by type within initiative
            by_type: dict[str, list[ChangelogEntry]] = defaultdict(list)
            for entry in entries:
                by_type[entry.signal_type].append(entry)

            type_labels = {
                "progress": "Progress",
                "blocker": "Blockers",
                "decision": "Decisions",
                "action_item": "Action Items",
                "status_change": "Status Changes",
                "raw": "Notes",
            }

            for signal_type, label in type_labels.items():
                type_entries = by_type.get(signal_type, [])
                if not type_entries:
                    continue

                lines.append(f"### {label}")
                lines.append("")
                for entry in type_entries:
                    people = f" ({', '.join(entry.people)})" if entry.people else ""
                    lines.append(f"- {entry.detail}{people}")
                lines.append("")

        lines.append(f"*Generated: {changelog.generated_at}*")
        lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path
