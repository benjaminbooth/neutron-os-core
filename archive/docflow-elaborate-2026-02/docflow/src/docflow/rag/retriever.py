"""
Hybrid retriever for DocFlow RAG

Combines dense (semantic), sparse (keyword), and graph-based retrieval
with intelligent query routing.
"""
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple

from .pgvector import PgVectorStore, Collection, SearchResult, Chunk
from .embedder import Embedder, EmbeddingConfig


class QueryType(str, Enum):
    """Types of queries that need different retrieval strategies"""
    FACTUAL = "factual"           # "What is X?" - direct lookup
    SYNTHESIS = "synthesis"       # "Summarize all X" - multi-doc
    RELATIONSHIP = "relationship" # "What depends on X?" - graph
    PROCEDURAL = "procedural"     # "How do I X?" - step-by-step
    TEMPORAL = "temporal"         # "What changed in X?" - timeline
    CODE = "code"                 # "How does X work?" - code search
    CREATIVE = "creative"         # "Draft a X" - minimal retrieval
    WORKFLOW = "workflow"         # "Show the chain from requirement to spec"


@dataclass
class RetrievalConfig:
    """Configuration for retrieval"""
    # Hybrid weights
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    
    # Default limits
    default_k: int = 10
    max_k: int = 50
    
    # Reranking
    rerank: bool = True
    rerank_k: int = 20  # Retrieve this many, rerank to k
    
    # Context expansion
    expand_chunks: bool = True
    expansion_window: int = 1  # Include N chunks before/after
    
    # Graph traversal
    max_graph_hops: int = 2


