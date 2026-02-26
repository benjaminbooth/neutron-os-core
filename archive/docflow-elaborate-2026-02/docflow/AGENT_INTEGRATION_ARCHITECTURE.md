# Agent Integration Architecture

## Critical Constraint

> **DocFlow must have ZERO dependencies on other Neutron OS components.**
> Other systems depend on DocFlow, not the reverse.

This fundamentally shapes where agent code lives.

---

## Part 1: ChromaDB vs PostgreSQL + pgvector

### Recommendation: **Use pgvector**

Since you're already running PostgreSQL, pgvector is the right choice:

| Factor | pgvector | ChromaDB |
|--------|----------|----------|
| **Ops overhead** | Zero (same DB) | New service to manage |
| **Transactions** | Full ACID with your data | Separate consistency model |
| **Hybrid search** | Native (vectors + FTS + filters in one query) | Requires multiple calls |
| **Backup/Recovery** | Same as your existing DB | Separate backup strategy |
| **Scaling** | You already know how | Different scaling model |
| **Maturity** | Production-proven | Good but younger |
| **Performance** | Excellent with HNSW indexes | Slightly faster for pure vector |

### pgvector Setup

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text search

-- Document chunks with embeddings
CREATE TABLE doc_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),  -- nomic-embed dimension
    
    -- Metadata for filtering
    collection TEXT NOT NULL,  -- personal, team, code, meeting
    author TEXT,
    project TEXT,
    state TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Full-text search
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- HNSW index for fast approximate nearest neighbor
CREATE INDEX ON doc_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Full-text search index
CREATE INDEX ON doc_chunks USING GIN (content_tsv);

-- Composite index for filtered searches
CREATE INDEX ON doc_chunks (collection, project);
```

### Hybrid Search Query

```sql
-- Single query: semantic + keyword + filters
WITH semantic AS (
    SELECT id, doc_id, content,
           1 - (embedding <=> $1::vector) AS semantic_score
    FROM doc_chunks
    WHERE collection = $2
      AND ($3::text IS NULL OR project = $3)
    ORDER BY embedding <=> $1::vector
    LIMIT 20
),
keyword AS (
    SELECT id, doc_id, content,
           ts_rank(content_tsv, plainto_tsquery('english', $4)) AS keyword_score
    FROM doc_chunks
    WHERE content_tsv @@ plainto_tsquery('english', $4)
      AND collection = $2
    LIMIT 20
)
SELECT 
    COALESCE(s.id, k.id) AS id,
    COALESCE(s.doc_id, k.doc_id) AS doc_id,
    COALESCE(s.content, k.content) AS content,
    -- RRF fusion
    COALESCE(1.0 / (60 + s.rank), 0) + COALESCE(1.0 / (60 + k.rank), 0) AS score
FROM (SELECT *, ROW_NUMBER() OVER (ORDER BY semantic_score DESC) AS rank FROM semantic) s
FULL OUTER JOIN (SELECT *, ROW_NUMBER() OVER (ORDER BY keyword_score DESC) AS rank FROM keyword) k
    ON s.id = k.id
