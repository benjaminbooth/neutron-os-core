"""Unit tests for the Signal RAG system."""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.agents.sense.signal_rag import (
    SignalRAG,
    SignalChunk,
    VectorStore,
    RetrievalResult,
    KeywordEmbeddings,
)
from tools.agents.sense.models import Signal


class TestSignalChunk:
    """Test SignalChunk dataclass."""

    def test_construction(self):
        chunk = SignalChunk(
            signal_id="abc123",
            text="Kevin is working on TRIGA thermal hydraulics",
            timestamp="2026-02-15T10:00:00Z",
            signal_type="progress",
            initiative="TRIGA Digital Twin",
            source="voice",
        )
        
        assert chunk.signal_id == "abc123"
        assert "Kevin" in chunk.text
        assert chunk.embedding is None  # Not set yet

    def test_roundtrip(self):
        chunk = SignalChunk(
            signal_id="def456",
            text="Test chunk",
            timestamp="2026-02-15T10:00:00Z",
            signal_type="blocker",
            initiative="MSR",
            source="email",
            metadata={"originator": "ben@example.com"},
        )
        
        d = chunk.to_dict()
        restored = SignalChunk.from_dict(d)
        
        assert restored.signal_id == chunk.signal_id
        assert restored.metadata == chunk.metadata


class TestKeywordEmbeddings:
    """Test the fallback keyword-based embedding provider."""

    @pytest.fixture
    def embedder(self):
        return KeywordEmbeddings()

    def test_is_always_available(self, embedder):
        """Keyword embeddings should always be available (no API needed)."""
        assert embedder.is_available() is True

    def test_produces_embeddings(self, embedder):
        texts = ["TRIGA reactor thermal hydraulics"]
        embeddings = embedder.embed(texts)
        
        assert len(embeddings) == 1
        assert isinstance(embeddings[0], list)
        assert len(embeddings[0]) > 0

    def test_similar_texts_have_similar_embeddings(self, embedder):
        text1 = "TRIGA reactor thermal hydraulics analysis"
        text2 = "TRIGA thermal hydraulics for reactor"
        text3 = "MSR salt chemistry analysis"
        
        emb1 = embedder.embed([text1])[0]
        emb2 = embedder.embed([text2])[0]
        emb3 = embedder.embed([text3])[0]
        
        # Compute simple dot product similarity
        def dot(a, b):
            return sum(x*y for x, y in zip(a, b))
        
        sim_12 = dot(emb1, emb2)
        sim_13 = dot(emb1, emb3)
        
        # text1 and text2 should be more similar than text1 and text3
        assert sim_12 > sim_13

    def test_empty_text(self, embedder):
        embeddings = embedder.embed([""])
        assert len(embeddings) == 1


class TestVectorStore:
    """Test the VectorStore class."""

    @pytest.fixture
    def store(self, tmp_path):
        return VectorStore(
            index_path=tmp_path / "index.json",
            embeddings_path=tmp_path / "embeddings.json",
        )

    @pytest.fixture
    def sample_chunks(self):
        return [
            SignalChunk(
                signal_id="sig1",
                text="Kevin working on TRIGA thermal hydraulics code",
                timestamp="2026-02-15T10:00:00Z",
                signal_type="progress",
                initiative="TRIGA Digital Twin",
                source="voice",
            ),
            SignalChunk(
                signal_id="sig2",
                text="MSR salt chemistry experiments ongoing",
                timestamp="2026-02-15T11:00:00Z",
                signal_type="progress",
                initiative="MSR Project",
                source="voice",
            ),
            SignalChunk(
                signal_id="sig3",
                text="Blocked on NRC approval for license",
                timestamp="2026-02-15T12:00:00Z",
                signal_type="blocker",
                initiative="TRIGA Digital Twin",
                source="email",
            ),
        ]

    def test_add_chunks(self, store, sample_chunks):
        store.add(sample_chunks)
        
        assert store.size() == 3

    def test_search_returns_results(self, store, sample_chunks):
        store.add(sample_chunks)
        
        results = store.search("TRIGA thermal", k=2)
        
        assert len(results) <= 2
        assert isinstance(results[0], RetrievalResult)

    def test_search_relevance_ordering(self, store, sample_chunks):
        store.add(sample_chunks)
        
        results = store.search("TRIGA thermal hydraulics", k=3)
        
        # First result should be most relevant
        assert "TRIGA" in results[0].chunk.text or "thermal" in results[0].chunk.text

    def test_persistence(self, store, sample_chunks, tmp_path):
        store.add(sample_chunks)
        store.save()
        
        # Create new store from same paths
        store2 = VectorStore(
            index_path=tmp_path / "index.json",
            embeddings_path=tmp_path / "embeddings.json",
        )
        store2.load()
        
        assert store2.size() == 3

    def test_clear(self, store, sample_chunks):
        store.add(sample_chunks)
        assert store.size() == 3
        
        store.clear()
        assert store.size() == 0


