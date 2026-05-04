# Copyright (c) 2026 The University of Texas at Austin
# SPDX-License-Identifier: Apache-2.0

"""Tests for NeutronOS-side corpus health-check wrapper.

Wraps axiom.rag.health.collect_rag_health with NeutronOS-flavoured
operator output (per-generation chunk counts, audit-trail logging) so
that startup logs make it obvious "the model probably doesn't have this"
domain context loaded.
"""

from __future__ import annotations

import logging


class TestCorpusHealthCheckEmpty:
    def test_no_db_returns_empty_summary_and_logs(self, tmp_path, caplog):
        from neutron_os.extensions.builtins.rag_grounding.health import (
            corpus_health_check,
        )

        with caplog.at_level(logging.INFO, logger="neutron_os.rag_grounding.health"):
            summary = corpus_health_check(rag_root=tmp_path)

        assert summary.healthy is False
        assert summary.total_chunks == 0
        # Operator-visible message names the missing-corpus state.
        msg = " ".join(r.getMessage() for r in caplog.records).lower()
        assert "no corpora" in msg or "0 chunks" in msg or "empty" in msg

    def test_no_path_returns_empty_summary(self):
        from neutron_os.extensions.builtins.rag_grounding.health import (
            corpus_health_check,
        )

        summary = corpus_health_check(rag_root=None)
        assert summary.healthy is False
        assert summary.total_chunks == 0


class TestCorpusHealthCheckPopulated:
    def test_populated_db_logs_per_generation_chunk_counts(self, tmp_path, caplog):
        """Build a minimal SQLite RAG store with two corpora and verify
        the wrapper logs chunk counts per corpus_id."""
        import sqlite3

        from neutron_os.extensions.builtins.rag_grounding.health import (
            corpus_health_check,
        )

        db = tmp_path / "rag.db"
        conn = sqlite3.connect(db)
        # Minimal schema axiom.rag.health expects: column names per
        # axiom/rag/health.py::_read_chunk_summaries (corpus, corpus_generation).
        conn.execute(
            """CREATE TABLE chunks (
                id INTEGER PRIMARY KEY,
                corpus TEXT NOT NULL,
                corpus_generation TEXT
            )"""
        )
        conn.executemany(
            "INSERT INTO chunks (corpus, corpus_generation) VALUES (?,?)",
            [
                ("netl_triga", "gen_2026_04"),
                ("netl_triga", "gen_2026_04"),
                ("ansi_15_1", "gen_2026_04"),
            ],
        )
        conn.commit()
        conn.close()

        with caplog.at_level(logging.INFO, logger="neutron_os.rag_grounding.health"):
            summary = corpus_health_check(rag_root=tmp_path)

        assert summary.healthy is True
        assert summary.total_chunks == 3
        # Both corpora appear in logs.
        msg = " ".join(r.getMessage() for r in caplog.records)
        assert "netl_triga" in msg
        assert "ansi_15_1" in msg
        # Chunk counts surface (2 and 1 are the only multi-row counts).
        assert "2" in msg
