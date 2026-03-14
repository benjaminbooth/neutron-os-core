"""Integration tests for the RAG subsystem.

Require a live PostgreSQL instance with pgvector.
Run with:
    pytest src/neutron_os/extensions/builtins/rag/tests/test_rag_integration.py \
        -m integration -v

DATABASE_URL is read from the `rag.database_url` setting or the DATABASE_URL
environment variable.  The tests create isolated data under the `rag-internal`
corpus and clean up after themselves.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        from neutron_os.extensions.builtins.settings.store import SettingsStore
        return SettingsStore().get("rag.database_url") or None
    except Exception:
        return None


def _requires_db(fn):
    """Decorator: skip if no DATABASE_URL configured."""
    url = _get_db_url()
    return pytest.mark.skipif(
        not url,
        reason="DATABASE_URL / rag.database_url not configured",
    )(pytest.mark.integration(fn))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_CORPUS = "rag-internal"
TEST_PREFIX = "integration-test/"


@pytest.fixture(scope="module")
def store():
    """Connected RAGStore, cleaned of test data before and after the session."""
    url = _get_db_url()
    if not url:
        pytest.skip("No database configured")
    from neutron_os.rag.store import RAGStore
    s = RAGStore(url)
    s.connect()
    # Pre-clean any leftovers from a previous failed run
    with s._cur() as cur:
        cur.execute(
            "DELETE FROM chunks WHERE source_path LIKE %s AND corpus = %s",
            (TEST_PREFIX + "%", TEST_CORPUS),
        )
        cur.execute(
            "DELETE FROM documents WHERE source_path LIKE %s AND corpus = %s",
            (TEST_PREFIX + "%", TEST_CORPUS),
        )
    yield s
    # Teardown
    with s._cur() as cur:
        cur.execute(
            "DELETE FROM chunks WHERE source_path LIKE %s AND corpus = %s",
            (TEST_PREFIX + "%", TEST_CORPUS),
        )
        cur.execute(
            "DELETE FROM documents WHERE source_path LIKE %s AND corpus = %s",
            (TEST_PREFIX + "%", TEST_CORPUS),
        )
    s.close()


@pytest.fixture(scope="module")
def sample_chunks():
    """Two synthetic document chunks for testing."""
    from neutron_os.rag.chunker import Chunk

    return [
        Chunk(
            source_path=TEST_PREFIX + "xenon-guide.md",
            source_title="Xenon Poisoning Guide",
            source_type="markdown",
            text=textwrap.dedent("""\
                ## Xenon Poisoning

                Xenon-135 is a fission product with a very high neutron absorption cross-section.
                During reactor shutdown, Xe-135 builds up as I-135 decays, causing the reactor
                to become harder to restart — a phenomenon called the iodine pit.
            """),
            chunk_index=0,
            start_line=1,
        ),
        Chunk(
            source_path=TEST_PREFIX + "export-control.md",
            source_title="Export Control Overview",
            source_type="markdown",
            text=textwrap.dedent("""\
                ## Export Control (EAR / 10 CFR 810)

                MCNP, SCALE, and ORIGEN are export-controlled nuclear codes.
                Any analysis using these tools must be routed through the VPN-gated model tier.
                Queries containing these code names should never reach cloud providers.
            """),
            chunk_index=0,
            start_line=1,
        ),
    ]


# ---------------------------------------------------------------------------
# Core store tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_upsert_and_retrieve(store, sample_chunks):
    """Chunks can be inserted and retrieved by source_path."""
    store.upsert_chunks(
        [sample_chunks[0]],
        checksum="abc123",
        corpus=TEST_CORPUS,
    )
    doc = store.get_document(TEST_PREFIX + "xenon-guide.md", corpus=TEST_CORPUS)
    assert doc is not None
    assert doc["chunk_count"] == 1
    assert doc["checksum"] == "abc123"


@pytest.mark.integration
def test_full_text_search_returns_relevant_chunk(store, sample_chunks):
    """Full-text search finds the xenon chunk when querying 'iodine pit'."""
    store.upsert_chunks([sample_chunks[0]], checksum="abc123", corpus=TEST_CORPUS)
    results = store.search(query_text="iodine pit xenon", limit=5)
    assert len(results) > 0
    texts = [r.chunk_text for r in results]
    assert any("Xenon" in t or "xenon" in t for t in texts)


@pytest.mark.integration
def test_search_returns_corpus_field(store, sample_chunks):
    """Search results include the corpus field."""
    store.upsert_chunks([sample_chunks[0]], checksum="abc123", corpus=TEST_CORPUS)
    results = store.search(query_text="xenon", limit=5)
    assert all(r.corpus == TEST_CORPUS for r in results)


@pytest.mark.integration
def test_upsert_replaces_existing_chunks(store, sample_chunks):
    """Upserting the same source_path+corpus replaces old chunks."""
    chunk = sample_chunks[0]
    store.upsert_chunks([chunk], checksum="v1", corpus=TEST_CORPUS)
    store.upsert_chunks([chunk], checksum="v2", corpus=TEST_CORPUS)
    doc = store.get_document(chunk.source_path, corpus=TEST_CORPUS)
    assert doc["checksum"] == "v2"
    with store._cur() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM chunks WHERE source_path = %s AND corpus = %s",
            (chunk.source_path, TEST_CORPUS),
        )
        assert cur.fetchone()["n"] == 1


@pytest.mark.integration
def test_per_corpus_stats(store, sample_chunks):
    """stats() returns per-corpus breakdown."""
    store.upsert_chunks([sample_chunks[0]], checksum="s1", corpus=TEST_CORPUS)
    store.upsert_chunks([sample_chunks[1]], checksum="s2", corpus=TEST_CORPUS)
    s = store.stats()
    assert s["total_chunks"] >= 2
    assert "rag-internal" in s["chunks_by_corpus"]
    assert s["chunks_by_corpus"]["rag-internal"] >= 2


@pytest.mark.integration
def test_delete_document(store, sample_chunks):
    """delete_document removes only the targeted doc from the corpus."""
    chunk = sample_chunks[1]
    store.upsert_chunks([chunk], checksum="del1", corpus=TEST_CORPUS)
    store.delete_document(chunk.source_path, corpus=TEST_CORPUS)
    assert store.get_document(chunk.source_path, corpus=TEST_CORPUS) is None


# ---------------------------------------------------------------------------
# Ingest integration tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_ingest_file_roundtrip(store, tmp_path):
    """ingest_file indexes a real markdown file and it becomes searchable."""
    from neutron_os.rag.ingest import ingest_file

    md = tmp_path / "test-doc.md"
    # Ensure no stale cache entry from a previous run (source_path is relative: "test-doc.md")
    store.delete_document("test-doc.md", corpus=TEST_CORPUS)
    md.write_text(
        "# TRIGA Reactor Safety\n\n"
        "The TRIGA reactor has a negative temperature coefficient of reactivity. "
        "This self-limiting safety feature prevents runaway power excursions.\n"
    )
    # Use a unique path prefix to avoid collisions
    stats = ingest_file(md, store, repo_root=tmp_path, corpus=TEST_CORPUS)
    assert stats.files_indexed == 1
    assert stats.chunks_created >= 1

    results = store.search(query_text="negative temperature coefficient TRIGA", limit=5)
    assert any("TRIGA" in r.chunk_text for r in results)


@pytest.mark.integration
def test_ingest_skips_unchanged_checksum(store, tmp_path):
    """ingest_file skips files whose checksum hasn't changed."""
    from neutron_os.rag.ingest import ingest_file

    md = tmp_path / "stable-doc.md"
    store.delete_document("stable-doc.md", corpus=TEST_CORPUS)
    md.write_text("# Stable\n\nNo changes here.\n")

    stats1 = ingest_file(md, store, repo_root=tmp_path, corpus=TEST_CORPUS)
    assert stats1.files_indexed == 1

    stats2 = ingest_file(md, store, repo_root=tmp_path, corpus=TEST_CORPUS)
    assert stats2.files_skipped == 1
    assert stats2.files_indexed == 0


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_cli_status_shows_counts(capsys):
    """neut rag status shows the per-corpus table."""
    from neutron_os.rag.cli import main

    main(["status"])
    out = capsys.readouterr().out
    assert "RAG Index Status" in out
    assert "community" in out
    assert "internal" in out


