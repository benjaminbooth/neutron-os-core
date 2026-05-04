# Copyright (c) 2026 The University of Texas at Austin
# SPDX-License-Identifier: Apache-2.0

"""NeutronOS-side wiring for axiom.rag.grounding.

Background
----------
The 2026-04-28 head-to-head evaluation of NeutronOS vs vanilla chat
surfaced a consumer-side weakness: when the RAG corpus does not contain
the answer (e.g. a regulatory standard that was never ingested), Qwen
on :8766 invented plausible-sounding facts and the user could not tell
the difference. axiom shipped a domain-agnostic ``GroundingHooks``
primitive in commit 5447583; this module is the NeutronOS-side glue.

Three responsibilities live here:

1. **NETL-tuned threshold defaults.** axiom's defaults are intentionally
   permissive so they don't surprise extensions. NeutronOS questions are
   technical (NETL TRIGA, ANSI/ANS-15.1, regulatory limits, etc.) and
   below-threshold answers are dangerous, so we tighten the floor.

2. **A factory** ``make_grounding_hooks`` so every NeutronOS surface
   that builds an ``AskPipeline`` can drop in the same hardened gate
   in one line. Mode and threshold are overridable per surface (ops
   tooling may want ``substitute``; classroom may want ``audit_only``
   while we tune).

3. **Low-confidence audit events.** Distinct from the grounding gate:
   the gate fires at the gate threshold (e.g. 0.55 top-score); this
   event fires at a *lower* floor (0.40) so operators see "the model
   probably doesn't have this" *before* the gate's user-facing notice
   — useful for corpus-coverage analysis even when the gate is muted.

Per project memory feedback_axiom_domain_agnostic, NeutronOS-side code
may name domain-specific things (NETL, TRIGA, ANSI standards). The
underlying axiom primitive remains generic.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from axiom.rag.grounding import (
    GroundingHooks,
    GroundingMode,
    GroundingThreshold,
)

if TYPE_CHECKING:
    from axiom.memory.ask import Citation

log = logging.getLogger("neutron_os.rag_grounding.grounding")


# ---------------------------------------------------------------------------
# NETL-tuned defaults
# ---------------------------------------------------------------------------
#
# Starting points (tunable per surface via the make_grounding_hooks
# factory). Rationale:
#
#   min_citations=2          — single-citation answers in NETL contexts
#                              are almost always wrong about *which*
#                              regulatory paragraph applies.
#   min_top_score=0.55       — Qwen's tokenizer + our embedding model put
#                              "right answer" hits in the 0.6–0.85 band;
#                              0.55 is a safe floor below which the gate
#                              should fire.
#   min_avg_score=0.40       — guards against one strong hit + several
#                              irrelevant chunks dragging the model into
#                              a wrong synthesis.
#   min_distinct_sources=1   — single-source is allowed (some questions
#                              live in exactly one document); raise to 2
#                              when redundancy is desired (production ops
#                              tooling).
#
# These are starting points. Tune by running
# `npx promptfoo eval -c rag-evals.yaml` and watching the hallucination
# rate before raising.
DEFAULT_NETL_THRESHOLD = GroundingThreshold(
    min_citations=2,
    min_top_score=0.55,
    min_avg_score=0.40,
    min_distinct_sources=1,
)


# Below this top-score we always emit a low-confidence audit event,
# regardless of whether the gate fires. Independent of the gate
# threshold so we capture pre-gate-failure signal.
LOW_CONFIDENCE_AUDIT_FLOOR: float = 0.40


# Default audit log location — under the user state dir per ADR-011
# (concurrent file write safety). Computed lazily so tests can override.
def _default_audit_path() -> Path:
    try:
        from axiom.infra.paths import get_user_state_dir

        return get_user_state_dir() / "logs" / "rag_low_confidence.jsonl"
    except Exception:  # pragma: no cover — defensive fallback
        return Path.home() / ".neut" / "logs" / "rag_low_confidence.jsonl"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_grounding_hooks(
    *,
    threshold: GroundingThreshold | None = None,
    mode: GroundingMode = "prepend",
) -> GroundingHooks:
    """Build a configured ``GroundingHooks`` for a NeutronOS ask path.

    Parameters
    ----------
    threshold
        Override the NETL defaults. Useful for surfaces that want a
        stricter or looser gate (e.g. ops tooling may want
        ``min_distinct_sources=2`` to demand corroboration).
    mode
        ``"prepend"`` (default) — let the LLM run, prepend an
        uncertainty notice when below threshold. Cheapest defense;
        appropriate for chat. ``"substitute"`` — short-circuit the
        LLM call and return the notice. Strongest defense; appropriate
        for ops tooling that must never echo a model-prior answer.
        ``"audit_only"`` — record the decision but don't change the
        user-visible answer. Use while tuning thresholds.

    Returns
    -------
    GroundingHooks
        Plug into an ``AskPipeline(..., hooks=...)``.

    Example
    -------
    >>> from axiom.memory.ask import AskPipeline
    >>> hooks = make_grounding_hooks()
    >>> pipeline = AskPipeline(
    ...     memory_stack=memory_stack,
    ...     retriever=retriever,
    ...     llm=llm,
    ...     hooks=hooks,
    ... )
    """
    return GroundingHooks(
        threshold=threshold if threshold is not None else DEFAULT_NETL_THRESHOLD,
        mode=mode,
    )


# ---------------------------------------------------------------------------
# Low-confidence audit event
# ---------------------------------------------------------------------------


def emit_low_confidence_audit(
    *,
    query: str,
    citations: list[Citation],
    audit_path: Path | None = None,
) -> None:
    """Write a JSONL audit row when retrieval looks low-confidence.

    Fires when the top citation's score is below
    ``LOW_CONFIDENCE_AUDIT_FLOOR`` (0.40) or when retrieval returned
    nothing at all. Operators can grep this file to find domain
    questions the corpus doesn't cover.

    The function is fail-closed by design: I/O errors are swallowed so
    audit logging can never break a chat turn. Per ADR-011, writes go
    through ``locked_append_jsonl`` to survive concurrent writers
    (CLI + daemon + agents may all share this file).

    Parameters
    ----------
    query
        The user's original question text.
    citations
        Whatever the retriever surfaced. Empty list is treated as worst
        case and always audited.
    audit_path
        Override the default path. Tests pass a tmp_path; production
        callers leave this ``None``.
    """
    top_score: float | None = None
    if citations:
        scored = [c.score for c in citations if c.score is not None]
        top_score = max(scored) if scored else 0.0

    # Decide whether to emit.
    if citations and top_score is not None and top_score >= LOW_CONFIDENCE_AUDIT_FLOOR:
        return

    path = audit_path if audit_path is not None else _default_audit_path()

    record = {
        "ts": datetime.now(UTC).isoformat(),
        "event": "rag.low_confidence",
        "query": query,
        "top_score": top_score,
        "citation_count": len(citations),
        "audit_floor": LOW_CONFIDENCE_AUDIT_FLOOR,
        "source_ids": [c.source_id for c in citations],
    }

    try:
        # Try ADR-011's lock-aware append first.
        try:
            from axiom.infra.state import locked_append_jsonl

            path.parent.mkdir(parents=True, exist_ok=True)
            locked_append_jsonl(path, record)
            return
        except ImportError:
            # Fall through to plain append for older axiom installs.
            pass

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        # Audit must never break a chat turn. Log at debug so the
        # primary loop is unaffected.
        log.debug("emit_low_confidence_audit: swallow %s", exc)


__all__ = [
    "DEFAULT_NETL_THRESHOLD",
    "LOW_CONFIDENCE_AUDIT_FLOOR",
    "emit_low_confidence_audit",
    "make_grounding_hooks",
]
