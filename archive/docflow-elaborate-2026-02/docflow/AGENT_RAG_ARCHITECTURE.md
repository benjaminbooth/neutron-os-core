# DocFlow Agent + RAG System Architecture

## Executive Summary

This document describes a sophisticated **Agentic RAG** system for DocFlow, designed for:
- **Local LLM hosting** (Kimi K2.5, Llama, Mistral, etc.)
- **Multi-source knowledge** (personal docs, team publications, code repos)
- **Adaptive retrieval routing** based on query type
- **Graph-enhanced understanding** of document relationships

**Key Design Principles:**
1. Privacy-first: All processing on local infrastructure
2. Context-aware: Different retrieval for different query types
3. Relationship-aware: Understand document connections, not just content
4. Evolutive: Learn from usage patterns over time

---

## Part 1: Context Analysis

### 1.1 DocFlow Operating Contexts

DocFlow operates across multiple knowledge domains with different characteristics:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DocFlow Knowledge Ecosystem                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Personal Docs   │  │  Team Published  │  │  Code Repos      │          │
│  │  ───────────────│  │  ───────────────│  │  ───────────────│          │
│  │  • Drafts       │  │  • Final docs    │  │  • README.md     │          │
│  │  • Notes        │  │  • Reports       │  │  • Docstrings    │          │
│  │  • Reviews      │  │  • Specs         │  │  • Comments      │          │
│  │  • Archives     │  │  • Guides        │  │  • API docs      │          │
│  │                  │  │                  │  │                  │          │
│  │  Access: Private │  │  Access: Team    │  │  Access: Repo    │          │
│  │  Update: Real-time│ │  Update: On publish│ │  Update: On push│          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Meeting Context │  │  External Refs   │  │  Project Graph   │          │
│  │  ───────────────│  │  ───────────────│  │  ───────────────│          │
│  │  • Transcripts  │  │  • NRC regs      │  │  • Dependencies  │          │
│  │  • Decisions    │  │  • Standards     │  │  • Relationships │          │
│  │  • Action items │  │  • Papers        │  │  • History       │          │
│  │  • Participants │  │  • Manuals       │  │  • Versions      │          │
│  │                  │  │                  │  │                  │          │
│  │  Access: Team    │  │  Access: Varies  │  │  Access: Derived │          │
│  │  Update: Post-mtg│  │  Update: Manual  │  │  Update: Auto    │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Query Type Taxonomy

Different queries require different retrieval strategies:

| Query Type | Example | Optimal RAG Approach |
|------------|---------|---------------------|
| **Factual Lookup** | "What's the thermal conductivity in SAM config?" | Dense retrieval → Direct answer |
| **Synthesis** | "Summarize all feedback on the MSR proposal" | Multi-doc retrieval → Aggregation |
| **Relationship** | "What docs depend on the boundary conditions spec?" | GraphRAG → Traversal |
| **Procedural** | "How do I set up a TRIGA simulation?" | Agentic RAG → Step retrieval |
| **Temporal** | "What changed in N-3 since last review?" | Timeline retrieval → Diff |
| **Code Context** | "How does the bubble flow model work?" | Code-aware retrieval → Explain |
| **Creative** | "Draft an abstract for the ANS presentation" | Light retrieval → Generation |

---

