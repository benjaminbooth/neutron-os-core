# Copyright (c) 2026 The University of Texas at Austin
# SPDX-License-Identifier: Apache-2.0

"""Startup-time corpus health check for NeutronOS RAG paths.

Wraps ``axiom.rag.health.collect_rag_health`` with a NeutronOS-flavoured
operator log so when ``neut chat`` (or another RAG-aware surface) starts,
the operator immediately sees how many chunks are loaded per corpus +
generation. If the answer is "zero", that's the loudest possible signal
that the model will fall back to its training prior.

Per project memory feedback_axiom_unstable_pause_neutronos_validation:
this wrapper exists *because* axiom's primitive is mid-flight; the
NeutronOS surface is intentionally thin so when axiom's API stabilises
we can replace this whole file with a one-liner.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from axiom.rag.health import RagHealth, collect_rag_health

log = logging.getLogger("neutron_os.rag_grounding.health")


def corpus_health_check(
    *,
    rag_root: Path | str | None = None,
    known_corpora: Sequence[str] | None = None,
    embedding_model_hint: str | None = None,
) -> RagHealth:
    """Collect + log RAG corpus health at startup.

    Parameters
    ----------
    rag_root
        Path to the SQLite RAG store, or a directory containing one.
        ``None`` yields an empty summary.
    known_corpora
        Optional list of corpus IDs to surface even when empty.
    embedding_model_hint
        Active embedding model name, surfaced in the log.

    Returns
    -------
    RagHealth
        The aggregate health snapshot — caller may render it further
        (e.g. in the ``neut doctor`` UI).

    The function never raises: corpus health is a status signal, not a
    correctness gate. Failures yield an empty snapshot and a debug log.
    """
    health = collect_rag_health(
        rag_root=rag_root,
        known_corpora=known_corpora,
        embedding_model_hint=embedding_model_hint,
    )

    if not health.corpora:
        log.info(
            "RAG corpus health: no corpora detected (rag_root=%s). "
            "RAG-grounded answers unavailable; the model will fall back "
            "to its training prior.",
            rag_root,
        )
        return health

    log.info(
        "RAG corpus health: %d total chunks across %d corpora",
        health.total_chunks,
        len(health.corpora),
    )
    for corpus in health.corpora:
        if corpus.chunk_count == 0:
            log.warning(
                "RAG corpus health: corpus=%s is empty (0 chunks). "
                "Run `neut rag ingest` to populate.",
                corpus.corpus_id,
            )
            continue
        log.info(
            "RAG corpus health: corpus=%s chunks=%d generation=%s last_ingested=%s",
            corpus.corpus_id,
            corpus.chunk_count,
            corpus.active_generation or "n/a",
            corpus.last_ingested_at or "n/a",
        )
    return health


__all__ = ["corpus_health_check"]