ORDER BY score DESC
LIMIT 10;
```

---

## Part 2: Layered Agent Architecture

Given DocFlow's independence constraint, here's the clean architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Dependency Flow                                 │
│                         (arrows point to dependencies)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Neutron CLI (future)                         │   │
│  │  • Top-level orchestrator                                            │   │
│  │  • Can import and use ALL tools                                      │   │
│  │  • Houses the "Neutron Agent" (cross-system)                        │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│              ┌───────────────────┼───────────────────┐                     │
│              ▼                   ▼                   ▼                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │    DocFlow       │  │  SAM Tools       │  │  TRIGA Tools     │         │
│  │  ─────────────── │  │  ─────────────── │  │  ─────────────── │         │
│  │  DocFlow Agent   │  │  (can use        │  │  (can use        │         │
│  │  (docs only)     │  │   DocFlow)       │  │   DocFlow)       │         │
│  │                  │  │                  │  │                  │         │
│  │  NO EXTERNAL     │  │                  │  │                  │         │
│  │  DEPENDENCIES    │  │                  │  │                  │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│           │                                                                 │
│           │ (DocFlow is a leaf - nothing below it)                         │
│           ▼                                                                 │
│       [PostgreSQL]  ← Only external dependency (database)                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Two Distinct Agents

| Agent | Scope | Lives In | Can Access |
|-------|-------|----------|------------|
| **DocFlow Agent** | Documents only | `docflow/` | DocFlow DB, doc embeddings, doc graph |
| **Neutron Agent** | Everything | `neutron_cli/` (future) | All tools including DocFlow Agent as a tool |

---

## Part 3: Code Organization

### Current Recommended Structure

```
Neutron_OS/
├── docs/
│   └── _tools/
│       └── docflow/                    # STANDALONE - no external deps
│           ├── src/
│           │   └── docflow/
│           │       ├── agent/          # DocFlow-specific agent
│           │       │   ├── __init__.py
│           │       │   ├── core.py         # DocFlowAgent class
│           │       │   ├── tools.py        # Document-only tools
│           │       │   ├── retriever.py    # Hybrid retrieval (pgvector)
│           │       │   └── prompts.py      # System prompts
│           │       ├── rag/            # RAG infrastructure
│           │       │   ├── __init__.py
│           │       │   ├── embedder.py     # Embedding pipeline
│           │       │   ├── chunker.py      # Document chunking
│           │       │   ├── indexer.py      # Index management
│           │       │   └── pgvector.py     # PostgreSQL vector store
│           │       └── ...             # Existing docflow code
│           ├── config/
│           │   ├── agent.yaml          # Agent config (models, params)
│           │   └── rag.yaml            # RAG config (chunking, retrieval)
│           └── pyproject.toml
│
├── neutron_cli/                        # FUTURE - top-level orchestrator
│   ├── src/
│   │   └── neutron/
│   │       ├── agent/                  # Cross-system agent
│   │       │   ├── __init__.py
│   │       │   ├── core.py             # NeutronAgent class
│   │       │   ├── tools.py            # All system tools
│           │   └── orchestrator.py     # Multi-agent coordination
│   │       └── cli/
│   │           └── main.py
│   └── pyproject.toml                  # Depends on docflow, sam_tools, etc.
│
└── shared/                             # OPTIONAL - shared utilities
    └── llm_client/                     # Common LLM interface
        ├── __init__.py
        └── client.py                   # vLLM/Ollama client wrapper
```

### Why This Structure?

1. **DocFlow remains independent**: Its agent only knows about documents
2. **Neutron CLI composes**: It imports DocFlow and uses its agent as a tool
3. **Gradual adoption**: DocFlow agent works standalone TODAY
4. **Clean boundaries**: Each agent has clear, limited scope

---

## Part 4: Agent Interface Design

### DocFlow Agent (Standalone)

```python
# docflow/agent/core.py

class DocFlowAgent:
    """
    Document-focused agent. Can be used standalone or as a tool
    by higher-level agents.
    """
    
    def __init__(self, config: AgentConfig):
        self.llm = LocalLLMClient(config.llm)
        self.retriever = HybridRetriever(config.retrieval)
        self.tools = self._build_tools()
    
    # Tools available to this agent (documents only)
    TOOLS = [
        "search_documents",      # Semantic + keyword search
        "get_document",          # Retrieve by ID
        "get_related_documents", # Graph traversal
        "get_document_history",  # Version timeline
        "search_by_author",      # Author filter
        "search_by_project",     # Project filter
        "create_document",       # New doc from template
        "update_document",       # Edit existing
        "generate_diagram",      # AI diagram creation
        "summarize_documents",   # Multi-doc summary
    ]
    
    async def chat(
        self, 
        message: str,
        history: List[Message] = None
    ) -> AgentResponse:
        """
        Single interface for agent interaction.
        Used by CLI, API, or as a tool by Neutron Agent.
        """
        return await self._run_agent_loop(message, history)
    
    def as_tool(self) -> Tool:
        """
        Expose this agent as a tool for higher-level agents.
        """
        return Tool(
            name="docflow_agent",
            description="Expert agent for document search, creation, and management",
            function=self.chat,
            parameters={
                "message": "Natural language request about documents"
            }
        )
```

### Neutron Agent (Future, Composes DocFlow)

```python
# neutron_cli/agent/core.py

from docflow.agent import DocFlowAgent
from sam_tools.agent import SAMAgent  # hypothetical
# ... other tool imports

class NeutronAgent:
    """
    Top-level agent that orchestrates across all Neutron OS tools.
    """
    
    def __init__(self, config: NeutronConfig):
        self.llm = LocalLLMClient(config.llm)
        
        # Compose sub-agents as tools
        self.docflow = DocFlowAgent(config.docflow)
        self.sam = SAMAgent(config.sam) if config.sam else None
        
        self.tools = self._build_tools()
    
    def _build_tools(self) -> List[Tool]:
        tools = [
            # DocFlow agent as a single tool
            self.docflow.as_tool(),
            
            # Direct tools for quick operations
            Tool("list_projects", ...),
            Tool("run_simulation", ...),
            Tool("check_job_status", ...),
        ]
        
        if self.sam:
            tools.append(self.sam.as_tool())
        
        return tools