## Part 2: System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DocFlow Agentic RAG System                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Query Interface Layer                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │   │
│  │  │ CLI Commands│  │ IDE Plugin  │  │ Web UI      │  │ API        │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Query Understanding Agent                       │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │   │
│  │  │ Intent Classify │  │ Entity Extract  │  │ Context Enrich      │ │   │
│  │  │ (7 query types) │  │ (docs, people)  │  │ (user, project)     │ │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       Retrieval Router Agent                         │   │
│  │                                                                       │   │
│  │   Query Type ──► Strategy Selection ──► Retriever Orchestration     │   │
│  │                                                                       │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │   │
│  │  │ Dense   │  │ Sparse  │  │ Graph   │  │ Code    │  │ Timeline│  │   │
│  │  │Retriever│  │Retriever│  │Retriever│  │Retriever│  │Retriever│  │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       Context Assembly Agent                         │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │   │
│  │  │ Rerank & Filter │  │ Chunk Expansion │  │ Context Compression │ │   │
│  │  │ (cross-encoder) │  │ (parent docs)   │  │ (fit LLM window)    │ │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       Generation Agent (Local LLM)                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐│   │
│  │  │                    Kimi K2.5 / Llama 3.x / Mistral              ││   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ ││   │
│  │  │  │ Answer Gen  │  │ Reflection  │  │ Tool Use (if needed)    │ ││   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘ ││   │
│  │  └─────────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       Response & Feedback                            │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │   │
│  │  │ Citation Links  │  │ Confidence Score│  │ Feedback Collection │ │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Knowledge Store Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Multi-Index Knowledge Store                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          Vector Store (Dense)                         │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ Embedding Model: nomic-embed-text-v1.5 (local) or BGE-M3       │  │  │
│  │  │ Dimensions: 768 or 1024                                         │  │  │
│  │  │ Distance: Cosine similarity                                     │  │  │
│  │  │ Backend: ChromaDB (local) or Qdrant (distributed)              │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  Collections:                                                          │  │
│  │  ├── personal_docs      (user's drafts, notes, reviews)               │  │
│  │  ├── team_published     (colleagues' published documents)             │  │
│  │  ├── code_docs          (README.md, docstrings, API docs)             │  │
│  │  ├── meeting_context    (transcripts, decisions, actions)             │  │
│  │  └── external_refs      (standards, regulations, papers)              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          Sparse Index (BM25)                          │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ Backend: SQLite FTS5 or Tantivy                                 │  │  │
│  │  │ Tokenizer: Whitespace + domain-specific (NE terminology)       │  │  │
│  │  │ Boost: Title (2x), Headers (1.5x), Body (1x)                   │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  Use cases: Exact term matching, acronyms, model names, config keys  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          Knowledge Graph                              │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ Backend: NetworkX (in-memory) or Neo4j (persistent)            │  │  │
│  │  │ Schema: Documents, People, Projects, Concepts, Code            │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  Node Types:                                                           │  │
│  │  ├── Document    {id, title, state, author, created, updated}        │  │
│  │  ├── Person      {id, name, email, role, team}                       │  │
│  │  ├── Project     {id, name, status, repo}                            │  │
│  │  ├── Concept     {id, name, definition, domain}                      │  │
│  │  └── CodeModule  {id, path, language, purpose}                       │  │
│  │                                                                        │  │
│  │  Edge Types:                                                           │  │
│  │  ├── AUTHORED_BY       (Document → Person)                            │  │
│  │  ├── REVIEWED_BY       (Document → Person)                            │  │
│  │  ├── REFERENCES        (Document → Document)                          │  │
│  │  ├── SUPERSEDES        (Document → Document)                          │  │
│  │  ├── BELONGS_TO        (Document → Project)                           │  │
│  │  ├── MENTIONS          (Document → Concept)                           │  │
│  │  ├── IMPLEMENTS        (CodeModule → Concept)                         │  │
│  │  ├── DEPENDS_ON        (CodeModule → CodeModule)                      │  │
│  │  └── DOCUMENTED_BY     (CodeModule → Document)                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          Timeline Index                               │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ Backend: SQLite with temporal queries                          │  │  │
│  │  │ Granularity: Version-level tracking                            │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  Events:                                                               │  │
│  │  ├── created, modified, reviewed, published, archived                 │  │
│  │  ├── comment_added, comment_resolved                                  │  │
│  │  └── version_created, version_diff                                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Retrieval Strategies

### 3.1 Hybrid Retrieval Pipeline

The default retrieval combines dense and sparse methods with learned fusion:

```python
class HybridRetriever:
    """
    Combines dense (semantic) and sparse (keyword) retrieval
    with Reciprocal Rank Fusion (RRF)
    """
    
    def retrieve(self, query: str, k: int = 10) -> List[Document]:
        # 1. Dense retrieval (semantic similarity)
        dense_results = self.dense_retriever.search(
            query_embedding=self.embed(query),
            k=k * 2  # Over-retrieve for fusion
        )
        
        # 2. Sparse retrieval (BM25 keyword matching)
        sparse_results = self.sparse_retriever.search(
            query=query,
            k=k * 2
        )
        
        # 3. Reciprocal Rank Fusion
        fused = self.rrf_fusion(
            dense_results, 
            sparse_results,
            k=60  # RRF constant
        )
        
        # 4. Return top-k after fusion
        return fused[:k]
    
    def rrf_fusion(self, *result_lists, k=60) -> List[Document]:
        """
        RRF score = Σ 1/(k + rank_i) for each result list
        """
        scores = defaultdict(float)
        
        for results in result_lists:
            for rank, doc in enumerate(results):
                scores[doc.id] += 1 / (k + rank + 1)
        
        # Sort by fused score
        return sorted(scores.items(), key=lambda x: -x[1])
```

### 3.2 Query-Adaptive Router

```python
class RetrievalRouter:
    """
    Routes queries to optimal retrieval strategy based on intent
    """
    
    STRATEGIES = {
        'factual': HybridRetriever,           # Dense + Sparse
        'synthesis': MultiDocRetriever,        # Iterative retrieval
        'relationship': GraphRetriever,        # Graph traversal
        'procedural': AgenticRetriever,        # Multi-step with tools
        'temporal': TimelineRetriever,         # Version-aware
        'code': CodeRetriever,                 # Code-specific embeddings
        'creative': LightRetriever,            # Minimal context
    }
    
    def route(self, query: str, context: QueryContext) -> RetrievalStrategy:
        # Classify query intent (using local LLM or classifier)
        intent = self.classify_intent(query)
        
        # Get base strategy
        strategy_class = self.STRATEGIES[intent]
        
        # Enhance with context
        strategy = strategy_class(
            collections=self.select_collections(query, context),
            filters=self.build_filters(context),
            boost=self.calculate_boost(context)
        )
        
        return strategy
    
    def classify_intent(self, query: str) -> str:
        """
        Fast intent classification using small classifier or LLM
        """
        # Option 1: Fine-tuned classifier (faster)
        # Option 2: LLM with few-shot examples (more flexible)
        
        prompt = """Classify this query into one category:
        - factual: Looking up specific information
        - synthesis: Combining information from multiple sources
        - relationship: Understanding connections between documents/concepts
        - procedural: How to do something step-by-step
        - temporal: What changed over time
        - code: Understanding code or implementation
        - creative: Generate new content
        
        Query: {query}
        Category:"""
        
        return self.llm.generate(prompt.format(query=query)).strip()
```

### 3.3 GraphRAG for Relationships

```python
class GraphRetriever:
    """
    Uses knowledge graph for relationship-aware retrieval
    """
    
    def retrieve(self, query: str, k: int = 10) -> List[Document]:
        # 1. Extract entities from query
        entities = self.extract_entities(query)
        
        # 2. Find seed nodes in graph
        seed_nodes = self.find_nodes(entities)
        
        # 3. Expand via graph traversal
        expanded_nodes = self.expand_subgraph(
            seeds=seed_nodes,
            hops=2,  # 2-hop neighborhood
            edge_types=['REFERENCES', 'SUPERSEDES', 'MENTIONS']
        )
        
        # 4. Retrieve documents for expanded nodes
        doc_ids = [n.doc_id for n in expanded_nodes if n.type == 'Document']
        
        # 5. Combine with dense retrieval for ranking
        graph_docs = self.fetch_documents(doc_ids)
        dense_docs = self.dense_retriever.search(query, k=k)
        
        # 6. Score combines graph centrality + semantic relevance
        return self.score_and_rank(graph_docs, dense_docs, seed_nodes)
    
    def expand_subgraph(self, seeds, hops, edge_types):
        """
        BFS expansion with edge type filtering
        """
        visited = set()
        frontier = seeds
        
        for _ in range(hops):
            next_frontier = []
            for node in frontier:
                if node.id in visited:
                    continue
                visited.add(node.id)
                
                # Get neighbors via specified edge types
                neighbors = self.graph.get_neighbors(
                    node.id, 
                    edge_types=edge_types
                )
                next_frontier.extend(neighbors)
            
            frontier = next_frontier
        
        return list(visited)
```

### 3.4 Agentic RAG for Complex Queries

```python
class AgenticRetriever:
    """
    Multi-step retrieval with planning and reflection
    """
    
    def retrieve(self, query: str, k: int = 10) -> List[Document]:
        # 1. Create retrieval plan
        plan = self.create_plan(query)
        
        # 2. Execute plan steps
        all_results = []
        context_so_far = ""
        
        for step in plan.steps:
            # Execute retrieval step
            step_results = self.execute_step(step, context_so_far)
            all_results.extend(step_results)
            
            # Update context for next step
            context_so_far = self.summarize(all_results)
            
            # Reflect: Do we have enough?
            if self.is_sufficient(query, context_so_far):
                break
        
        # 3. Deduplicate and rank
        return self.dedupe_and_rank(all_results, query)[:k]
    
    def create_plan(self, query: str) -> RetrievalPlan:
        """
        LLM generates a retrieval plan
        """
        prompt = """Given this query, create a retrieval plan.
        
        Query: {query}
        
        Available tools:
        - search_docs(query): Search document content
        - search_code(query): Search code and README files
        - get_related(doc_id): Get related documents
        - get_history(doc_id): Get version history
        - search_by_author(name): Find docs by author
        - search_by_project(name): Find docs in project
        
        Plan (list of steps):"""
        
        return self.llm.generate(prompt.format(query=query))
```

---

## Part 4: Local LLM Infrastructure

### 4.1 Model Selection & Configuration

```yaml
# config/models.yaml

generation:
  primary:
    model: "kimi-k2.5"  # MoE model, excellent for technical content
    context_window: 128000
    parameters:
      temperature: 0.7
      top_p: 0.9
      max_tokens: 4096
    
  fallback:
    model: "llama-3.1-70b-instruct"
    context_window: 128000
    
  fast:  # For classification, quick responses
    model: "llama-3.2-3b-instruct"
    context_window: 8192

embedding:
  primary:
    model: "nomic-embed-text-v1.5"
    dimensions: 768
    max_tokens: 8192
    # Good for: general text, supports long context
    
  code:
    model: "jina-embeddings-v3"  # or CodeBERT
    dimensions: 1024
    max_tokens: 8192
    # Good for: code, technical documentation
    
  reranker:
    model: "bge-reranker-v2-m3"
    # Cross-encoder for reranking retrieved results

infrastructure:
  backend: "vllm"  # or "ollama", "text-generation-inference"
  gpu: "A100-80GB"  # or RTX 4090, etc.
  quantization: "AWQ"  # or "GPTQ", "none"
  batch_size: 8
  tensor_parallel: 1
```

### 4.2 Local Deployment Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Local LLM Deployment                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         API Gateway (FastAPI)                         │  │
│  │  • Rate limiting                                                       │  │
│  │  • Request routing (generation vs embedding)                          │  │
│  │  • Caching (Redis)                                                     │  │
│  │  • Metrics (Prometheus)                                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│              ┌───────────────────────┼───────────────────────┐              │
│              ▼                       ▼                       ▼              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │  vLLM Server     │  │  Embedding Server│  │  Reranker Server │         │
│  │  ─────────────── │  │  ─────────────── │  │  ─────────────── │         │
│  │  Kimi K2.5       │  │  nomic-embed     │  │  bge-reranker    │         │
│  │  (or Llama)      │  │  jina-embed      │  │                  │         │
│  │                  │  │                  │  │                  │         │
│  │  GPU: Primary    │  │  GPU: Secondary  │  │  CPU: Sufficient │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         Storage Layer                                 │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │  │
│  │  │ ChromaDB    │  │ SQLite FTS5 │  │ NetworkX    │  │ Redis      │  │  │
│  │  │ (vectors)   │  │ (sparse)    │  │ (graph)     │  │ (cache)    │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Embedding Pipeline for Team Content

```python
class TeamEmbeddingPipeline:
    """
    Processes and embeds documents from team members
    """
    
    def __init__(self, config: EmbeddingConfig):
        self.text_embedder = NomicEmbedder(config.text_model)
        self.code_embedder = JinaCodeEmbedder(config.code_model)
        self.chunker = AdaptiveChunker(config.chunk_config)
        self.vector_store = ChromaDB(config.vector_store)
        
    async def index_team_documents(self, team_id: str):
        """
        Index all published documents from team members
        """
        # 1. Discover published documents
        team_docs = await self.discover_team_docs(team_id)
        
        for doc in team_docs:
            await self.index_document(doc)
    
    async def index_document(self, doc: Document):
        """
        Process and index a single document
        """
        # 1. Determine document type
        doc_type = self.classify_document(doc)
        
        # 2. Select appropriate chunking strategy
        if doc_type == 'code':
            chunks = self.chunker.chunk_code(doc.content)
            embedder = self.code_embedder
            collection = 'code_docs'
        elif doc_type == 'technical':
            chunks = self.chunker.chunk_technical(doc.content)
            embedder = self.text_embedder
            collection = 'team_published'
        else:
            chunks = self.chunker.chunk_general(doc.content)
            embedder = self.text_embedder
            collection = 'team_published'
        
        # 3. Generate embeddings
        embeddings = await embedder.embed_batch([c.text for c in chunks])
        
        # 4. Store with metadata
        await self.vector_store.upsert(
            collection=collection,
            ids=[f"{doc.id}_{i}" for i in range(len(chunks))],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[{
                'doc_id': doc.id,
                'doc_title': doc.title,
                'author': doc.author,
                'team': doc.team,
                'project': doc.project,
                'chunk_index': i,
                'total_chunks': len(chunks),
                'created': doc.created.isoformat(),
                'doc_type': doc_type
            } for i, c in enumerate(chunks)]
        )
        
        # 5. Update knowledge graph
        await self.update_graph(doc, chunks)
    
    async def index_code_repository(self, repo_path: Path):
        """
        Index README.md and documentation from code repos
        """
        # Find all markdown files
        md_files = list(repo_path.rglob('*.md'))
        
        # Find Python docstrings
        py_files = list(repo_path.rglob('*.py'))
        
        for md_file in md_files:
            doc = Document(
                id=f"repo:{repo_path.name}:{md_file.relative_to(repo_path)}",
                title=md_file.name,
                content=md_file.read_text(),
                type='code_docs',
                metadata={
                    'repo': repo_path.name,
                    'file_path': str(md_file.relative_to(repo_path))
                }
            )
            await self.index_document(doc)
        
        for py_file in py_files:
            docstrings = self.extract_docstrings(py_file)
            for ds in docstrings:
                doc = Document(
                    id=f"repo:{repo_path.name}:{py_file.relative_to(repo_path)}:{ds.name}",
                    title=f"{py_file.name}::{ds.name}",
                    content=ds.content,
                    type='code_docs',
                    metadata={
                        'repo': repo_path.name,
                        'file_path': str(py_file.relative_to(repo_path)),
                        'symbol': ds.name,
                        'symbol_type': ds.type  # function, class, module
                    }
                )
                await self.index_document(doc)
```

---

## Part 5: Chunking Strategies

### 5.1 Adaptive Chunking

Different document types need different chunking approaches:

```python
class AdaptiveChunker:
    """
    Intelligent chunking based on document structure
    """
    
    def __init__(self, config: ChunkConfig):
        self.max_chunk_size = config.max_chunk_size  # tokens
        self.overlap = config.overlap
        self.min_chunk_size = config.min_chunk_size
        
    def chunk_technical(self, content: str) -> List[Chunk]:
        """
        Technical documents: Respect section boundaries
        """
        # 1. Parse into sections (by headers)
        sections = self.parse_sections(content)
        
        chunks = []
        for section in sections:
            # If section fits, use as-is
            if self.token_count(section.text) <= self.max_chunk_size:
                chunks.append(Chunk(
                    text=section.text,
                    metadata={'section': section.header}
                ))
            else:
                # Split by paragraphs, maintaining context
                paragraphs = section.text.split('\n\n')
                current_chunk = f"# {section.header}\n\n"
                
                for para in paragraphs:
                    if self.token_count(current_chunk + para) <= self.max_chunk_size:
                        current_chunk += para + '\n\n'
                    else:
                        if current_chunk.strip():
                            chunks.append(Chunk(
                                text=current_chunk.strip(),
                                metadata={'section': section.header}
                            ))
                        current_chunk = f"# {section.header} (continued)\n\n{para}\n\n"
                
                if current_chunk.strip():
                    chunks.append(Chunk(
                        text=current_chunk.strip(),
                        metadata={'section': section.header}
                    ))
        
        return chunks
    
    def chunk_code(self, content: str) -> List[Chunk]:
        """
        Code documents: Respect function/class boundaries
        """
        # Parse AST to find logical boundaries
        tree = ast.parse(content)
        
        chunks = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Extract function/class with docstring
                source = ast.get_source_segment(content, node)
                
                chunks.append(Chunk(
                    text=source,
                    metadata={
                        'type': 'function' if isinstance(node, ast.FunctionDef) else 'class',
                        'name': node.name,
                        'lineno': node.lineno
                    }
                ))
        
        return chunks
    
    def chunk_with_hierarchy(self, content: str) -> List[Chunk]:
        """
        Hierarchical chunking: Include parent context
        """
        # Create chunk tree
        sections = self.parse_sections(content)
        
        chunks = []
        for section in sections:
            # Include breadcrumb path in chunk
            path = self.get_section_path(section)
            prefixed_text = f"Context: {' > '.join(path)}\n\n{section.text}"
            
            chunks.append(Chunk(
                text=prefixed_text,
                metadata={
                    'section': section.header,
                    'path': path,
                    'level': section.level
                }
            ))
        
        return chunks
```

### 5.2 Parent Document Retrieval

```python
class ParentDocumentRetriever:
    """
    Retrieves chunks but returns parent context
    """
    
    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        # 1. Find relevant chunks
        chunks = self.chunk_retriever.search(query, k=k * 3)
        
        # 2. Group by parent document
        by_parent = defaultdict(list)
        for chunk in chunks:
            by_parent[chunk.metadata['doc_id']].append(chunk)
        
        # 3. Score parents by chunk relevance
        parent_scores = {}
        for doc_id, doc_chunks in by_parent.items():
            # Aggregate chunk scores
            parent_scores[doc_id] = sum(c.score for c in doc_chunks)
        
        # 4. Get top-k parents
        top_parents = sorted(parent_scores.items(), key=lambda x: -x[1])[:k]
        
        # 5. Retrieve full parent documents (or expanded context)
        results = []
        for doc_id, score in top_parents:
            # Get chunks for this document
            doc_chunks = by_parent[doc_id]
            
            # Expand to include surrounding context
            expanded = self.expand_chunks(doc_chunks)
            
            results.append(Document(
                id=doc_id,
                content=expanded,
                score=score,
                metadata=doc_chunks[0].metadata
            ))
        
        return results
```

---

## Part 6: Context Assembly & Compression

### 6.1 Context Window Management

```python
class ContextAssembler:
    """
    Assembles retrieved content to fit LLM context window
    """
    
    def __init__(self, max_context_tokens: int = 100000):
        self.max_tokens = max_context_tokens
        self.reserve_for_generation = 4000
        self.available = self.max_tokens - self.reserve_for_generation
        
    def assemble(
        self, 
        query: str,
        retrieved: List[Document],
        conversation_history: List[Message] = None
    ) -> str:
        """
        Assemble context that fits in LLM window
        """
        # 1. Calculate token budgets
        history_tokens = self.count_tokens(conversation_history) if conversation_history else 0
        query_tokens = self.count_tokens(query)
        remaining = self.available - history_tokens - query_tokens
        
        # 2. Rerank retrieved documents
        reranked = self.rerank(query, retrieved)
        
        # 3. Greedily add documents until budget exhausted
        context_parts = []
        used_tokens = 0
        
        for doc in reranked:
            doc_tokens = self.count_tokens(doc.content)
            
            if used_tokens + doc_tokens <= remaining:
                context_parts.append(self.format_document(doc))
                used_tokens += doc_tokens
            else:
                # Try to fit truncated version
                available_for_doc = remaining - used_tokens
                if available_for_doc > 500:  # Minimum useful size
                    truncated = self.smart_truncate(doc.content, available_for_doc)
                    context_parts.append(self.format_document(doc, truncated))
                break
        
        # 4. Format final context
        return self.format_context(context_parts)
    
    def smart_truncate(self, content: str, max_tokens: int) -> str:
        """
        Truncate preserving important parts (start, relevant sections)
        """
        sentences = content.split('. ')
        
        # Always include first paragraph
        result = sentences[0] + '. '
        used = self.count_tokens(result)
        
        # Add remaining sentences until limit
        for sent in sentences[1:]:
            sent_tokens = self.count_tokens(sent)
            if used + sent_tokens <= max_tokens:
                result += sent + '. '
                used += sent_tokens
            else:
                result += '...[truncated]'
                break
        
        return result
    
    def rerank(self, query: str, documents: List[Document]) -> List[Document]:
        """
        Use cross-encoder for more accurate ranking
        """
        pairs = [(query, doc.content) for doc in documents]
        scores = self.reranker.score(pairs)
        
        for doc, score in zip(documents, scores):
            doc.rerank_score = score
        
        return sorted(documents, key=lambda x: -x.rerank_score)
```

### 6.2 Context Compression for Long Documents

```python
class ContextCompressor:
    """
    Compress context when too much relevant content
    """
    
    def compress(
        self, 
        query: str,
        documents: List[Document],
        target_tokens: int
    ) -> str:
        """
        Compress documents to fit target token budget
        """
        total_tokens = sum(self.count_tokens(d.content) for d in documents)
        
        if total_tokens <= target_tokens:
            return '\n\n'.join(d.content for d in documents)
        
        # Need compression
        compression_ratio = target_tokens / total_tokens
        
        if compression_ratio > 0.5:
            # Light compression: extractive summarization
            return self.extractive_compress(query, documents, target_tokens)
        else:
            # Heavy compression: abstractive summarization
            return self.abstractive_compress(query, documents, target_tokens)
    
    def extractive_compress(
        self, 
        query: str,
        documents: List[Document],
        target_tokens: int
    ) -> str:
        """
        Keep most relevant sentences
        """
        all_sentences = []
        
        for doc in documents:
            sentences = self.split_sentences(doc.content)
            for sent in sentences:
                all_sentences.append({
                    'text': sent,
                    'doc_id': doc.id,
                    'score': self.score_relevance(query, sent)
                })
        
        # Sort by relevance
        all_sentences.sort(key=lambda x: -x['score'])
        
        # Take top sentences until budget
        result = []
        used = 0
        
        for sent in all_sentences:
            tokens = self.count_tokens(sent['text'])
            if used + tokens <= target_tokens:
                result.append(sent)
                used += tokens
        
        # Reorder by original position for coherence
        result.sort(key=lambda x: (x['doc_id'], documents[0].content.find(x['text'])))
        
        return ' '.join(s['text'] for s in result)
    
    def abstractive_compress(
        self,
        query: str,
        documents: List[Document],
        target_tokens: int
    ) -> str:
        """
        Use LLM to summarize (for heavy compression)
        """
        prompt = f"""Summarize the following documents to answer this query.
        Keep only information directly relevant to the query.
        Target length: approximately {target_tokens // 4} words.
        
        Query: {query}
        
        Documents:
        {self._format_docs(documents)}
        
        Focused Summary:"""
        
        return self.llm.generate(prompt, max_tokens=target_tokens)
```

---

## Part 7: Agent Orchestration

### 7.1 LangGraph Workflow for RAG

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List

class RAGState(TypedDict):
    # Input
    query: str
    conversation_history: List[Message]
    user_context: UserContext
    
    # Processing
    query_type: str
    entities: List[str]
    retrieval_plan: List[RetrievalStep]
    
    # Retrieved content
    retrieved_docs: List[Document]
    reranked_docs: List[Document]
    assembled_context: str
    
    # Output
    response: str
    citations: List[Citation]
    confidence: float
    follow_up_questions: List[str]


def create_rag_workflow() -> StateGraph:
    """
    Create the RAG workflow graph
    """
    workflow = StateGraph(RAGState)
    
    # Add nodes
    workflow.add_node("understand_query", understand_query_node)
    workflow.add_node("plan_retrieval", plan_retrieval_node)
    workflow.add_node("execute_retrieval", execute_retrieval_node)
    workflow.add_node("rerank_and_filter", rerank_node)
    workflow.add_node("check_sufficiency", check_sufficiency_node)
    workflow.add_node("assemble_context", assemble_context_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("extract_citations", extract_citations_node)
    workflow.add_node("generate_followups", generate_followups_node)
    
    # Define edges
    workflow.add_edge("understand_query", "plan_retrieval")
    workflow.add_edge("plan_retrieval", "execute_retrieval")
    workflow.add_edge("execute_retrieval", "rerank_and_filter")
    
    # Conditional: Need more retrieval?
    workflow.add_conditional_edges(
        "rerank_and_filter",
        should_retrieve_more,
        {
            "more": "plan_retrieval",  # Loop back
            "sufficient": "check_sufficiency"
        }
    )
    
    workflow.add_conditional_edges(
        "check_sufficiency",
        is_context_sufficient,
        {
            "yes": "assemble_context",
            "no": "plan_retrieval"  # Try different strategy
        }
    )
    
    workflow.add_edge("assemble_context", "generate_response")
    workflow.add_edge("generate_response", "extract_citations")
    workflow.add_edge("extract_citations", "generate_followups")
    workflow.add_edge("generate_followups", END)
    
    # Set entry point
    workflow.set_entry_point("understand_query")
    
    return workflow.compile()


# Node implementations
async def understand_query_node(state: RAGState) -> RAGState:
    """Analyze query intent and extract entities"""
    
    # Classify query type
    state['query_type'] = await classify_query(state['query'])
    
    # Extract entities (documents, people, projects mentioned)
    state['entities'] = await extract_entities(state['query'])
    
    return state


async def plan_retrieval_node(state: RAGState) -> RAGState:
    """Create retrieval plan based on query type"""
    
    router = RetrievalRouter()
    strategy = router.route(state['query'], state['user_context'])
    
    state['retrieval_plan'] = strategy.create_plan(
        query=state['query'],
        entities=state['entities'],
        already_retrieved=state.get('retrieved_docs', [])
    )
    
    return state


async def execute_retrieval_node(state: RAGState) -> RAGState:
    """Execute retrieval plan"""
    
    retrieved = []
    
    for step in state['retrieval_plan']:
        if step.type == 'dense':
            results = await dense_retriever.search(step.query, k=step.k)
        elif step.type == 'sparse':
            results = await sparse_retriever.search(step.query, k=step.k)
        elif step.type == 'graph':
            results = await graph_retriever.search(step.query, k=step.k)
        elif step.type == 'hybrid':
            results = await hybrid_retriever.search(step.query, k=step.k)
        
        retrieved.extend(results)
    
    # Deduplicate
    seen = set()
    unique = []
    for doc in retrieved:
        if doc.id not in seen:
            seen.add(doc.id)
            unique.append(doc)
    
    state['retrieved_docs'] = unique
    return state


def should_retrieve_more(state: RAGState) -> str:
    """Decide if more retrieval needed"""
    
    # Check if we have enough relevant documents
    if len(state['reranked_docs']) < 3:
        return "more"
    
    # Check if top documents are relevant enough
    if state['reranked_docs'][0].score < 0.5:
        return "more"
    
    return "sufficient"


async def generate_response_node(state: RAGState) -> RAGState:
    """Generate response using local LLM"""
    
    prompt = f"""You are a helpful assistant for DocFlow, a documentation system.
    
Answer the user's question based on the provided context. If the context doesn't contain
enough information, say so clearly. Always cite your sources using [DocTitle] notation.

Context:
{state['assembled_context']}

Conversation History:
{format_history(state['conversation_history'])}

User Question: {state['query']}

Answer:"""
    
    response = await llm.generate(prompt)
    state['response'] = response
    
    # Estimate confidence based on retrieval scores
    state['confidence'] = calculate_confidence(state['reranked_docs'])
    
    return state
```

### 7.2 Tool-Augmented Agent

```python
class DocFlowRAGAgent:
    """
    Agent with tools for complex RAG tasks
    """
    
    TOOLS = [
        {
            "name": "search_documents",
            "description": "Search for documents by content",
            "parameters": {
                "query": "Search query",
                "filters": "Optional filters (author, project, state)",
                "k": "Number of results"
            }
        },
        {
            "name": "search_code",
            "description": "Search code repositories and documentation",
            "parameters": {
                "query": "Search query",
                "repo": "Optional repository name",
                "file_type": "Optional file type filter"
            }
        },
        {
            "name": "get_document",
            "description": "Retrieve full document by ID",
            "parameters": {
                "doc_id": "Document ID"
            }
        },
        {
            "name": "get_related_documents",
            "description": "Find documents related to a given document",
            "parameters": {
                "doc_id": "Source document ID",
                "relationship_type": "Type of relationship (references, supersedes, etc.)"
            }
        },
        {
            "name": "get_document_history",
            "description": "Get version history and changes",
            "parameters": {
                "doc_id": "Document ID",
                "since": "Optional date filter"
            }
        },
        {
            "name": "search_by_author",
            "description": "Find documents by author",
            "parameters": {
                "author": "Author name or email"
            }
        },
        {
            "name": "get_project_documents",
            "description": "Get all documents for a project",
            "parameters": {
                "project": "Project name"
            }
        },
        {
            "name": "compare_versions",
            "description": "Compare two versions of a document",
            "parameters": {
                "doc_id": "Document ID",
                "version_a": "First version",
                "version_b": "Second version"
            }
        }
    ]
    
    async def run(self, query: str, context: UserContext) -> AgentResponse:
        """
        Run agent with ReAct-style reasoning
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query}
        ]
        
        max_iterations = 5
        
        for _ in range(max_iterations):
            # Get LLM response (may include tool calls)
            response = await self.llm.generate(
                messages,
                tools=self.TOOLS,
                tool_choice="auto"
            )
            
            if response.tool_calls:
                # Execute tool calls
                tool_results = []
                for tool_call in response.tool_calls:
                    result = await self.execute_tool(
                        tool_call.name,
                        tool_call.arguments
                    )
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "result": result
                    })
                
                # Add tool results to conversation
                messages.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
                messages.append({"role": "tool", "content": json.dumps(tool_results)})
            else:
                # Final response
                return AgentResponse(
                    answer=response.content,
                    tool_calls_made=self.tool_history,
                    sources=self.cited_sources
                )
        
        return AgentResponse(
            answer="I couldn't find a complete answer within the allowed steps.",
            tool_calls_made=self.tool_history,
            sources=self.cited_sources
        )
```

---

## Part 8: Incremental Indexing & Updates

### 8.1 Change Detection

```python
class IncrementalIndexer:
    """
    Efficiently update indices when documents change
    """
    
    def __init__(self, config: IndexConfig):
        self.vector_store = ChromaDB(config.vector_store)
        self.sparse_index = SQLiteFTS(config.sparse_index)
        self.graph = KnowledgeGraph(config.graph)
        self.change_log = ChangeLog(config.change_log)
        
    async def process_changes(self):
        """
        Process pending document changes
        """
        # Get changes since last sync
        changes = await self.change_log.get_pending()
        
        for change in changes:
            if change.type == 'created':
                await self.index_document(change.document)
            elif change.type == 'updated':
                await self.update_document(change.document)
            elif change.type == 'deleted':
                await self.delete_document(change.document_id)
            elif change.type == 'published':
                await self.promote_to_team(change.document)
            
            # Mark as processed
            await self.change_log.mark_processed(change.id)
    
    async def update_document(self, doc: Document):
        """
        Update existing document (re-chunk, re-embed)
        """
        old_doc = await self.get_current(doc.id)
        
        # Calculate content hash
        new_hash = self.hash_content(doc.content)
        old_hash = old_doc.metadata.get('content_hash')
        
        if new_hash == old_hash:
            # No content change, just metadata
            await self.update_metadata_only(doc)
            return
        
        # Content changed - need to re-embed
        # 1. Delete old chunks
        await self.vector_store.delete(
            where={"doc_id": doc.id}
        )
        
        # 2. Re-chunk and re-embed
        chunks = self.chunker.chunk(doc)
        embeddings = await self.embedder.embed_batch([c.text for c in chunks])
        
        # 3. Insert new chunks
        await self.vector_store.upsert(
            collection=self.get_collection(doc),
            ids=[f"{doc.id}_{i}" for i in range(len(chunks))],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[{
                **c.metadata,
                'doc_id': doc.id,
                'content_hash': new_hash
            } for c in chunks]
        )
        
        # 4. Update graph relationships
        await self.update_graph_relationships(doc, old_doc)
    
    async def watch_directories(self, paths: List[Path]):
        """
        Watch directories for changes
        """
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        
        class DocFlowHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if self.is_doc_file(event.src_path):
                    asyncio.create_task(
                        self.change_log.record_change('updated', event.src_path)
                    )
            
            def on_created(self, event):
                if self.is_doc_file(event.src_path):
                    asyncio.create_task(
                        self.change_log.record_change('created', event.src_path)
                    )
            
            def on_deleted(self, event):
                if self.is_doc_file(event.src_path):
                    asyncio.create_task(
                        self.change_log.record_change('deleted', event.src_path)
                    )
        
        observer = Observer()
        handler = DocFlowHandler()
        
        for path in paths:
            observer.schedule(handler, str(path), recursive=True)
        
        observer.start()
```

### 8.2 Team Document Sync

```python
class TeamDocumentSync:
    """
    Sync published documents from team members
    """
    
    async def sync_team_documents(self, team_id: str):
        """
        Sync all published documents from team
        """
        # Get team members
        team = await self.get_team(team_id)
        
        for member in team.members:
            await self.sync_member_published(member)
    
    async def sync_member_published(self, member: TeamMember):
        """
        Sync published documents from one team member
        """
        # Check their published folder
        published_docs = await self.storage_provider.list_documents(
            path=member.published_path,
            state='published'
        )
        
        for doc_info in published_docs:
            # Check if we have this version
            local_version = await self.get_local_version(doc_info.id)
            
            if local_version is None or local_version < doc_info.version:
                # Download and index
                doc = await self.storage_provider.download(doc_info.id)
                
                # Add team metadata
                doc.metadata['source'] = 'team'
                doc.metadata['author'] = member.name
                doc.metadata['author_email'] = member.email
                
                await self.indexer.index_document(doc)
    
    async def sync_code_repositories(self, repos: List[RepoConfig]):
        """
        Sync README.md and docs from code repos
        """
        for repo in repos:
            # Clone or pull latest
            local_path = await self.git.ensure_latest(repo.url, repo.branch)
            
            # Index markdown files
            await self.indexer.index_code_repository(local_path)
```

---

## Part 9: Configuration & Deployment

### 9.1 Complete Configuration Schema

```yaml
# ~/.docflow/config.yaml

# LLM Configuration
llm:
  provider: "local"  # local, anthropic, openai
  
  local:
    base_url: "http://localhost:8000/v1"
    api_key: "local-key"
    
    models:
      generation: "kimi-k2.5"
      fast: "llama-3.2-3b"
      
    parameters:
      temperature: 0.7
      max_tokens: 4096
      
  # Fallback to cloud if local unavailable
  fallback:
    provider: "anthropic"
    model: "claude-3-haiku"
    api_key: "${ANTHROPIC_API_KEY}"

# Embedding Configuration  
embedding:
  provider: "local"
  
  local:
    text_model: "nomic-embed-text-v1.5"
    code_model: "jina-embeddings-v3"
    base_url: "http://localhost:8001/v1"
    
  # Reranker
  reranker:
    model: "bge-reranker-v2-m3"
    base_url: "http://localhost:8002/v1"

# Vector Store
vector_store:
  provider: "chroma"  # chroma, qdrant, pinecone
  
  chroma:
    path: "~/.docflow/chroma"
    
  collections:
    personal_docs:
      distance: "cosine"
      embedding_dim: 768
    team_published:
      distance: "cosine"
      embedding_dim: 768
    code_docs:
      distance: "cosine"
      embedding_dim: 1024  # Code embeddings
    meeting_context:
      distance: "cosine"
      embedding_dim: 768
    external_refs:
      distance: "cosine"
      embedding_dim: 768

# Knowledge Graph
graph:
  provider: "networkx"  # networkx, neo4j
  
  networkx:
    path: "~/.docflow/knowledge_graph.pickle"
    
  # Auto-extract relationships
  extraction:
    enabled: true
    extract_references: true
    extract_mentions: true
    extract_authors: true

# Retrieval Configuration
retrieval:
  # Hybrid retrieval weights
  hybrid:
    dense_weight: 0.7
    sparse_weight: 0.3
    
  # Default k values
  defaults:
    k: 10
    rerank_k: 5
    
  # Query routing
  routing:
    enabled: true
    classifier: "llm"  # llm, classifier
    
  # Context assembly
  context:
    max_tokens: 100000  # For Kimi K2.5's 128k window
    reserve_for_generation: 4000
    compression:
      enabled: true
      threshold: 0.7  # Compress if > 70% of budget

# Chunking Configuration
chunking:
  max_chunk_size: 512  # tokens
  overlap: 50
  min_chunk_size: 100
  
  # Strategy per document type
  strategies:
    technical: "section_aware"
    code: "ast_aware"
    general: "recursive"

# Team Configuration
team:
  id: "ut_computational_ne"
  sync_interval: 3600  # seconds
  
  members:
    - name: "Team Member 1"
      email: "member1@utexas.edu"
      published_path: "/shared/member1/published"
      
  repositories:
    - url: "git@github.com:UT-CompNE/bubble_flow_tools.git"
      branch: "main"
      doc_paths: ["docs/", "README.md"]
      
    - url: "git@github.com:UT-CompNE/msr_tools.git"
      branch: "main"
      doc_paths: ["docs/", "README.md"]

# Storage
storage:
  provider: "multi"  # local, onedrive, google, multi
  
  local:
    root: "~/Documents/DocFlow"
    
  onedrive:
    tenant_id: "${AZURE_TENANT_ID}"
    client_id: "${AZURE_CLIENT_ID}"
    
  google:
    credentials: "~/.docflow/google_credentials.json"
    folder_id: "${GOOGLE_DRIVE_FOLDER_ID}"
```

### 9.2 Deployment Docker Compose

```yaml
# docker-compose.yml

version: '3.8'

services:
  # vLLM for generation
  vllm:
    image: vllm/vllm-openai:latest
    command: >
      --model moonshot-ai/kimi-k2.5
      --tensor-parallel-size 1
      --max-model-len 131072
      --quantization awq
    ports:
      - "8000:8000"
    volumes:
      - ./models:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  # Embedding server
  embedding:
    image: ghcr.io/huggingface/text-embeddings-inference:latest
    command: >
      --model-id nomic-ai/nomic-embed-text-v1.5
      --port 8001
    ports:
      - "8001:8001"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  # ChromaDB
  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8002:8000"
    volumes:
      - chroma_data:/chroma/chroma
    environment:
      - ANONYMIZED_TELEMETRY=False
  
  # Redis for caching
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  # DocFlow API
  docflow-api:
    build: .
    ports:
      - "8080:8080"
    environment:
      - LLM_BASE_URL=http://vllm:8000/v1
      - EMBEDDING_BASE_URL=http://embedding:8001
      - CHROMA_URL=http://chroma:8000
      - REDIS_URL=redis://redis:6379
    depends_on:
      - vllm
      - embedding
      - chroma
      - redis
    volumes:
      - ./config:/app/config
      - docflow_data:/app/data

volumes:
  chroma_data:
  redis_data:
  docflow_data:
```

---

## Part 10: Evaluation & Monitoring

### 10.1 RAG Quality Metrics

```python
class RAGEvaluator:
    """
    Evaluate RAG system quality
    """
    
    async def evaluate_retrieval(
        self,
        query: str,
        retrieved: List[Document],
        ground_truth: List[str]
    ) -> RetrievalMetrics:
        """
        Evaluate retrieval quality
        """
        retrieved_ids = {d.id for d in retrieved}
        relevant_ids = set(ground_truth)
        
        # Precision@k
        precision = len(retrieved_ids & relevant_ids) / len(retrieved_ids)
        
        # Recall
        recall = len(retrieved_ids & relevant_ids) / len(relevant_ids)
        
        # NDCG
        ndcg = self.calculate_ndcg(retrieved, ground_truth)
        
        # MRR
        mrr = self.calculate_mrr(retrieved, ground_truth)
        
        return RetrievalMetrics(
            precision=precision,
            recall=recall,
            ndcg=ndcg,
            mrr=mrr
        )
    
    async def evaluate_generation(
        self,
        query: str,
        response: str,
        context: str,
        ground_truth: str = None
    ) -> GenerationMetrics:
        """
        Evaluate generation quality
        """
        # Faithfulness: Is response grounded in context?
        faithfulness = await self.llm_judge(
            prompt=f"""Rate how faithful this response is to the given context.
            Score 1-5 where 5 = completely faithful, no hallucinations.
            
            Context: {context}
            Response: {response}
            
            Score:"""
        )
        
        # Relevance: Does response answer the query?
        relevance = await self.llm_judge(
            prompt=f"""Rate how relevant this response is to the query.
            Score 1-5 where 5 = directly and completely answers the query.
            
            Query: {query}
            Response: {response}
            
            Score:"""
        )
        
        # Answer correctness (if ground truth available)
        correctness = None
        if ground_truth:
            correctness = await self.llm_judge(
                prompt=f"""Rate the correctness of this response compared to ground truth.
                Score 1-5 where 5 = completely correct.
                
                Ground Truth: {ground_truth}
                Response: {response}
                
                Score:"""
            )
        
        return GenerationMetrics(
            faithfulness=faithfulness,
            relevance=relevance,
            correctness=correctness
        )
```

### 10.2 Monitoring Dashboard

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Retrieval metrics
retrieval_latency = Histogram(
    'docflow_retrieval_latency_seconds',
    'Time spent retrieving documents',
    ['strategy']  # dense, sparse, hybrid, graph
)

retrieval_count = Counter(
    'docflow_retrieval_total',
    'Total retrieval requests',
    ['strategy', 'collection']
)

retrieval_empty = Counter(
    'docflow_retrieval_empty_total',
    'Retrievals that returned no results'
)

# Generation metrics
generation_latency = Histogram(
    'docflow_generation_latency_seconds',
    'Time spent generating responses'
)

tokens_used = Counter(
    'docflow_tokens_total',
    'Total tokens used',
    ['type']  # input, output
)

# Quality metrics
faithfulness_score = Histogram(
    'docflow_faithfulness_score',
    'Faithfulness scores for responses'
)

relevance_score = Histogram(
    'docflow_relevance_score',
    'Relevance scores for responses'
)

# Cache metrics
cache_hits = Counter(
    'docflow_cache_hits_total',
    'Cache hit count',
    ['cache_type']  # embedding, retrieval, generation
)

cache_misses = Counter(
    'docflow_cache_misses_total',
    'Cache miss count',
    ['cache_type']
)
```

---

## Summary: Decision Matrix

| Decision Point | Recommendation | Rationale |
|----------------|----------------|-----------|
| **Primary LLM** | Kimi K2.5 (local) | 128k context, MoE efficiency, technical strength |
| **Text Embedding** | nomic-embed-text-v1.5 | 8k context, open weights, good quality |
| **Code Embedding** | jina-embeddings-v3 | Code-optimized, multilingual |
| **Reranker** | BGE-reranker-v2-m3 | Best quality/speed tradeoff |
| **Vector Store** | ChromaDB (local) → Qdrant (scale) | Easy local, scales well |
| **Sparse Index** | SQLite FTS5 | Simple, fast, no dependencies |
| **Graph Store** | NetworkX → Neo4j (scale) | In-memory fast, Neo4j for team |
| **Default Retrieval** | Hybrid (0.7 dense + 0.3 sparse) | Best coverage for technical docs |
| **Chunking** | Section-aware, 512 tokens | Preserve document structure |
| **Context Window** | Use 100k of 128k | Reserve for generation |

---

## Next Steps

1. **Phase 1**: Deploy local LLM infrastructure (vLLM + embeddings)
2. **Phase 2**: Implement hybrid retriever with your documents
3. **Phase 3**: Build knowledge graph from existing relationships
4. **Phase 4**: Add team document sync
5. **Phase 5**: Deploy agent workflow with LangGraph
6. **Phase 6**: Add monitoring and evaluation

Ready to implement? Start with the local LLM setup and basic hybrid retrieval.