@pytest.mark.integration
def test_cli_index_with_explicit_path(tmp_path):
    """neut rag index <path> traverses the directory and indexes docs."""
    from neutron_os.rag.cli import main

    doc = tmp_path / "reactor-ops.md"
    doc.write_text(
        "# Reactor Operations\n\nMaintain criticality with control rod withdrawal.\n"
    )
    main(["index", str(tmp_path), "--corpus", "rag-internal"])

    # Verify it's searchable
    url = _get_db_url()
    from neutron_os.rag.store import RAGStore
    s = RAGStore(url)
    s.connect()
    results = s.search(query_text="criticality control rod", limit=5)
    s.close()
    assert any("criticality" in r.chunk_text.lower() for r in results)


# ---------------------------------------------------------------------------
# Vector search (pgvector query_embedding path)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_vector_search_returns_nearest_chunk(store):
    """Chunks with explicit embeddings are returned when queried by embedding vector.

    We inject two chunks with known synthetic embeddings that are orthogonal
    to each other. The query embedding matches the first chunk exactly, so it
    should come back first (highest cosine similarity).
    """
    from neutron_os.rag.chunker import Chunk

    DIMS = 1536

    def _unit(index: int) -> list[float]:
        """1536-dim unit vector with 1.0 at position `index`."""
        v = [0.0] * DIMS
        v[index] = 1.0
        return v

    chunk_a = Chunk(
        source_path=TEST_PREFIX + "vec-alpha.md",
        source_title="Alpha Document",
        source_type="markdown",
        text="Alpha: neutron flux measurement techniques.",
        chunk_index=0,
        start_line=1,
    )
    chunk_b = Chunk(
        source_path=TEST_PREFIX + "vec-beta.md",
        source_title="Beta Document",
        source_type="markdown",
        text="Beta: coolant temperature monitoring.",
        chunk_index=0,
        start_line=1,
    )

    emb_a = _unit(0)   # [1, 0, 0, ...]
    emb_b = _unit(1)   # [0, 1, 0, ...]

    store.upsert_chunks([chunk_a], embeddings=[emb_a], checksum="va1", corpus=TEST_CORPUS)
    store.upsert_chunks([chunk_b], embeddings=[emb_b], checksum="vb1", corpus=TEST_CORPUS)

    # Query with embedding identical to chunk_a — should rank it first
    results = store.search(query_embedding=emb_a, limit=5)

    assert len(results) >= 1
    # The closest result must be alpha (similarity == 1.0)
    assert results[0].source_title == "Alpha Document"
    assert results[0].similarity > 0.99


