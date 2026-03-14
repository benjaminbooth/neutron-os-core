"""PostgreSQL / pgvector storage for RAG chunks.

Three-tier corpus model:
  rag-community  — pre-indexed community knowledge (ships with pip package)
  rag-org        — facility/organization corpus (admin-managed)
  rag-internal   — personal workspace index (built during install + post-push)

Uses ``psycopg2`` for database access.  The schema is created automatically
on first ``connect()`` call if it does not exist.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

from .chunker import Chunk

log = logging.getLogger(__name__)

CORPUS_COMMUNITY = "rag-community"
CORPUS_ORG = "rag-org"
CORPUS_INTERNAL = "rag-internal"

ALL_CORPORA = (CORPUS_COMMUNITY, CORPUS_ORG, CORPUS_INTERNAL)

# ---------------------------------------------------------------------------
# Schema DDL — idempotent (IF NOT EXISTS everywhere)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """\
-- Extensions must be created by superuser (done by setup-rascal.sh)
-- CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id              BIGSERIAL PRIMARY KEY,
    source_path     TEXT NOT NULL,
    corpus          TEXT NOT NULL DEFAULT 'rag-internal',
    source_type     TEXT NOT NULL DEFAULT 'markdown',
    title           TEXT NOT NULL DEFAULT '',
    checksum        TEXT NOT NULL DEFAULT '',
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    owner           TEXT,
    first_indexed   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_indexed    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_path, corpus)
);

CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    source_path     TEXT NOT NULL,
    source_title    TEXT NOT NULL DEFAULT '',
    source_type     TEXT NOT NULL DEFAULT 'markdown',
    chunk_text      TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL DEFAULT 0,
    start_line      INTEGER NOT NULL DEFAULT 1,
    embedding       vector(1536),
    corpus          TEXT NOT NULL DEFAULT 'rag-internal',
    owner           TEXT,
    team            TEXT,
    checksum        TEXT NOT NULL DEFAULT '',
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_source_path ON chunks (source_path);
CREATE INDEX IF NOT EXISTS idx_chunks_corpus ON chunks (corpus);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""


@dataclass
class SearchResult:
    """A single search hit from the RAG store."""

    source_path: str
    source_title: str
    chunk_text: str
    chunk_index: int
    similarity: float
    combined_score: float
    corpus: str = CORPUS_INTERNAL