class HybridRetriever:
    """
    Intelligent retriever that routes queries to optimal strategy.
    
    Strategies:
    - Dense: Semantic similarity for conceptual queries
    - Sparse: Keyword matching for specific terms
    - Hybrid: RRF fusion for general queries
    - Graph: Relationship traversal for dependency queries
    - Workflow: Chain traversal for requirement→spec queries
    
    Usage:
        retriever = HybridRetriever(store, embedder)
        
        # Auto-routed retrieval
        results = await retriever.retrieve("What documents mention thermal hydraulics?")
        
        # Explicit strategy
        results = await retriever.retrieve_hybrid("thermal hydraulics", k=5)
    """
    
    def __init__(
        self,
        store: PgVectorStore,
        embedder: Embedder,
        config: Optional[RetrievalConfig] = None
    ):
        self.store = store
        self.embedder = embedder
        self.config = config or RetrievalConfig()
    
    async def retrieve(
        self,
        query: str,
        k: int = None,
        collection: Optional[Collection] = None,
        filters: Optional[Dict[str, Any]] = None,
        query_type: Optional[QueryType] = None
    ) -> List[SearchResult]:
        """
        Retrieve documents using auto-detected or specified strategy.
        
        Args:
            query: Natural language query
            k: Number of results
            collection: Limit to specific collection
            filters: Metadata filters
            query_type: Override auto-detection
            
        Returns:
            List of search results
        """
        k = k or self.config.default_k
        
        # Auto-detect query type if not specified
        if query_type is None:
            query_type = self._classify_query(query)
        
        # Route to appropriate strategy
        if query_type == QueryType.RELATIONSHIP:
            return await self._retrieve_with_graph(query, k, collection, filters)
        elif query_type == QueryType.WORKFLOW:
            return await self._retrieve_workflow_chain(query, k, collection, filters)
        elif query_type == QueryType.CREATIVE:
            # Minimal retrieval for creative tasks
            return await self.retrieve_hybrid(query, k=3, collection=collection, filters=filters)
        elif query_type == QueryType.CODE:
            # Use code collection
            return await self.retrieve_hybrid(
                query, k=k, 
                collection=Collection.CODE, 
                filters=filters
            )
        else:
            # Default to hybrid for most queries
            return await self.retrieve_hybrid(query, k, collection, filters)
    
    def _classify_query(self, query: str) -> QueryType:
        """
        Simple rule-based query classification.
        TODO: Replace with LLM classifier for better accuracy.
        """
        query_lower = query.lower()
        
        # Relationship queries
        relationship_keywords = [
            "depend", "related", "reference", "link", "connect",
            "what documents", "which docs", "who wrote"
        ]
        if any(kw in query_lower for kw in relationship_keywords):
            return QueryType.RELATIONSHIP
        
        # Workflow queries
        workflow_keywords = [
            "requirement", "prd", "spec", "chain", "trace",
            "derived from", "implements", "flow from"
        ]
        if any(kw in query_lower for kw in workflow_keywords):
            return QueryType.WORKFLOW
        
        # Procedural queries
        procedural_keywords = [
            "how do i", "how to", "steps to", "guide", "tutorial",
            "set up", "configure"
        ]
        if any(kw in query_lower for kw in procedural_keywords):
            return QueryType.PROCEDURAL
        
        # Code queries
        code_keywords = [
            "code", "function", "class", "method", "api",
            "implementation", "module", "script"
        ]
        if any(kw in query_lower for kw in code_keywords):
            return QueryType.CODE
        
        # Creative queries
        creative_keywords = [
            "draft", "write", "create", "generate", "compose"
        ]
        if any(kw in query_lower for kw in creative_keywords):
            return QueryType.CREATIVE
        
        # Synthesis queries
        synthesis_keywords = [
            "summarize", "overview", "all", "compare", "contrast"
        ]
        if any(kw in query_lower for kw in synthesis_keywords):
            return QueryType.SYNTHESIS
        
        # Default to factual
        return QueryType.FACTUAL
    
    async def retrieve_dense(
        self,
        query: str,
        k: int = None,
        collection: Optional[Collection] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Pure semantic retrieval"""
        k = k or self.config.default_k
        
        # Embed query
        query_embedding = await self.embedder.embed(query)
        
        # Search
        results = await self.store.search_dense(
            query_embedding=query_embedding,
            k=k if not self.config.rerank else self.config.rerank_k,
            collection=collection,
            filters=filters
        )
        
        # Optionally rerank
        if self.config.rerank:
            results = await self._rerank(query, results, k)
        
        # Expand chunks if configured
        if self.config.expand_chunks:
            results = await self._expand_chunks(results)
        
        return results[:k]
    
    async def retrieve_sparse(
        self,
        query: str,
        k: int = None,
        collection: Optional[Collection] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Pure keyword retrieval"""
        k = k or self.config.default_k
        
        results = await self.store.search_sparse(
            query_text=query,
            k=k,
            collection=collection,
            filters=filters
        )
        
        return results
    
    async def retrieve_hybrid(
        self,
        query: str,
        k: int = None,
        collection: Optional[Collection] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Hybrid retrieval combining dense and sparse with RRF fusion.
        """
        k = k or self.config.default_k
        
        # Embed query
        query_embedding = await self.embedder.embed(query)
        
        # Hybrid search
        results = await self.store.search_hybrid(
            query_text=query,
            query_embedding=query_embedding,
            k=k if not self.config.rerank else self.config.rerank_k,
            dense_weight=self.config.dense_weight,
            sparse_weight=self.config.sparse_weight,
            collection=collection,
            filters=filters
        )
        
        # Optionally rerank
        if self.config.rerank:
            results = await self._rerank(query, results, k)
        
        # Expand chunks if configured
        if self.config.expand_chunks:
            results = await self._expand_chunks(results)
        
        return results[:k]
    
    async def _retrieve_with_graph(
        self,
        query: str,
        k: int,
        collection: Optional[Collection],
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Graph-enhanced retrieval.
        1. Find seed documents via hybrid search
        2. Expand via graph relationships
        3. Re-score and return
        """
        # Get seed documents
        seeds = await self.retrieve_hybrid(query, k=5, collection=collection, filters=filters)
        
        if not seeds:
            return []
        
        # Expand via graph
        expanded_doc_ids = set()
        for seed in seeds:
            expanded_doc_ids.add(seed.chunk.doc_id)
            
            # Get related documents
            related = await self.store.get_related_documents(
                seed.chunk.doc_id,
                direction="both"
            )
            for rel in related:
                if rel['source_doc_id'] != seed.chunk.doc_id:
                    expanded_doc_ids.add(rel['source_doc_id'])
                if rel['target_doc_id'] != seed.chunk.doc_id:
                    expanded_doc_ids.add(rel['target_doc_id'])
        
        # Re-search with expanded doc filter
        query_embedding = await self.embedder.embed(query)
        
        all_results = []
        for doc_id in expanded_doc_ids:
            results = await self.store.search_dense(
                query_embedding=query_embedding,
                k=2,
                filters={'doc_id': doc_id}
            )
            all_results.extend(results)
        
        # Sort by score and deduplicate
        seen = set()
        unique_results = []
        for r in sorted(all_results, key=lambda x: -x.combined_score):
            if r.chunk.id not in seen:
                seen.add(r.chunk.id)
                unique_results.append(r)
        
        return unique_results[:k]
    
    async def _retrieve_workflow_chain(
        self,
        query: str,
        k: int,
        collection: Optional[Collection],
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Retrieve documents along the workflow chain.
        Requirement → PRD → Design → Spec
        """
        # First find the document being asked about
        seeds = await self.retrieve_hybrid(query, k=3, collection=collection, filters=filters)
        
        if not seeds:
            return []
        
        # Get the workflow chain for the top seed
        chain = await self.store.get_workflow_chain(seeds[0].chunk.doc_id)
        
        # Get content for each document in chain
        results = []
        query_embedding = await self.embedder.embed(query)
        
        for doc in chain:
            doc_results = await self.store.search_dense(
                query_embedding=query_embedding,
                k=1,
                filters={'doc_id': doc['doc_id']}
            )
            if doc_results:
                # Add chain metadata
                doc_results[0].chunk.metadata['workflow_depth'] = doc['depth']
                doc_results[0].chunk.metadata['workflow_direction'] = doc['direction']
                results.append(doc_results[0])
        
        return results[:k]
    
    async def _rerank(
        self,
        query: str,
        results: List[SearchResult],
        k: int
    ) -> List[SearchResult]:
        """
        Rerank results using cross-encoder or LLM.
        TODO: Implement actual reranking with bge-reranker
        
        For now, just return sorted by combined score.
        """
        return sorted(results, key=lambda x: -x.combined_score)[:k]
    
    async def _expand_chunks(
        self,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Expand chunks to include surrounding context.
        
        If a chunk is chunk 3 of 5, also fetch chunks 2 and 4.
        """
        # TODO: Implement chunk expansion
        # This would fetch adjacent chunks from the same document
        return results
    
    # === Convenience Methods ===
    
    async def search_by_author(
        self,
        author: str,
        query: Optional[str] = None,
        k: int = 10
    ) -> List[SearchResult]:
        """Search documents by author, optionally filtered by query"""
        if query:
            return await self.retrieve_hybrid(query, k=k, filters={'author': author})
        else:
            # Just list recent from author
            return await self.store.search_sparse(
                query_text="*",  # Match all
                k=k,
                filters={'author': author}
            )
    
    async def search_by_project(
        self,
        project: str,
        query: Optional[str] = None,
        k: int = 10
    ) -> List[SearchResult]:
        """Search documents by project"""
        if query:
            return await self.retrieve_hybrid(query, k=k, filters={'project': project})
        else:
            return await self.store.search_sparse(
                query_text="*",
                k=k,
                filters={'project': project}
            )
    
    async def search_workflow_stage(
        self,
        stage: str,
        query: Optional[str] = None,
        k: int = 10
    ) -> List[SearchResult]:
        """Search documents at a specific workflow stage"""
        return await self.retrieve_hybrid(
            query or "*",
            k=k,
            filters={'workflow_stage': stage}
        )
    
    async def find_requirements_for_spec(
        self,
        spec_doc_id: str
    ) -> List[Dict]:
        """
        Trace back from a spec to find original requirements.
        """
        chain = await self.store.get_workflow_chain(spec_doc_id, direction="upstream")
        return [doc for doc in chain if doc['workflow_stage'] == 'requirement']
    
    async def find_specs_for_requirement(
        self,
        requirement_doc_id: str
    ) -> List[Dict]:
        """
        Trace forward from a requirement to find all specs.
        """
        chain = await self.store.get_workflow_chain(requirement_doc_id, direction="downstream")
        return [doc for doc in chain if doc['workflow_stage'] == 'spec']