@pytest.mark.integration
def test_hybrid_search_combines_vector_and_text(store):
    """Hybrid search (embedding + text) returns results ordered by combined_score."""
    from neutron_os.rag.chunker import Chunk

    DIMS = 1536

    chunk = Chunk(
        source_path=TEST_PREFIX + "vec-hybrid.md",
        source_title="Hybrid Test",
        source_type="markdown",
        text="Delayed neutrons play a key role in reactor control and kinetics.",
        chunk_index=0,
        start_line=1,
    )
    emb = [0.0] * DIMS
    emb[5] = 1.0

    store.upsert_chunks([chunk], embeddings=[emb], checksum="vh1", corpus=TEST_CORPUS)

    results = store.search(
        query_embedding=emb,
        query_text="delayed neutrons reactor control",
        limit=5,
    )

    assert len(results) >= 1
    paths = [r.source_path for r in results]
    assert TEST_PREFIX + "vec-hybrid.md" in paths
    # Formula: 0.7 * similarity + 0.3 * text_rank.  When similarity == 1.0 and
    # text_rank > 0, combined_score lands between 0.7 and 1.0 — both paths fired.
    hit = next(r for r in results if r.source_path == TEST_PREFIX + "vec-hybrid.md")
    assert hit.similarity > 0.99, "Expected near-perfect vector match"
    assert hit.combined_score > 0.7, "Text rank component must have contributed (> 0.7 * 1.0)"


# ---------------------------------------------------------------------------
# Multi-corpus search
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_search_across_all_three_corpora(store):
    """corpora=None searches rag-internal, rag-org, and rag-community simultaneously."""
    from neutron_os.rag.chunker import Chunk
    from neutron_os.rag.store import CORPUS_COMMUNITY, CORPUS_INTERNAL, CORPUS_ORG

    def _make_chunk(path: str, title: str, text: str) -> Chunk:
        return Chunk(
            source_path=TEST_PREFIX + path,
            source_title=title,
            source_type="markdown",
            text=text,
            chunk_index=0,
            start_line=1,
        )

    chunks_by_corpus = {
        CORPUS_INTERNAL: _make_chunk(
            "mc-internal.md", "Internal Doc",
            "The TRIGA reactor uses a unique prompt-negative temperature coefficient."
        ),
        CORPUS_ORG: _make_chunk(
            "mc-org.md", "Org Doc",
            "The TRIGA reactor fuel-moderator design enables inherent safety."
        ),
        CORPUS_COMMUNITY: _make_chunk(
            "mc-community.md", "Community Doc",
            "TRIGA reactors are widely used for research and isotope production."
        ),
    }

    for corpus, chunk in chunks_by_corpus.items():
        store.upsert_chunks([chunk], checksum="mc1", corpus=corpus)

    # Search all three corpora (default: corpora=None)
    results = store.search(query_text="TRIGA reactor", limit=10)

    found_corpora = {r.corpus for r in results}
    # All three corpora should have contributed a result
    assert CORPUS_INTERNAL in found_corpora, "rag-internal chunk not found"
    assert CORPUS_ORG in found_corpora, "rag-org chunk not found"
    assert CORPUS_COMMUNITY in found_corpora, "rag-community chunk not found"


