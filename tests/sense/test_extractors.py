"""Unit and integration tests for signal extractors."""

import json
import pytest
from pathlib import Path

from tools.agents.sense.extractors.gitlab_diff import GitLabDiffExtractor
from tools.agents.sense.extractors.freetext import FreetextExtractor
from tools.agents.sense.extractors.voice import VoiceExtractor
from tools.agents.sense.extractors.transcript import TranscriptExtractor
from tools.agents.sense.correlator import Correlator
from tools.agents.sense.gateway import Gateway


# ─── GitLab Diff Extractor ───


class TestGitLabDiffExtractor:
    """Tests for the pure-Python GitLab diff extractor."""

    def test_name(self):
        extractor = GitLabDiffExtractor()
        assert extractor.name == "gitlab_diff"

    def test_can_handle_valid_json(self, sample_gitlab_export):
        extractor = GitLabDiffExtractor()
        assert extractor.can_handle(sample_gitlab_export)

    def test_can_handle_invalid_file(self, tmp_path):
        extractor = GitLabDiffExtractor()
        txt = tmp_path / "notes.txt"
        txt.write_text("not a gitlab export")
        assert not extractor.can_handle(txt)

    def test_single_export_summary(self, sample_gitlab_export):
        """Single export produces summary signals."""
        extractor = GitLabDiffExtractor()
        extraction = extractor.extract(sample_gitlab_export)

        assert not extraction.errors
        assert len(extraction.signals) > 0

        # Should have commit summary and stale repo signals
        types = {s.signal_type for s in extraction.signals}
        assert "progress" in types or "status_change" in types

    def test_diff_two_exports(self, sample_gitlab_export, sample_gitlab_export_previous):
        """Diffing two exports produces new commit signals."""
        extractor = GitLabDiffExtractor()
        extraction = extractor.extract(
            sample_gitlab_export, previous=sample_gitlab_export_previous
        )

        assert not extraction.errors
        assert len(extraction.signals) > 0

        # Should detect new commits (abc123, def456 are new vs old123)
        commit_signals = [
            s for s in extraction.signals
            if s.metadata.get("event") == "new_commits"
        ]
        assert len(commit_signals) > 0

    def test_diff_detects_new_issues(self, sample_gitlab_export, sample_gitlab_export_previous):
        """Diff detects newly opened issues."""
        extractor = GitLabDiffExtractor()
        extraction = extractor.extract(
            sample_gitlab_export, previous=sample_gitlab_export_previous
        )

        issue_signals = [
            s for s in extraction.signals
            if s.metadata.get("event") == "issue_opened"
        ]
        assert len(issue_signals) > 0

    def test_diff_detects_new_contributors(self, sample_gitlab_export, sample_gitlab_export_previous):
        """Diff detects new contributors."""
        extractor = GitLabDiffExtractor()
        extraction = extractor.extract(
            sample_gitlab_export, previous=sample_gitlab_export_previous
        )

        contributor_signals = [
            s for s in extraction.signals
            if s.metadata.get("event") == "new_contributor"
        ]
        # Bob Jones is new compared to previous export
        assert len(contributor_signals) > 0

    def test_confidence_always_1(self, sample_gitlab_export):
        """All GitLab signals should have confidence=1.0."""
        extractor = GitLabDiffExtractor()
        extraction = extractor.extract(sample_gitlab_export)

        for signal in extraction.signals:
            assert signal.confidence == 1.0

    def test_invalid_json(self, tmp_path):
        """Handles corrupt JSON gracefully."""
        bad_file = tmp_path / "gitlab_export_bad.json"
        bad_file.write_text("not valid json {{{")

        extractor = GitLabDiffExtractor()
        extraction = extractor.extract(bad_file)
        assert len(extraction.errors) > 0

    def test_nonexistent_file(self, tmp_path):
        """Handles missing file gracefully."""
        extractor = GitLabDiffExtractor()
        extraction = extractor.extract(tmp_path / "nonexistent.json")
        assert len(extraction.errors) > 0

    def test_real_export(self, repo_root):
        """Integration: process the actual gitlab export if available."""
        exports_dir = repo_root / "tools" / "exports"
        exports = sorted(exports_dir.glob("gitlab_export_*.json"))
        if not exports:
            pytest.skip("No gitlab exports available")

        extractor = GitLabDiffExtractor()
        extraction = extractor.extract(exports[-1])
        assert not extraction.errors
        assert len(extraction.signals) > 0