```

---

## Part 5: CLI UX Design

### DocFlow CLI (Available NOW)

```bash
# Interactive chat mode (Claude Code-style)
$ docflow chat
╭─────────────────────────────────────────────────────────────╮
│  DocFlow Agent                                              │
│  Ask me about your documents, or type /help for commands    │
╰─────────────────────────────────────────────────────────────╯

You: Find all documents about thermal hydraulics that Sarah reviewed

Agent: I found 7 documents matching your criteria:

  1. [TH Analysis for MSR Loop](docs/msr/thermal_analysis.md)
     Author: Ben Booth | Reviewed by: Sarah Chen | State: Published
     
  2. [Heat Transfer Correlations](docs/shared/correlations.md)
     Author: Mike Torres | Reviewed by: Sarah Chen | State: Published
     
  ... (5 more)

  Would you like me to:
  • Summarize these documents?
  • Show the review comments from Sarah?
  • Find related documents?

You: Summarize the first two and show Sarah's comments

Agent: [Thinking: search_documents → get_document (x2) → get_comments]

## Summary

### TH Analysis for MSR Loop
This document covers the thermal-hydraulic modeling approach for...

### Heat Transfer Correlations  
A comprehensive catalog of heat transfer correlations applicable to...

## Sarah's Review Comments

**TH Analysis for MSR Loop** (3 comments):
- "Consider adding uncertainty bounds to Table 3" (resolved)
- "Reference to Smith et al. should be 2024, not 2023" (resolved)
- "Excellent treatment of the boundary layer effects" (positive feedback)

**Heat Transfer Correlations** (1 comment):
- "Missing Dittus-Boelter for turbulent regime" (resolved)

You: /new "TRIGA Thermal Analysis" --template technical

Agent: Created new document:
  Path: docs/triga/thermal_analysis.md
  State: Draft
  Template: Technical Document
  
  Opening in your editor...
```

### Slash Commands (Power User Mode)

```bash
# Quick commands without entering chat
$ docflow /search "boundary conditions" --project msr
$ docflow /status                    # Show pending reviews, drafts
$ docflow /sync                      # Sync with cloud storage
$ docflow /diagram "MSR flow loop"   # Generate diagram

# One-shot agent query
$ docflow ask "What documents reference the N-3 progression problem?"
```

### Neutron CLI (Future)

```bash
# Top-level CLI with access to everything
$ neutron chat
╭─────────────────────────────────────────────────────────────╮
│  Neutron OS Agent                                           │
│  I can help with documents, simulations, and analysis       │
╰─────────────────────────────────────────────────────────────╯

You: Set up a new thermal analysis for the TRIGA pulsing experiment

Agent: I'll help you set up a complete thermal analysis. Let me:

1. **Create documentation** (using DocFlow)
2. **Set up simulation inputs** (using SAM tools)
3. **Configure the analysis pipeline**

[Calling docflow_agent: "Create new technical document for TRIGA pulsing thermal analysis"]

✓ Created: docs/triga/pulsing_thermal_analysis.md

[Calling sam_tools: "Generate input template for TRIGA pulsing transient"]

✓ Created: simulations/triga/pulsing/input.yaml

Would you like me to:
• Open the document for editing?
• Run an initial simulation?
• Find related previous analyses?
```

---

## Part 6: Gradual Team Adoption Strategy

### Phase 1: DocFlow Agent Only (NOW)

Since Neutron OS isn't built yet, start with DocFlow:

```
Week 1-2: Personal Use
├── You (Ben) use docflow chat daily
├── Iterate on prompts and tools based on your workflow
├── Build muscle memory with slash commands
└── Document pain points

Week 3-4: Soft Launch
├── Demo to 1-2 team members
├── "Hey, try this for finding documents"
├── Low stakes: search and summarize only
└── Collect feedback

Month 2: Expand
├── Enable for team document search
├── Add team's published docs to index
├── Monitor usage patterns
└── Refine retrieval quality
```

### Phase 2: Surface AI Gradually

| Surface | Audience | Risk Level | When |
|---------|----------|------------|------|
| `docflow chat` | You | None | Now |
| `docflow ask "..."` | Power users | Low | Week 2 |
| `/search` in CLI | Everyone | Low | Week 3 |
| Auto-suggestions on `docflow new` | Everyone | Low | Month 2 |
| Review comment summarization | Reviewers | Medium | Month 2 |
| Diagram generation | Content creators | Medium | Month 3 |
| Full Neutron agent | Team | Higher | When Neutron CLI exists |

### Entry Points (Where AI Appears)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI Surface Points in DocFlow                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LOW RISK (start here)                                                       │
│  ─────────────────────                                                       │
│  • docflow search "query"     → AI-enhanced retrieval (invisible)           │
│  • docflow chat               → Explicit agent interaction                  │
│  • docflow ask "question"     → One-shot query                              │
│                                                                              │
│  MEDIUM RISK (after trust built)                                            │
│  ───────────────────────────────                                            │
│  • docflow review summary     → AI summarizes feedback                      │
│  • docflow diagram create     → AI generates diagrams                       │
│  • docflow meeting process    → AI extracts action items                    │
│                                                                              │
│  HIGHER RISK (after validation)                                             │
│  ──────────────────────────────                                             │
│  • docflow draft "topic"      → AI drafts initial content                   │
│  • docflow workflow auto      → AI manages document lifecycle               │
│  • Proactive suggestions      → AI suggests actions                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 7: Configuration Strategy

### DocFlow Agent Config (lives in docflow/)

```yaml
# docflow/config/agent.yaml