class RAGStore:
    """PostgreSQL/pgvector document store for RAG retrieval — three-tier corpus."""

    def __init__(self, database_url: str) -> None:
        self._dsn = database_url
        self._conn: Optional[psycopg2.extensions.connection] = None

    # -- connection management ------------------------------------------------

    def connect(self) -> None:
        """Establish a database connection and ensure the schema exists."""
        if self._conn and not self._conn.closed:
            return
        self._conn = psycopg2.connect(self._dsn)
        self._conn.autocommit = True
        with self._conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        log.info("RAGStore connected and schema ensured")

    def _cur(self):
        """Return a cursor, reconnecting if needed."""
        if self._conn is None or self._conn.closed:
            self.connect()
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()

    # -- write operations -----------------------------------------------------

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        embeddings: Optional[list[list[float]]] = None,
        checksum: str = "",
        corpus: str = CORPUS_INTERNAL,
        owner: Optional[str] = None,
    ) -> None:
        """Insert or replace all chunks for a document within a corpus.

        All chunks must share the same ``source_path``.  Existing chunks for
        that path+corpus are deleted first (full replace).  Embeddings are
        optional — if None, chunks are stored with NULL embeddings (full-text
        search only).
        """
        if not chunks:
            return

        source_path = chunks[0].source_path
        now = datetime.now(timezone.utc)

        with self._cur() as cur:
            # Delete old chunks for this path+corpus
            cur.execute(
                "DELETE FROM chunks WHERE source_path = %s AND corpus = %s",
                (source_path, corpus),
            )

            for i, chunk in enumerate(chunks):
                emb = embeddings[i] if embeddings and i < len(embeddings) else None
                emb_val = str(emb) if emb else None
                cur.execute(
                    """
                    INSERT INTO chunks
                        (source_path, source_title, source_type, chunk_text,
                         chunk_index, start_line, embedding, corpus, owner,
                         checksum, indexed_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chunk.source_path,
                        chunk.source_title,
                        chunk.source_type,
                        chunk.text,
                        chunk.chunk_index,
                        chunk.start_line,
                        emb_val,
                        corpus,
                        owner,
                        checksum,
                        now,
                        now,
                    ),
                )

            # Upsert documents record
            cur.execute(
                """
                INSERT INTO documents
                    (source_path, corpus, source_type, title, checksum,
                     chunk_count, owner, first_indexed, last_indexed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_path, corpus) DO UPDATE SET
                    title        = EXCLUDED.title,
                    checksum     = EXCLUDED.checksum,
                    chunk_count  = EXCLUDED.chunk_count,
                    owner        = EXCLUDED.owner,
                    last_indexed = EXCLUDED.last_indexed
                """,
                (
                    source_path,
                    corpus,
                    chunks[0].source_type,
                    chunks[0].source_title,
                    checksum,
                    len(chunks),
                    owner,
                    now,
                    now,
                ),
            )

    def delete_document(self, path: str, corpus: str = CORPUS_INTERNAL) -> None:
        """Remove all chunks and the document record for *path* in *corpus*."""
        with self._cur() as cur:
            cur.execute(
                "DELETE FROM chunks WHERE source_path = %s AND corpus = %s",
                (path, corpus),
            )
            cur.execute(
                "DELETE FROM documents WHERE source_path = %s AND corpus = %s",
                (path, corpus),
            )

    def delete_corpus(self, corpus: str) -> int:
        """Remove all chunks and documents for an entire corpus. Returns chunk count."""
        with self._cur() as cur:
            cur.execute(
                "SELECT count(*) AS n FROM chunks WHERE corpus = %s", (corpus,)
            )
            n = cur.fetchone()["n"]
            cur.execute("DELETE FROM chunks WHERE corpus = %s", (corpus,))
            cur.execute("DELETE FROM documents WHERE corpus = %s", (corpus,))
        log.info("Deleted corpus %s (%d chunks)", corpus, n)
        return n

    # -- read operations ------------------------------------------------------

    def get_document(self, path: str, corpus: str = CORPUS_INTERNAL) -> Optional[dict]:
        """Return document metadata or ``None`` if not indexed."""
        with self._cur() as cur:
            cur.execute(
                "SELECT source_path, corpus, checksum, chunk_count, last_indexed "
                "FROM documents WHERE source_path = %s AND corpus = %s",
                (path, corpus),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def search(
        self,
        query_embedding: Optional[list[float]] = None,
        query_text: str = "",
        corpora: Optional[list[str]] = None,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Hybrid vector + full-text search across one or more corpora.

        Priority order: rag-internal > rag-org > rag-community.
        If ``corpora`` is None, searches all three in priority order.
        If no embeddings (query_embedding is None), falls back to pure
        full-text search over tsvector.
        """
        if corpora is None:
            corpora = list(ALL_CORPORA)

        corpus_filter = tuple(corpora)
        params: list = []

        if query_embedding is not None:
            if query_text.strip():
                sql = """
                    WITH vector_search AS (
                        SELECT id, source_path, source_title, chunk_text,
                               chunk_index, corpus,
                               1 - (embedding <=> %s::vector) AS similarity
                        FROM chunks
                        WHERE corpus = ANY(%s) AND embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    ),
                    text_search AS (
                        SELECT id,
                               ts_rank(to_tsvector('english', chunk_text),
                                       plainto_tsquery('english', %s)) AS text_rank
                        FROM chunks
                        WHERE corpus = ANY(%s)
                          AND to_tsvector('english', chunk_text) @@
                              plainto_tsquery('english', %s)
                    )
                    SELECT v.source_path, v.source_title, v.chunk_text,
                           v.chunk_index, v.corpus, v.similarity,
                           (0.7 * v.similarity + 0.3 * COALESCE(t.text_rank, 0))
                               AS combined_score
                    FROM vector_search v
                    LEFT JOIN text_search t ON v.id = t.id
                    ORDER BY combined_score DESC
                    LIMIT %s
                """
                emb_str = str(query_embedding)
                params = [
                    emb_str, list(corpus_filter), emb_str, limit * 2,
                    query_text, list(corpus_filter), query_text, limit,
                ]
            else:
                sql = """
                    SELECT source_path, source_title, chunk_text, chunk_index, corpus,
                           1 - (embedding <=> %s::vector) AS similarity,
                           1 - (embedding <=> %s::vector) AS combined_score
                    FROM chunks
                    WHERE corpus = ANY(%s) AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """
                emb_str = str(query_embedding)
                params = [emb_str, emb_str, list(corpus_filter), emb_str, limit]
        else:
            # Pure full-text search
            sql = """
                SELECT source_path, source_title, chunk_text, chunk_index, corpus,
                       0.0 AS similarity,
                       ts_rank(to_tsvector('english', chunk_text),
                               plainto_tsquery('english', %s)) AS combined_score
                FROM chunks
                WHERE corpus = ANY(%s)
                  AND to_tsvector('english', chunk_text) @@
                      plainto_tsquery('english', %s)
                ORDER BY combined_score DESC
                LIMIT %s
            """
            params = [query_text, list(corpus_filter), query_text, limit]

        with self._cur() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        return [
            SearchResult(
                source_path=r["source_path"],
                source_title=r["source_title"],
                chunk_text=r["chunk_text"],
                chunk_index=r["chunk_index"],
                similarity=float(r["similarity"]),
                combined_score=float(r["combined_score"]),
                corpus=r["corpus"],
            )
            for r in rows
        ]

    def stats(self) -> dict:
        """Return index statistics including per-corpus breakdown."""
        with self._cur() as cur:
            cur.execute("SELECT count(*) AS n FROM documents")
            total_docs = cur.fetchone()["n"]

            cur.execute("SELECT count(*) AS n FROM chunks")
            total_chunks = cur.fetchone()["n"]

            cur.execute(
                "SELECT corpus, count(*) AS n FROM chunks GROUP BY corpus ORDER BY corpus"
            )
            by_corpus = {r["corpus"]: r["n"] for r in cur.fetchall()}

            cur.execute(
                "SELECT corpus, count(*) AS n FROM documents GROUP BY corpus ORDER BY corpus"
            )
            docs_by_corpus = {r["corpus"]: r["n"] for r in cur.fetchall()}

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "chunks_by_corpus": by_corpus,
            "documents_by_corpus": docs_by_corpus,
        }

    # -- community corpus operations ------------------------------------------

    def load_community_dump(self, dump_path: Path) -> None:
        """Load a pre-built community corpus from a pg_dump file.

        Clears the existing rag-community corpus first, then restores.
        The dump must contain only the chunks/documents tables filtered to
        corpus='rag-community'.

        Args:
            dump_path: Path to the .sql or .pgdump file to restore.
        """
        log.info("Loading community corpus from %s", dump_path)

        # Clear existing community data
        deleted = self.delete_corpus(CORPUS_COMMUNITY)
        if deleted > 0:
            log.info("Cleared %d existing community chunks before reload", deleted)

        # Use psql to execute the dump directly
        cmd = ["psql", self._dsn, "-f", str(dump_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            log.info("Community corpus loaded: %s", result.stdout.strip() or "ok")
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to load community corpus from {dump_path}:\n{exc.stderr}"
            ) from exc
        except FileNotFoundError:
            raise RuntimeError(
                "psql not found — ensure PostgreSQL client tools are installed"
            )
