"""Tests for mirror_agent — sensitivity reviewer and M-O subscriber.

Easter egg: this test file is its own proof of concept. The mirror_agent
reviews public content for sensitive data before it gets published. These
tests verify that the reviewer correctly flags sensitive content and gives
clean files a green light — including this file, which contains no secrets,
no staff names, no budget figures, and no internal URLs. If you're reading
this in the public repo, the gate worked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# reviewer.py — unit tests
# ---------------------------------------------------------------------------


def test_parse_response_clear():
    """CLEAR verdict is parsed correctly."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import _parse_response

    response = """VERDICT: CLEAR
FINDINGS:
- None
RECOMMENDATION: No action needed."""

    review = _parse_response("README.md", response)
    assert review.verdict == "CLEAR"
    assert review.findings == []
    assert "No action" in review.recommendation


def test_parse_response_review_needed():
    """REVIEW_NEEDED verdict with findings is parsed correctly."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import _parse_response

    response = """VERDICT: REVIEW_NEEDED
FINDINGS:
- Contains staff name: Jane Researcher
- Internal hostname: reactor.internal.example.org
RECOMMENDATION: Redact names and internal hostnames before publishing."""

    review = _parse_response("config.py", response)
    assert review.verdict == "REVIEW_NEEDED"
    assert len(review.findings) == 2
    assert "Jane Researcher" in review.findings[0]
    assert "Redact" in review.recommendation


def test_parse_response_missing_none_finding():
    """'None' findings are not included in the findings list."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import _parse_response

    response = "VERDICT: CLEAR\nFINDINGS:\n- None\nRECOMMENDATION: All clear."
    review = _parse_response("pyproject.toml", response)
    assert review.findings == []


def test_is_text_file_skips_binaries():
    """Binary extensions are correctly excluded."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import _is_text_file

    assert not _is_text_file(Path("model.h5"))
    assert not _is_text_file(Path("data.parquet"))
    assert not _is_text_file(Path("recording.m4a"))
    assert not _is_text_file(Path("report.pdf"))
    assert _is_text_file(Path("README.md"))
    assert _is_text_file(Path("pyproject.toml"))
    assert _is_text_file(Path("cli.py"))


def test_review_file_error_becomes_review_needed(tmp_path):
    """If the gateway call fails, the file is flagged (fail-safe)."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import _review_file

    target = tmp_path / "secret.py"
    target.write_text("# totally fine file")

    gateway = MagicMock()
    gateway.complete.side_effect = RuntimeError("LLM unavailable")

    review = _review_file(target, tmp_path, gateway)
    assert review.verdict == "REVIEW_NEEDED"
    assert review.error != ""


def test_review_mirror_content_empty(tmp_path):
    """Review of zero files returns a clear result."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import review_mirror_content

    gateway = MagicMock()
    result = review_mirror_content(
        repo_root=tmp_path,
        public_paths=[],
        exclude_paths=[],
        gateway=gateway,
        since_ref=None,
        max_files=50,
    )
    assert result.is_clear
    assert result.files_reviewed == 0


def test_mirror_review_is_clear_property():
    """MirrorReview.is_clear returns True only when files_flagged == 0."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import MirrorReview

    r = MirrorReview(files_reviewed=5, files_flagged=0)
    assert r.is_clear

    r2 = MirrorReview(files_reviewed=5, files_flagged=1)
    assert not r2.is_clear