# ─── Freetext Extractor ───


class TestFreetextExtractor:
    """Tests for the freetext extractor."""

    def test_name(self):
        assert FreetextExtractor().name == "freetext"

    def test_can_handle_md(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("# Meeting notes")
        assert FreetextExtractor().can_handle(f)

    def test_can_handle_txt(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("Some notes")
        assert FreetextExtractor().can_handle(f)

    def test_cannot_handle_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}")
        assert not FreetextExtractor().can_handle(f)

    def test_extract_without_llm(self, tmp_path):
        """Without LLM, produces a single raw signal."""
        f = tmp_path / "notes.md"
        f.write_text("Alice discussed the bubble flow project status.")

        extractor = FreetextExtractor()
        extraction = extractor.extract(f)

        assert not extraction.errors
        assert len(extraction.signals) == 1
        assert extraction.signals[0].signal_type == "raw"
        assert extraction.signals[0].confidence == 0.3

    def test_extract_with_correlator(self, tmp_path, tmp_config):
        """With correlator, resolves people and initiative mentions."""
        f = tmp_path / "notes.md"
        f.write_text("Alice discussed Project Alpha progress with Bob.")

        correlator = Correlator(config_dir=tmp_config)
        extractor = FreetextExtractor()
        extraction = extractor.extract(f, correlator=correlator)

        assert len(extraction.signals) == 1
        signal = extraction.signals[0]
        assert "Alice Smith" in signal.people
        assert "Project Alpha" in signal.initiatives

    def test_long_text_truncation(self, tmp_path):
        """Long text is truncated in raw_text field."""
        f = tmp_path / "long.md"
        f.write_text("x" * 5000)

        extractor = FreetextExtractor()
        extraction = extractor.extract(f)

        assert len(extraction.signals[0].raw_text) <= 2000

    def test_nonexistent_file(self, tmp_path):
        extractor = FreetextExtractor()
        extraction = extractor.extract(tmp_path / "ghost.md")
        assert len(extraction.errors) > 0


# ─── Voice Extractor ───


class TestVoiceExtractor:
    """Tests for the voice memo extractor."""

    def test_name(self):
        assert VoiceExtractor().name == "voice"

    def test_supported_extensions(self):
        extractor = VoiceExtractor()
        assert ".m4a" in extractor.SUPPORTED_EXTENSIONS
        assert ".wav" in extractor.SUPPORTED_EXTENSIONS
        assert ".mp3" in extractor.SUPPORTED_EXTENSIONS

    def test_cannot_handle_text(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("text")
        assert not VoiceExtractor().can_handle(f)

    def test_graceful_degradation_without_whisper(self, tmp_path):
        """When whisper is not installed, returns informative error."""
        f = tmp_path / "memo.m4a"
        f.write_bytes(b"fake audio data")

        extractor = VoiceExtractor()
        extraction = extractor.extract(f)

        # Should have an error about whisper not being installed,
        # OR succeed if whisper happens to be installed
        if extraction.errors:
            assert any("whisper" in e.lower() for e in extraction.errors)


# ─── Transcript Extractor ───


class TestTranscriptExtractor:
    """Tests for the transcript extractor."""

    def test_name(self):
        assert TranscriptExtractor().name == "transcript"

    def test_can_handle_transcript(self, tmp_path):
        f = tmp_path / "meeting_transcript.md"
        f.write_text("# Meeting Transcript\nDiscussion about X")
        assert TranscriptExtractor().can_handle(f)

    def test_can_handle_teams_dir(self, tmp_path):
        teams = tmp_path / "teams"
        teams.mkdir()
        f = teams / "notes.md"
        f.write_text("Meeting notes")
        assert TranscriptExtractor().can_handle(f)

    def test_does_not_handle_random_md(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# README")
        assert not TranscriptExtractor().can_handle(f)

    def test_extract_without_llm(self, tmp_path, tmp_config):
        """Without LLM, produces a raw signal with correlator matching."""
        f = tmp_path / "meeting_transcript.md"
        f.write_text("Alice presented Project Alpha progress. Bob raised a blocker.")

        correlator = Correlator(config_dir=tmp_config)
        extractor = TranscriptExtractor()
        extraction = extractor.extract(f, correlator=correlator)

        assert len(extraction.signals) == 1
        signal = extraction.signals[0]
        assert signal.signal_type == "raw"
        assert "Alice Smith" in signal.people
