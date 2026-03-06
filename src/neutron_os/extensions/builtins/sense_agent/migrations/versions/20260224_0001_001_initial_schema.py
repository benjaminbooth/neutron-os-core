"""Initial schema: signals, media, participants, people with pgvector.

Revision ID: 001
Revises:
Create Date: 2026-02-24

This migration creates the complete initial schema for Neut Sense:
- pgvector extension for vector similarity search
- signals: Signal chunks with embeddings for RAG
- media: Audio/video recordings with transcripts and embeddings
- participants: Links people to media with access control
- people: Person registry with aliases
- HNSW indexes for fast vector search
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Embedding dimension (OpenAI text-embedding-3-small)
EMBEDDING_DIM = 1536


def upgrade() -> None:
    """Create initial schema with pgvector support."""

    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # =========================================================================
    # Signals table - Signal chunks with embeddings for RAG
    # =========================================================================
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}),
            signal_type TEXT,
            initiative TEXT,
            source TEXT,
            timestamp TIMESTAMPTZ,
            metadata JSONB DEFAULT '{{}}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            owner_id TEXT,
            version INTEGER DEFAULT 1
        )
    """)

    # =========================================================================
    # Media table - Recordings with transcripts and embeddings
    # =========================================================================
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS media (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            media_type TEXT,
            title TEXT,
            transcript TEXT,
            transcript_preview TEXT,
            embedding vector({EMBEDDING_DIM}),
            duration_sec REAL,
            recorded_at TIMESTAMPTZ,
            owner_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            version INTEGER DEFAULT 1
        )
    """)

    # =========================================================================
    # Participants table - Links people to media with access control
    # =========================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id TEXT PRIMARY KEY,
            media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
            person_id TEXT NOT NULL,
            name TEXT,
            role TEXT,
            access_level TEXT DEFAULT 'participant',
            mention_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # =========================================================================
    # People table - Person registry with aliases
    # =========================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            aliases TEXT[],
            email TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # =========================================================================
    # HNSW Indexes for fast vector search (cosine similarity)
    # =========================================================================
    op.execute("""
        CREATE INDEX IF NOT EXISTS signals_embedding_idx
        ON signals USING hnsw (embedding vector_cosine_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS media_embedding_idx
        ON media USING hnsw (embedding vector_cosine_ops)
    """)

    # =========================================================================
    # B-tree indexes for filtering
    # =========================================================================
    op.execute("CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_signals_initiative ON signals(initiative)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_media_owner ON media(owner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_media_recorded ON media(recorded_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_participants_media ON participants(media_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_participants_person ON participants(person_id)")

    # =========================================================================
    # Alembic version table (if not exists)
    # =========================================================================
    # Alembic creates this automatically, but we ensure it exists for clarity


def downgrade() -> None:
    """Drop all tables (destructive!)."""

    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS idx_participants_person")
    op.execute("DROP INDEX IF EXISTS idx_participants_media")
    op.execute("DROP INDEX IF EXISTS idx_media_recorded")
    op.execute("DROP INDEX IF EXISTS idx_media_owner")
    op.execute("DROP INDEX IF EXISTS idx_signals_timestamp")
    op.execute("DROP INDEX IF EXISTS idx_signals_initiative")
    op.execute("DROP INDEX IF EXISTS idx_signals_type")
    op.execute("DROP INDEX IF EXISTS media_embedding_idx")
    op.execute("DROP INDEX IF EXISTS signals_embedding_idx")

    # Drop tables in correct order (respecting foreign keys)
    op.execute("DROP TABLE IF EXISTS participants")
    op.execute("DROP TABLE IF EXISTS people")
    op.execute("DROP TABLE IF EXISTS media")
    op.execute("DROP TABLE IF EXISTS signals")

    # Note: We don't drop the vector extension as other databases might use it
