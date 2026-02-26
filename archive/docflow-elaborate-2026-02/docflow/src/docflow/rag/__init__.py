"""
DocFlow RAG Module

Retrieval-Augmented Generation infrastructure for DocFlow.
Uses pgvector for vector storage with hybrid (dense + sparse) search.
"""

from .pgvector import (
    PgVectorStore,
    Collection,
    SearchResult,
    Chunk,
)

from .embedder import (
    Embedder,
    CodeEmbedder,
    EmbeddingConfig,
)

from .retriever import (
    HybridRetriever,
    QueryType,
    RetrievalConfig,
)

__all__ = [
    # pgvector store
    "PgVectorStore",
    "Collection", 
    "SearchResult",
    "Chunk",
    # embedding
    "Embedder",
    "CodeEmbedder",
    "EmbeddingConfig",
    # retrieval
    "HybridRetriever",
    "QueryType",
    "RetrievalConfig",
]
