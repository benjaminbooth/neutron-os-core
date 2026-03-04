"""Unit tests for the signal synthesizer."""

import pytest
from pathlib import Path

from tools.pipelines.sense.models import Signal, Changelog
from tools.pipelines.sense.synthesizer import Synthesizer


@pytest.fixture
def sample_signals():
    """Create a set of test signals for synthesis."""
    return [
        Signal(
            source="gitlab_diff",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="Added feature X",
            people=["Alice"],
            initiatives=["Project Alpha"],
            signal_type="progress",
            detail="Alice: 3 new commits in alpha-project",
            confidence=1.0,
        ),
        Signal(
            source="gitlab_diff",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="Closed issue #5",
            people=["Bob"],
            initiatives=["Project Alpha"],
            signal_type="progress",
            detail="Issue closed: #5 Fix CI pipeline",
            confidence=1.0,
        ),
        Signal(
            source="freetext",
            timestamp="2026-02-14T10:00:00Z",
            raw_text="Blocked on data access",
            people=["Charlie"],
            initiatives=["Project Beta"],
            signal_type="blocker",
            detail="Charlie blocked on data access permissions",
            confidence=0.7,
        ),
        Signal(
            source="gitlab_diff",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="No recent commits",
            initiatives=["Project Gamma"],
            signal_type="status_change",
            detail="Repository stale: gamma-project",
            confidence=1.0,
        ),
    ]


class TestSynthesizer:
    """Tests for changelog synthesis."""

    def test_synthesize_groups_by_initiative(self, sample_signals):
        synth = Synthesizer()
        changelog = synth.synthesize(sample_signals, date="2026-02-15")

        initiatives = {e.initiative for e in changelog.entries}
        assert "Project Alpha" in initiatives
        assert "Project Beta" in initiatives
        assert "Project Gamma" in initiatives

    def test_synthesize_preserves_signal_types(self, sample_signals):
        synth = Synthesizer()
        changelog = synth.synthesize(sample_signals)

        types = {e.signal_type for e in changelog.entries}
        assert "progress" in types
        assert "blocker" in types
        assert "status_change" in types

    def test_synthesize_builds_summary(self, sample_signals):
        synth = Synthesizer()
        changelog = synth.synthesize(sample_signals, date="2026-02-15")

        assert "4 signals" in changelog.summary
        assert "3 initiatives" in changelog.summary

    def test_synthesize_empty_signals(self):
        synth = Synthesizer()
        changelog = synth.synthesize([])
        assert len(changelog.entries) == 0
        assert "0 signals" in changelog.summary

    def test_write_changelog(self, sample_signals, tmp_path):
        synth = Synthesizer(drafts_dir=tmp_path)
        changelog = synth.synthesize(sample_signals, date="2026-02-15")
        path = synth.write_changelog(changelog)

        assert path.exists()
        assert path.name == "changelog_2026-02-15.md"

        content = path.read_text()
        assert "Project Alpha" in content
        assert "progress" in content

    def test_write_weekly_summary(self, sample_signals, tmp_path):
        synth = Synthesizer(drafts_dir=tmp_path)
        changelog = synth.synthesize(sample_signals, date="2026-02-15")
        path = synth.write_weekly_summary(changelog)

        assert path.exists()
        assert path.name == "weekly_summary_2026-02-15.md"

        content = path.read_text()
        assert "## Project Alpha" in content
        assert "### Blockers" in content or "### Progress" in content

    def test_changelog_table_format(self, sample_signals, tmp_path):
        """Verify the changelog uses proper markdown table format."""
        synth = Synthesizer(drafts_dir=tmp_path)
        changelog = synth.synthesize(sample_signals, date="2026-02-15")
        path = synth.write_changelog(changelog)

        content = path.read_text()
        lines = content.strip().splitlines()

        # Should have table header and separator
        table_lines = [l for l in lines if l.startswith("|")]
        assert len(table_lines) >= 3  # Header + separator + at least 1 row

    def test_uncategorized_signals(self, tmp_path):
        """Signals without initiatives get grouped under 'Uncategorized'."""
        signals = [
            Signal(
                source="freetext",
                timestamp="2026-02-15T10:00:00Z",
                raw_text="Random note",
                signal_type="raw",
                detail="Something happened",
                confidence=0.3,
            ),
        ]
        synth = Synthesizer(drafts_dir=tmp_path)
        changelog = synth.synthesize(signals)

        assert any(e.initiative == "Uncategorized" for e in changelog.entries)