class TestSignalRAG:
    """Test the SignalRAG class."""

    @pytest.fixture
    def rag(self, tmp_path):
        return SignalRAG(
            index_path=tmp_path / "index.json",
            embeddings_path=tmp_path / "embeddings.json",
            processed_dir=tmp_path / "processed",
        )

    @pytest.fixture
    def rag_with_signals(self, tmp_path):
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()
        
        signals = [
            Signal(
                source="voice",
                timestamp="2026-02-15T10:00:00Z",
                raw_text="Kevin making progress on TRIGA thermal hydraulics",
                detail="TRIGA TH progress",
                people=["Kevin"],
                initiatives=["TRIGA Digital Twin"],
                signal_type="progress",
            ),
            Signal(
                source="voice",
                timestamp="2026-02-15T11:00:00Z",
                raw_text="MSR salt loop experiments complete",
                detail="MSR experiments done",
                initiatives=["MSR Project"],
                signal_type="progress",
            ),
        ]
        
        for i, sig in enumerate(signals):
            (processed_dir / f"signal_{i}.json").write_text(
                json.dumps(sig.to_dict(), indent=2)
            )
        
        rag = SignalRAG(
            index_path=tmp_path / "index.json",
            embeddings_path=tmp_path / "embeddings.json",
            processed_dir=processed_dir,
        )
        return rag

    def test_index_signals(self, rag_with_signals):
        rag_with_signals.index_signals()
        
        assert rag_with_signals.store.size() >= 2

    def test_query_returns_results(self, rag_with_signals):
        rag_with_signals.index_signals()
        
        results = rag_with_signals.query("TRIGA thermal")
        
        assert len(results) >= 1

    def test_query_with_filters(self, rag_with_signals):
        rag_with_signals.index_signals()
        
        results = rag_with_signals.query(
            "progress",
            initiative_filter="TRIGA Digital Twin",
        )
        
        for r in results:
            assert "TRIGA" in r.chunk.initiative

    def test_signal_to_chunk_conversion(self, rag):
        signal = Signal(
            source="voice",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="Raw transcript here",
            detail="Extracted detail",
            people=["Kevin", "Ben"],
            initiatives=["TRIGA"],
            signal_type="progress",
        )
        
        chunk = rag._signal_to_chunk(signal)
        
        assert signal.signal_id == chunk.signal_id
        assert "Kevin" in chunk.text or "detail" in chunk.text.lower()


class TestRetrievalResult:
    """Test RetrievalResult dataclass."""

    def test_construction(self):
        chunk = SignalChunk(
            signal_id="abc",
            text="test",
            timestamp="2026-02-15T10:00:00Z",
            signal_type="progress",
            initiative="TRIGA",
            source="voice",
        )
        
        result = RetrievalResult(
            chunk=chunk,
            relevance=0.85,
            rank=1,
        )
        
        assert result.relevance == 0.85
        assert result.rank == 1