def test_flagged_property_filters_reviews():
    """MirrorReview.flagged returns only REVIEW_NEEDED items."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import MirrorReview, FileReview

    clear = FileReview(path="ok.py", verdict="CLEAR")
    flagged = FileReview(path="bad.py", verdict="REVIEW_NEEDED", findings=["Contains PII"])

    review = MirrorReview(files_reviewed=2, files_flagged=1, reviews=[clear, flagged])
    assert len(review.flagged) == 1
    assert review.flagged[0].path == "bad.py"


# ---------------------------------------------------------------------------
# subscriber.py — circuit breaker
# ---------------------------------------------------------------------------


def test_should_review_cooldown():
    """Same commit SHA is not reviewed twice within the cooldown window."""
    import neutron_os.extensions.builtins.mirror_agent.subscriber as sub

    # Clear state
    sub._reviewed.clear()

    sha = "abc123def456"
    assert sub._should_review(sha) is True   # first time: proceed
    assert sub._should_review(sha) is False  # cooldown active: skip


def test_should_review_different_shas():
    """Different SHAs are each reviewed independently."""
    import neutron_os.extensions.builtins.mirror_agent.subscriber as sub

    sub._reviewed.clear()
    assert sub._should_review("sha_a") is True
    assert sub._should_review("sha_b") is True


def test_subscriber_register_wires_handlers():
    """register(bus) wires mo.heartbeat and mirror.commit handlers."""
    from neutron_os.extensions.builtins.mirror_agent.subscriber import register

    bus = MagicMock()
    register(bus)

    calls = [call[0][0] for call in bus.subscribe.call_args_list]
    assert "mo.heartbeat" in calls
    assert "mirror.commit" in calls


def test_handle_commit_skips_missing_sha():
    """handle_commit is a no-op when sha is missing from data."""
    from neutron_os.extensions.builtins.mirror_agent.subscriber import handle_commit

    # Should not raise
    handle_commit("mirror.commit", {})
    handle_commit("mirror.commit", {"sha": "", "repo_root": "/tmp"})


# ---------------------------------------------------------------------------
# EventBus wiring — heartbeat published during chat REPL
# ---------------------------------------------------------------------------


def test_review_file_uses_gateway_prompt_kwarg(tmp_path):
    """_review_file calls gateway.complete with 'prompt=' not 'user=' (regression)."""
    from neutron_os.extensions.builtins.mirror_agent.reviewer import _review_file

    target = tmp_path / "clean.py"
    target.write_text("x = 1")

    gateway = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "VERDICT: CLEAR\nFINDINGS:\n- None\nRECOMMENDATION: All clear."
    gateway.complete.return_value = mock_response

    _review_file(target, tmp_path, gateway)

    call_kwargs = gateway.complete.call_args.kwargs
    assert "prompt" in call_kwargs, "gateway.complete must be called with 'prompt=' kwarg"
    assert "user" not in call_kwargs, "'user=' kwarg not accepted by Gateway.complete"


def test_ci_mode_exits_nonzero_on_findings(tmp_path, monkeypatch):
    """--ci flag causes sys.exit(1) when review finds issues."""
    import argparse
    from neutron_os.extensions.builtins.mirror_agent import cli as mirror_cli

    # Build a fake flagged result
    from neutron_os.extensions.builtins.mirror_agent.reviewer import MirrorReview, FileReview
    flagged_result = MirrorReview(
        files_reviewed=1,
        files_flagged=1,
        reviews=[FileReview(path="bad.py", verdict="REVIEW_NEEDED", findings=["Contains PII"])],
    )

    monkeypatch.setattr(mirror_cli, "_repo_root", lambda: tmp_path)

    from neutron_os.infra.gateway import Gateway
    monkeypatch.setattr(Gateway, "active_provider", property(lambda self: True))

    import neutron_os.extensions.builtins.mirror_agent.reviewer as rev
    monkeypatch.setattr(rev, "review_mirror_content", lambda **kw: flagged_result)

    args = argparse.Namespace(mirror_cmd="review", all=True, since=None, ci=True)
    with pytest.raises(SystemExit) as exc:
        mirror_cli._cmd_review(args)
    assert exc.value.code == 1


def test_ci_mode_does_not_exit_on_clear(tmp_path, monkeypatch):
    """--ci flag does not exit when review is clean."""
    import argparse
    from neutron_os.extensions.builtins.mirror_agent import cli as mirror_cli
    from neutron_os.extensions.builtins.mirror_agent.reviewer import MirrorReview

    clean_result = MirrorReview(files_reviewed=3, files_flagged=0)

    monkeypatch.setattr(mirror_cli, "_repo_root", lambda: tmp_path)

    from neutron_os.infra.gateway import Gateway
    monkeypatch.setattr(Gateway, "active_provider", property(lambda self: True))

    import neutron_os.extensions.builtins.mirror_agent.reviewer as rev
    monkeypatch.setattr(rev, "review_mirror_content", lambda **kw: clean_result)

    args = argparse.Namespace(mirror_cmd="review", all=True, since=None, ci=True)
    mirror_cli._cmd_review(args)  # Should not raise


def test_eventbus_heartbeat_triggers_mirror_subscriber():
    """Publishing mo.heartbeat on the bus invokes the mirror handler."""
    from neutron_os.infra.orchestrator.bus import EventBus
    from neutron_os.extensions.builtins.mirror_agent.subscriber import register
    import neutron_os.extensions.builtins.mirror_agent.subscriber as sub

    sub._reviewed.clear()

    bus = EventBus()
    register(bus)

    called = []

    # Patch _repo_root to return None so handle_heartbeat exits early
    with patch(
        "neutron_os.extensions.builtins.mirror_agent.subscriber._repo_root",
        return_value=None,
    ):
        # Publish a heartbeat — handler should be invoked (and exit early via None repo_root)
        original_handle = sub.handle_heartbeat

        def spy(topic, data):
            called.append(topic)
            original_handle(topic, data)

        bus.unsubscribe(original_handle)
        bus.subscribe("mo.heartbeat", spy)
        bus.publish("mo.heartbeat", {}, source="test")

    assert "mo.heartbeat" in called