# LLM Configuration
llm:
  provider: "local"
  
  local:
    base_url: "http://localhost:8000/v1"
    model: "kimi-k2.5"
    
    # Generation parameters
    temperature: 0.7
    max_tokens: 4096
    
  # Fallback when local unavailable
  fallback:
    provider: "anthropic"
    model: "claude-3-haiku-20240307"
    api_key: "${ANTHROPIC_API_KEY}"

# Agent behavior
agent:
  # System prompt customization
  persona: "helpful documentation assistant for nuclear engineering"
  
  # Tool configuration
  tools:
    search_documents:
      enabled: true
      default_k: 10
    create_document:
      enabled: true
      require_confirmation: true  # Ask before creating
    generate_diagram:
      enabled: true
      max_iterations: 3
  
  # Safety
  max_iterations: 10
  timeout_seconds: 60

# RAG configuration
rag:
  # Retrieval
  retrieval:
    strategy: "hybrid"  # hybrid, dense, sparse
    dense_weight: 0.7
    sparse_weight: 0.3
    default_k: 10
    rerank: true
    
  # Embeddings
  embedding:
    model: "nomic-embed-text-v1.5"
    base_url: "http://localhost:8001/v1"
    dimensions: 768
    batch_size: 32
    
  # Vector store (pgvector)
  vector_store:
    provider: "pgvector"
    connection_string: "${DATABASE_URL}"
    table: "doc_chunks"
    
  # Chunking
  chunking:
    strategy: "section_aware"
    max_chunk_size: 512
    overlap: 50
```

### Environment-Specific Overrides

```yaml
# docflow/config/agent.local.yaml (development)
llm:
  local:
    model: "llama-3.2-3b"  # Smaller model for fast iteration

# docflow/config/agent.prod.yaml (team deployment)
llm:
  local:
    model: "kimi-k2.5"
    
agent:
  tools:
    create_document:
      require_confirmation: false  # Trust established
```

---

## Part 8: Integration Points Summary

### DocFlow Exposes (for Neutron to consume)

```python
# docflow/__init__.py

# Core functionality (already exists)
from docflow.core import DocumentState, StateManager
from docflow.review import ReviewManager
from docflow.convert import UniversalConverter

# NEW: Agent interface
from docflow.agent import DocFlowAgent
from docflow.agent.tools import DOCFLOW_TOOLS

# NEW: RAG infrastructure (can be reused)
from docflow.rag import (
    HybridRetriever,
    PgVectorStore,
    DocumentChunker,
    EmbeddingPipeline
)
```

### Neutron Consumes (future)

```python
# neutron_cli/agent/tools.py

from docflow.agent import DocFlowAgent

def build_neutron_tools(config):
    """Build tools for Neutron Agent"""
    
    # DocFlow as a sub-agent tool
    docflow = DocFlowAgent(config.docflow)
    
    tools = [
        docflow.as_tool(),  # "Ask the document expert"
        
        # Other tools...
        build_sam_tool(config.sam),
        build_triga_tool(config.triga),
    ]
    
    return tools
```

---

## Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector store | **pgvector** | Already have PostgreSQL, simpler ops |
| Agent location | **DocFlow agent in docflow/, Neutron agent in neutron_cli/** | Respects dependency constraint |
| First CLI | **docflow chat** | Can ship today, no new infra |
| Adoption strategy | **Start with search, expand gradually** | Build trust before automation |
| Config location | **docflow/config/agent.yaml** | Self-contained, overridable |
| Agent composition | **DocFlow agent as tool for Neutron agent** | Clean abstraction |

---

## Next Steps

1. **Implement pgvector store** in `docflow/rag/pgvector.py`
2. **Build DocFlowAgent** in `docflow/agent/core.py`
3. **Add `docflow chat` command** to CLI
4. **Index your documents** with new embedding pipeline
5. **Iterate** based on your usage
6. **Expand** to team when ready

Ready to implement the pgvector store and basic agent?