@pytest.mark.integration
def test_search_filtered_to_single_corpus(store):
    """Passing corpora=['rag-internal'] restricts results to that corpus only."""
    from neutron_os.rag.chunker import Chunk
    from neutron_os.rag.store import CORPUS_INTERNAL

    results = store.search(
        query_text="TRIGA reactor",
        corpora=[CORPUS_INTERNAL],
        limit=10,
    )
    # All returned results must be from rag-internal
    assert all(r.corpus == CORPUS_INTERNAL for r in results)


# ---------------------------------------------------------------------------
# reindex command
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_cli_reindex_clears_and_rebuilds(tmp_path, capsys):
    """neut rag reindex clears the corpus then re-indexes from REPO_ROOT.

    We stub out the actual ingest_repo call (which would crawl the whole codebase)
    so the test verifies the delete_corpus → ingest_repo orchestration, not
    the speed of a full index.
    """
    from unittest.mock import patch
    from neutron_os.rag import cli as rag_cli
    from neutron_os.rag.ingest import IngestStats
    from neutron_os.rag.store import CORPUS_INTERNAL, RAGStore

    url = _get_db_url()
    s = RAGStore(url)
    s.connect()

    # Insert a sentinel chunk that should disappear after reindex
    from neutron_os.rag.chunker import Chunk
    sentinel = Chunk(
        source_path=TEST_PREFIX + "sentinel-reindex.md",
        source_title="Sentinel",
        source_type="markdown",
        text="This sentinel chunk must be gone after reindex.",
        chunk_index=0,
        start_line=1,
    )
    s.upsert_chunks([sentinel], checksum="s99", corpus=CORPUS_INTERNAL)
    s.close()

    stub_stats = IngestStats()
    stub_stats.files_indexed = 3
    stub_stats.chunks_created = 12
    stub_stats.files_skipped = 0

    with patch("neutron_os.rag.ingest.ingest_repo", return_value=stub_stats):
        rag_cli.main(["reindex", "--corpus", CORPUS_INTERNAL])

    out = capsys.readouterr().out
    assert "Cleared" in out
    assert "Re-indexed" in out
    assert "3 files" in out

    # Sentinel must be gone — delete_corpus was called on the real store
    s = RAGStore(url)
    s.connect()
    doc = s.get_document(TEST_PREFIX + "sentinel-reindex.md", corpus=CORPUS_INTERNAL)
    s.close()
    assert doc is None, "Sentinel chunk survived reindex — delete_corpus not called"


# ---------------------------------------------------------------------------
# load_community_dump (psql restore)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_load_community_dump_restores_data(store, tmp_path):
    """load_community_dump() clears rag-community and restores from a .sql fixture.

    We generate a minimal SQL fixture at test time (plain INSERT statements)
    that avoids pg_dump binary format dependencies.

    Requires ``psql`` on PATH — skipped automatically in environments where only
    the PostgreSQL server is available (e.g. k3d with port-forward only).
    """
    import shutil
    if not shutil.which("psql"):
        pytest.skip("psql client not on PATH — install postgresql-client to run this test")

    from neutron_os.rag.store import CORPUS_COMMUNITY

    # Build a small SQL fixture with one document + one chunk in rag-community
    fixture_sql = tmp_path / "community-v0.1.0-test.sql"
    fixture_sql.write_text(
        "BEGIN;\n"
        "INSERT INTO documents (source_path, corpus, source_type, title, checksum, chunk_count)\n"
        "VALUES ('community/nrc-glossary.md', 'rag-community', 'markdown',\n"
        "        'NRC Glossary', 'dump-test-checksum', 1)\n"
        "ON CONFLICT (source_path, corpus) DO UPDATE\n"
        "    SET checksum = EXCLUDED.checksum;\n"
        "\n"
        "INSERT INTO chunks (source_path, source_title, source_type, chunk_text,\n"
        "                    chunk_index, start_line, corpus, checksum)\n"
        "VALUES ('community/nrc-glossary.md', 'NRC Glossary', 'markdown',\n"
        "        'Reactivity: the relative departure from criticality of a reactor.',\n"
        "        0, 1, 'rag-community', 'dump-test-checksum');\n"
        "COMMIT;\n"
    )

    store.load_community_dump(fixture_sql)

    # Verify the restored chunk is searchable
    results = store.search(
        query_text="reactivity criticality reactor",
        corpora=[CORPUS_COMMUNITY],
        limit=5,
    )
    assert len(results) >= 1
    assert any("criticality" in r.chunk_text.lower() for r in results)

    # Verify the document record was restored
    doc = store.get_document("community/nrc-glossary.md", corpus=CORPUS_COMMUNITY)
    assert doc is not None
    assert doc["checksum"] == "dump-test-checksum"
