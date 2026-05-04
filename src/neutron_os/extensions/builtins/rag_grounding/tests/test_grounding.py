# Copyright (c) 2026 The University of Texas at Austin
# SPDX-License-Identifier: Apache-2.0

"""Tests for NeutronOS-side wiring of axiom.rag.grounding.

NeutronOS consumes the GroundingHooks primitive shipped by axiom and
configures it with NETL-style technical-question thresholds.  These tests
pin (a) the threshold defaults, (b) the factory's mode/threshold
overrides, and (c) the integration with axiom's AskHooks contract.

Per project memory feedback_axiom_domain_agnostic: NeutronOS extension
code can name domain-specific things (NETL, TRIGA, regulatory standards),
but the underlying axiom primitive must stay generic. We test against
the published axiom contract, not internal axiom modules.
"""

from __future__ import annotations


def _cite(*, title: str, source_id: str, score: float | None, text: str = "x"):
    from axiom.memory.ask import Citation
    return Citation(title=title, text=text, source_id=source_id, score=score)


def _request(question: str = "what is xenon poisoning?"):
    from axiom.memory.ask import AskRequest
    return AskRequest(question=question, principal_id="netl_op", scope_id="reactor_ops")


# ---------------------------------------------------------------------------
# NETL-tuned threshold defaults
# ---------------------------------------------------------------------------


class TestNETLThresholdDefaults:
    """The factory ships NETL-style thresholds out of the box.

    Starting points (documented as tunable in grounding.py):
        min_citations         = 2
        min_top_score         = 0.55
        min_avg_score         = 0.40
        min_distinct_sources  = 1
    """

    def test_default_threshold_values(self):
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            DEFAULT_NETL_THRESHOLD,
        )

        assert DEFAULT_NETL_THRESHOLD.min_citations == 2
        assert DEFAULT_NETL_THRESHOLD.min_top_score == 0.55
        assert DEFAULT_NETL_THRESHOLD.min_avg_score == 0.40
        assert DEFAULT_NETL_THRESHOLD.min_distinct_sources == 1

    def test_factory_returns_groundinghooks_in_prepend_mode_by_default(self):
        from axiom.rag.grounding import GroundingHooks
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            make_grounding_hooks,
        )

        hooks = make_grounding_hooks()

        assert isinstance(hooks, GroundingHooks)
        assert hooks.mode == "prepend"
        # Threshold round-trips the NETL defaults.
        assert hooks.threshold.min_citations == 2
        assert hooks.threshold.min_top_score == 0.55

    def test_factory_accepts_mode_override(self):
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            make_grounding_hooks,
        )

        hooks = make_grounding_hooks(mode="substitute")
        assert hooks.mode == "substitute"

        audit = make_grounding_hooks(mode="audit_only")
        assert audit.mode == "audit_only"

    def test_factory_accepts_threshold_override(self):
        from axiom.rag.grounding import GroundingThreshold
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            make_grounding_hooks,
        )

        custom = GroundingThreshold(
            min_citations=5, min_top_score=0.8, min_avg_score=0.6,
            min_distinct_sources=3,
        )
        hooks = make_grounding_hooks(threshold=custom)
        assert hooks.threshold is custom


# ---------------------------------------------------------------------------
# Behavioural integration with axiom GroundingHooks
# ---------------------------------------------------------------------------


class TestNETLBehaviourBelowThreshold:
    """When citations don't meet NETL thresholds, the hook prepends a
    notice instead of letting the LLM hallucinate. Pins the wiring."""

    def test_single_citation_top_score_below_threshold_prepends_notice(self):
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            make_grounding_hooks,
        )

        hooks = make_grounding_hooks()
        # min_top_score=0.55 fails; only 1 citation also trips
        # min_citations=2.
        cites = [_cite(title="A", source_id="s1", score=0.30)]

        # post_llm prepends the notice in prepend mode.
        out = hooks.post_llm(_request(), "qwen says use boric acid", cites)

        assert out is not None
        assert "verify" in out.lower()
        assert "qwen says use boric acid" in out

    def test_no_citations_prepends_notice(self):
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            make_grounding_hooks,
        )

        hooks = make_grounding_hooks()
        out = hooks.post_llm(_request(), "qwen response", [])

        assert out is not None
        assert "verify" in out.lower()


class TestNETLBehaviourAboveThreshold:
    """When all NETL thresholds pass, the hook is a no-op."""

    def test_two_solid_citations_pass(self):
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            make_grounding_hooks,
        )

        hooks = make_grounding_hooks()
        cites = [
            _cite(title="NETL TRIGA Tech Manual §3", source_id="netl_tm_3", score=0.82),
            _cite(title="ANSI/ANS-15.1", source_id="ansi_15_1", score=0.71),
        ]
        out = hooks.post_llm(_request(), "qwen response", cites)
        assert out is None  # no transformation needed


# ---------------------------------------------------------------------------
# Low-confidence audit event
# ---------------------------------------------------------------------------


class TestLowConfidenceAuditEvent:
    """Below-threshold retrievals should leave a trail under runtime/logs/
    so operators can see "the model probably doesn't have this".

    Threshold for the audit event is independent of the grounding gate
    threshold (per the prompt: top_score < 0.40 specifically).
    """

    def test_emits_event_when_top_score_below_audit_floor(self, tmp_path):
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            LOW_CONFIDENCE_AUDIT_FLOOR,
            emit_low_confidence_audit,
        )

        assert LOW_CONFIDENCE_AUDIT_FLOOR == 0.40

        cites = [_cite(title="A", source_id="s1", score=0.31)]
        path = tmp_path / "audit.jsonl"
        emit_low_confidence_audit(
            query="what is the regulatory limit?",
            citations=cites,
            audit_path=path,
        )

        assert path.exists()
        lines = path.read_text().splitlines()
        assert len(lines) == 1
        import json

        rec = json.loads(lines[0])
        assert rec["event"] == "rag.low_confidence"
        assert rec["query"] == "what is the regulatory limit?"
        assert rec["top_score"] == 0.31
        assert rec["citation_count"] == 1
        assert "ts" in rec  # ISO timestamp

    def test_does_not_emit_when_top_score_meets_floor(self, tmp_path):
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            emit_low_confidence_audit,
        )

        cites = [_cite(title="A", source_id="s1", score=0.55)]
        path = tmp_path / "audit.jsonl"
        emit_low_confidence_audit(
            query="q", citations=cites, audit_path=path,
        )

        # No event written — confidence was acceptable.
        assert not path.exists() or path.read_text() == ""

    def test_emits_event_when_no_citations(self, tmp_path):
        """Empty retrieval is the worst case — always audited."""
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            emit_low_confidence_audit,
        )

        path = tmp_path / "audit.jsonl"
        emit_low_confidence_audit(query="q", citations=[], audit_path=path)

        assert path.exists()
        import json

        rec = json.loads(path.read_text().splitlines()[0])
        assert rec["event"] == "rag.low_confidence"
        assert rec["citation_count"] == 0
        assert rec["top_score"] is None

    def test_emit_swallows_path_errors(self, tmp_path):
        """Audit must NEVER break a chat turn — bad paths are swallowed."""
        from neutron_os.extensions.builtins.rag_grounding.grounding import (
            emit_low_confidence_audit,
        )

        # Point at a file inside a non-existent, non-creatable parent.
        bad = tmp_path / "does" / "not" / "exist" / "audit.jsonl"
        # No exception escapes.
        emit_low_confidence_audit(query="q", citations=[], audit_path=bad)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


class TestPublicSurface:
    def test_extension_exports_expected_names(self):
        from neutron_os.extensions.builtins import rag_grounding

        for name in (
            "DEFAULT_NETL_THRESHOLD",
            "LOW_CONFIDENCE_AUDIT_FLOOR",
            "make_grounding_hooks",
            "emit_low_confidence_audit",
            "corpus_health_check",
        ):
            assert hasattr(rag_grounding, name), f"missing public export: {name}"
