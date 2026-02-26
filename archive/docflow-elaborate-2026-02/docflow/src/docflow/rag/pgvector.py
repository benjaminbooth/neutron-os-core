"""
PostgreSQL + pgvector store for DocFlow RAG

Uses your existing PostgreSQL database with pgvector extension
for efficient hybrid search (semantic + keyword + filters).
"""
import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import asyncpg

from ..core.config import get_config


class Collection(str, Enum):
    """Document collections for organized retrieval"""
    PERSONAL = "personal"      # User's drafts, notes
    TEAM = "team"              # Colleagues' published docs
    CODE = "code"              # README.md, docstrings, API docs
    MEETING = "meeting"        # Transcripts, decisions
    EXTERNAL = "external"      # Standards, papers, regulations
    REQUIREMENTS = "requirements"  # Requirements documents
    PRD = "prd"                # Product requirement docs
    DESIGN = "design"          # Design documents
    SPEC = "spec"              # Implementation specs


@dataclass
class Chunk:
    """A document chunk with embedding"""
    id: str
    doc_id: str
    content: str
    embedding: Optional[List[float]] = None
    chunk_index: int = 0
    total_chunks: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class SearchResult:
    """Result from hybrid search"""
    chunk: Chunk
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    combined_score: float = 0.0
    highlights: List[str] = field(default_factory=list)


class PgVectorStore:
    """
    PostgreSQL vector store with pgvector extension.
    
    Supports:
    - Dense retrieval (vector similarity)
    - Sparse retrieval (full-text search)
    - Hybrid retrieval (RRF fusion)
    - Metadata filtering
    - Collection-based organization
    """
    
    # SQL for table creation
    INIT_SQL = """
    -- Enable required extensions
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    
    -- Document chunks with embeddings
    CREATE TABLE IF NOT EXISTS doc_chunks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        doc_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL DEFAULT 0,
        total_chunks INTEGER NOT NULL DEFAULT 1,
        content TEXT NOT NULL,
        embedding vector({dimensions}),
        
        -- Categorization
        collection TEXT NOT NULL DEFAULT 'personal',
        
        -- Metadata for filtering
        author TEXT,
        project TEXT,
        doc_type TEXT,
        state TEXT,
        title TEXT,
        file_path TEXT,
        
        -- Workflow metadata
        parent_doc_id TEXT,  -- For requirements → PRD → spec chains
        workflow_stage TEXT,  -- requirement, prd, design, spec
        
        -- Timestamps
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        doc_created_at TIMESTAMPTZ,
        
        -- Content hash for deduplication
        content_hash TEXT,
        
        -- Full-text search vector
        content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
        
        UNIQUE(doc_id, chunk_index)
    );
    
    -- HNSW index for fast approximate nearest neighbor search
    CREATE INDEX IF NOT EXISTS doc_chunks_embedding_idx 
        ON doc_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    
    -- Full-text search index
    CREATE INDEX IF NOT EXISTS doc_chunks_content_tsv_idx 
        ON doc_chunks USING GIN (content_tsv);
    
    -- Composite indexes for filtered searches
    CREATE INDEX IF NOT EXISTS doc_chunks_collection_idx ON doc_chunks (collection);
    CREATE INDEX IF NOT EXISTS doc_chunks_project_idx ON doc_chunks (project);
    CREATE INDEX IF NOT EXISTS doc_chunks_author_idx ON doc_chunks (author);
    CREATE INDEX IF NOT EXISTS doc_chunks_workflow_idx ON doc_chunks (workflow_stage);
    CREATE INDEX IF NOT EXISTS doc_chunks_parent_idx ON doc_chunks (parent_doc_id);
    
    -- Document relationships (for graph queries)
    CREATE TABLE IF NOT EXISTS doc_relationships (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source_doc_id TEXT NOT NULL,
        target_doc_id TEXT NOT NULL,
        relationship_type TEXT NOT NULL,  -- references, supersedes, implements, derived_from
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        
        UNIQUE(source_doc_id, target_doc_id, relationship_type)
    );
    
    CREATE INDEX IF NOT EXISTS doc_rel_source_idx ON doc_relationships (source_doc_id);
    CREATE INDEX IF NOT EXISTS doc_rel_target_idx ON doc_relationships (target_doc_id);
    CREATE INDEX IF NOT EXISTS doc_rel_type_idx ON doc_relationships (relationship_type);
    """
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        dimensions: int = 768,
        pool_size: int = 10
    ):
        """
        Initialize pgvector store.
        
        Args:
            connection_string: PostgreSQL connection string
            dimensions: Embedding dimensions (768 for nomic, 1024 for jina)
            pool_size: Connection pool size
        """
        self.connection_string = connection_string or get_config().database_url
        self.dimensions = dimensions
        self.pool_size = pool_size
        self._pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self) -> None:
        """Initialize database connection and create tables"""
        self._pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=2,
            max_size=self.pool_size
        )
        
        async with self._pool.acquire() as conn:
            await conn.execute(self.INIT_SQL.format(dimensions=self.dimensions))
    
    async def close(self) -> None:
        """Close database connections"""
        if self._pool:
            await self._pool.close()
    
    async def upsert_chunks(
        self,
        chunks: List[Chunk],
        collection: Collection = Collection.PERSONAL
    ) -> int:
        """
        Insert or update document chunks.
        
        Args:
            chunks: List of chunks to upsert
            collection: Collection to store in
            
        Returns:
            Number of chunks upserted
        """
        if not chunks:
            return 0
        
        async with self._pool.acquire() as conn:
            # Prepare the upsert statement
            stmt = """
                INSERT INTO doc_chunks (
                    doc_id, chunk_index, total_chunks, content, embedding,
                    collection, author, project, doc_type, state, title,
                    file_path, parent_doc_id, workflow_stage, content_hash,
                    doc_created_at
                ) VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    collection = EXCLUDED.collection,
                    author = EXCLUDED.author,
                    project = EXCLUDED.project,
                    doc_type = EXCLUDED.doc_type,
                    state = EXCLUDED.state,
                    title = EXCLUDED.title,
                    file_path = EXCLUDED.file_path,
                    parent_doc_id = EXCLUDED.parent_doc_id,
                    workflow_stage = EXCLUDED.workflow_stage,
                    content_hash = EXCLUDED.content_hash,
                    updated_at = NOW()
            """
            
            # Batch upsert
            count = 0
            for chunk in chunks:
                content_hash = hashlib.sha256(chunk.content.encode()).hexdigest()[:16]
                
                await conn.execute(
                    stmt,
                    chunk.doc_id,
                    chunk.chunk_index,
                    chunk.total_chunks,
                    chunk.content,
                    json.dumps(chunk.embedding) if chunk.embedding else None,
                    collection.value,
                    chunk.metadata.get('author'),
                    chunk.metadata.get('project'),
                    chunk.metadata.get('doc_type'),
                    chunk.metadata.get('state'),
                    chunk.metadata.get('title'),
                    chunk.metadata.get('file_path'),
                    chunk.metadata.get('parent_doc_id'),
                    chunk.metadata.get('workflow_stage'),
                    content_hash,
                    chunk.metadata.get('doc_created_at')
                )
                count += 1
            
            return count
    
    async def delete_document(self, doc_id: str) -> int:
        """Delete all chunks for a document"""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM doc_chunks WHERE doc_id = $1",
                doc_id
            )
            return int(result.split()[-1])
    
    async def search_dense(
        self,
        query_embedding: List[float],
        k: int = 10,
        collection: Optional[Collection] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Dense (semantic) search using vector similarity.
        
        Args:
            query_embedding: Query vector
            k: Number of results
            collection: Filter by collection
            filters: Additional metadata filters
            
        Returns:
            List of search results
        """
        # Build filter conditions
        conditions = []
        params = [json.dumps(query_embedding), k]
        param_idx = 3
        
        if collection:
            conditions.append(f"collection = ${param_idx}")
            params.append(collection.value)
            param_idx += 1
        
        if filters:
            for key, value in filters.items():
                if value is not None:
                    conditions.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
        
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        
        query = f"""
            SELECT 
                id, doc_id, chunk_index, total_chunks, content,
                author, project, doc_type, state, title, file_path,
                parent_doc_id, workflow_stage,
                1 - (embedding <=> $1::vector) AS score
            FROM doc_chunks
            WHERE {where_clause}
                AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        return [
            SearchResult(
                chunk=Chunk(
                    id=str(row['id']),
                    doc_id=row['doc_id'],
                    content=row['content'],
                    chunk_index=row['chunk_index'],
                    total_chunks=row['total_chunks'],
                    metadata={
                        'author': row['author'],
                        'project': row['project'],
                        'doc_type': row['doc_type'],
                        'state': row['state'],
                        'title': row['title'],
                        'file_path': row['file_path'],
                        'parent_doc_id': row['parent_doc_id'],
                        'workflow_stage': row['workflow_stage']
                    }
                ),
                semantic_score=row['score'],
                combined_score=row['score']
            )
            for row in rows
        ]
    
    async def search_sparse(
        self,
        query_text: str,
        k: int = 10,
        collection: Optional[Collection] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Sparse (keyword) search using full-text search.
        
        Args:
            query_text: Search query
            k: Number of results
            collection: Filter by collection
            filters: Additional metadata filters
            
        Returns:
            List of search results with highlights
        """
        # Build filter conditions
        conditions = ["content_tsv @@ plainto_tsquery('english', $1)"]
        params = [query_text, k]
        param_idx = 3
        
        if collection:
            conditions.append(f"collection = ${param_idx}")
            params.append(collection.value)
            param_idx += 1
        
        if filters:
            for key, value in filters.items():
                if value is not None:
                    conditions.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                id, doc_id, chunk_index, total_chunks, content,
                author, project, doc_type, state, title, file_path,
                parent_doc_id, workflow_stage,
                ts_rank(content_tsv, plainto_tsquery('english', $1)) AS score,
                ts_headline('english', content, plainto_tsquery('english', $1),
                    'StartSel=**, StopSel=**, MaxWords=50, MinWords=20') AS highlight
            FROM doc_chunks
            WHERE {where_clause}
            ORDER BY score DESC
            LIMIT $2
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        return [
            SearchResult(
                chunk=Chunk(
                    id=str(row['id']),
                    doc_id=row['doc_id'],
                    content=row['content'],
                    chunk_index=row['chunk_index'],
                    total_chunks=row['total_chunks'],
                    metadata={
                        'author': row['author'],
                        'project': row['project'],
                        'doc_type': row['doc_type'],
                        'state': row['state'],
                        'title': row['title'],
                        'file_path': row['file_path'],
                        'parent_doc_id': row['parent_doc_id'],
                        'workflow_stage': row['workflow_stage']
                    }
                ),
                keyword_score=row['score'],
                combined_score=row['score'],
                highlights=[row['highlight']] if row['highlight'] else []
            )
            for row in rows
        ]
    
    async def search_hybrid(
        self,
        query_text: str,
        query_embedding: List[float],
        k: int = 10,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        collection: Optional[Collection] = None,
        filters: Optional[Dict[str, Any]] = None,
        rrf_k: int = 60
    ) -> List[SearchResult]:
        """
        Hybrid search combining dense and sparse retrieval with RRF fusion.
        
        Args:
            query_text: Text query for keyword search
            query_embedding: Query vector for semantic search
            k: Number of results
            dense_weight: Weight for dense scores (0-1)
            sparse_weight: Weight for sparse scores (0-1)
            collection: Filter by collection
            filters: Additional metadata filters
            rrf_k: RRF constant (higher = more uniform weighting)
            
        Returns:
            Fused search results
        """
        # Build filter conditions
        filter_conditions = []
        filter_params = []
        
        if collection:
            filter_conditions.append("collection = $PARAM")
            filter_params.append(collection.value)
        
        if filters:
            for key, value in filters.items():
                if value is not None:
                    filter_conditions.append(f"{key} = $PARAM")
                    filter_params.append(value)
        
        # Build the hybrid query with RRF
        filter_where = " AND ".join(filter_conditions) if filter_conditions else "TRUE"
        
        # Replace $PARAM with actual parameter positions
        param_idx = 5  # First 4 are: embedding, query_text, k*2, rrf_k
        for i, _ in enumerate(filter_params):
            filter_where = filter_where.replace("$PARAM", f"${param_idx}", 1)
            param_idx += 1
        
        query = f"""
            WITH dense_results AS (
                SELECT 
                    id, doc_id, chunk_index, total_chunks, content,
                    author, project, doc_type, state, title, file_path,
                    parent_doc_id, workflow_stage,
                    1 - (embedding <=> $1::vector) AS semantic_score,
                    ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS rank
                FROM doc_chunks
                WHERE {filter_where}
                    AND embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            ),
            sparse_results AS (
                SELECT 
                    id, doc_id, chunk_index, total_chunks, content,
                    author, project, doc_type, state, title, file_path,
                    parent_doc_id, workflow_stage,
                    ts_rank(content_tsv, plainto_tsquery('english', $2)) AS keyword_score,
                    ts_headline('english', content, plainto_tsquery('english', $2),
                        'StartSel=**, StopSel=**, MaxWords=50') AS highlight,
                    ROW_NUMBER() OVER (ORDER BY ts_rank(content_tsv, plainto_tsquery('english', $2)) DESC) AS rank
                FROM doc_chunks
                WHERE {filter_where}
                    AND content_tsv @@ plainto_tsquery('english', $2)
                ORDER BY keyword_score DESC
                LIMIT $3
            )
            SELECT 
                COALESCE(d.id, s.id) AS id,
                COALESCE(d.doc_id, s.doc_id) AS doc_id,
                COALESCE(d.chunk_index, s.chunk_index) AS chunk_index,
                COALESCE(d.total_chunks, s.total_chunks) AS total_chunks,
                COALESCE(d.content, s.content) AS content,
                COALESCE(d.author, s.author) AS author,
                COALESCE(d.project, s.project) AS project,
                COALESCE(d.doc_type, s.doc_type) AS doc_type,
                COALESCE(d.state, s.state) AS state,
                COALESCE(d.title, s.title) AS title,
                COALESCE(d.file_path, s.file_path) AS file_path,
                COALESCE(d.parent_doc_id, s.parent_doc_id) AS parent_doc_id,
                COALESCE(d.workflow_stage, s.workflow_stage) AS workflow_stage,
                COALESCE(d.semantic_score, 0) AS semantic_score,
                COALESCE(s.keyword_score, 0) AS keyword_score,
                s.highlight,
                -- RRF fusion score
                COALESCE(1.0 / ($4 + d.rank), 0) * {dense_weight} + 
                COALESCE(1.0 / ($4 + s.rank), 0) * {sparse_weight} AS combined_score
            FROM dense_results d
            FULL OUTER JOIN sparse_results s ON d.id = s.id
            ORDER BY combined_score DESC
            LIMIT $3 / 2
        """
        
        params = [
            json.dumps(query_embedding),
            query_text,
            k * 2,  # Over-retrieve for fusion
            rrf_k,
            *filter_params
        ]
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        return [
            SearchResult(
                chunk=Chunk(
                    id=str(row['id']),
                    doc_id=row['doc_id'],
                    content=row['content'],
                    chunk_index=row['chunk_index'],
                    total_chunks=row['total_chunks'],
                    metadata={
                        'author': row['author'],
                        'project': row['project'],
                        'doc_type': row['doc_type'],
                        'state': row['state'],
                        'title': row['title'],
                        'file_path': row['file_path'],
                        'parent_doc_id': row['parent_doc_id'],
                        'workflow_stage': row['workflow_stage']
                    }
                ),
                semantic_score=row['semantic_score'],
                keyword_score=row['keyword_score'],
                combined_score=row['combined_score'],
                highlights=[row['highlight']] if row['highlight'] else []
            )
            for row in rows
        ][:k]
    
    # === Relationship/Graph Queries ===
    
    async def add_relationship(
        self,
        source_doc_id: str,
        target_doc_id: str,
        relationship_type: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Add a relationship between documents"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO doc_relationships (source_doc_id, target_doc_id, relationship_type, metadata)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (source_doc_id, target_doc_id, relationship_type) DO UPDATE
                SET metadata = EXCLUDED.metadata
                """,
                source_doc_id, target_doc_id, relationship_type, 
                json.dumps(metadata or {})
            )
    
    async def get_related_documents(
        self,
        doc_id: str,
        relationship_types: Optional[List[str]] = None,
        direction: str = "outgoing"  # outgoing, incoming, both
    ) -> List[Dict]:
        """Get documents related to a given document"""
        conditions = []
        params = [doc_id]
        
        if direction == "outgoing":
            conditions.append("source_doc_id = $1")
        elif direction == "incoming":
            conditions.append("target_doc_id = $1")
        else:
            conditions.append("(source_doc_id = $1 OR target_doc_id = $1)")
        
        if relationship_types:
            placeholders = ", ".join(f"${i+2}" for i in range(len(relationship_types)))
            conditions.append(f"relationship_type IN ({placeholders})")
            params.extend(relationship_types)
        
        query = f"""
            SELECT 
                r.source_doc_id, r.target_doc_id, r.relationship_type, r.metadata,
                c.title, c.doc_type, c.workflow_stage
            FROM doc_relationships r
            LEFT JOIN doc_chunks c ON (
                CASE WHEN r.source_doc_id = $1 THEN r.target_doc_id ELSE r.source_doc_id END
            ) = c.doc_id AND c.chunk_index = 0
            WHERE {" AND ".join(conditions)}
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        return [
            {
                'source_doc_id': row['source_doc_id'],
                'target_doc_id': row['target_doc_id'],
                'relationship_type': row['relationship_type'],
                'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                'related_doc': {
                    'title': row['title'],
                    'doc_type': row['doc_type'],
                    'workflow_stage': row['workflow_stage']
                }
            }
            for row in rows
        ]
    
    async def get_workflow_chain(
        self,
        doc_id: str,
        direction: str = "both"  # upstream, downstream, both
    ) -> List[Dict]:
        """
        Get the workflow chain for a document.
        E.g., Requirement → PRD → Design → Spec
        """
        # Use recursive CTE to traverse the chain
        query = """
            WITH RECURSIVE chain AS (
                -- Base case: the starting document
                SELECT 
                    doc_id, title, workflow_stage, parent_doc_id, 0 as depth, 'start' as direction
                FROM doc_chunks
                WHERE doc_id = $1 AND chunk_index = 0
                
                UNION ALL
                
                -- Recursive: find parents (upstream)
                SELECT 
                    c.doc_id, c.title, c.workflow_stage, c.parent_doc_id, 
                    ch.depth - 1, 'upstream'
                FROM doc_chunks c
                JOIN chain ch ON c.doc_id = ch.parent_doc_id
                WHERE c.chunk_index = 0
                    AND ($2 = 'upstream' OR $2 = 'both')
                    AND ch.depth > -10
                
                UNION ALL
                
                -- Recursive: find children (downstream)
                SELECT 
                    c.doc_id, c.title, c.workflow_stage, c.parent_doc_id,
                    ch.depth + 1, 'downstream'
                FROM doc_chunks c
                JOIN chain ch ON c.parent_doc_id = ch.doc_id
                WHERE c.chunk_index = 0
                    AND ($2 = 'downstream' OR $2 = 'both')
                    AND ch.depth < 10
            )
            SELECT DISTINCT doc_id, title, workflow_stage, parent_doc_id, depth, direction
            FROM chain
            ORDER BY depth
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, doc_id, direction)
        
        return [
            {
                'doc_id': row['doc_id'],
                'title': row['title'],
                'workflow_stage': row['workflow_stage'],
                'parent_doc_id': row['parent_doc_id'],
                'depth': row['depth'],
                'direction': row['direction']
            }
            for row in rows
        ]
    
    # === Stats and Maintenance ===
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get store statistics"""
        async with self._pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_chunks,
                    COUNT(DISTINCT doc_id) as total_documents,
                    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as embedded_chunks,
                    jsonb_object_agg(collection, cnt) as by_collection
                FROM doc_chunks,
                LATERAL (
                    SELECT collection, COUNT(*) as cnt 
                    FROM doc_chunks 
                    GROUP BY collection
                ) sub
            """)
            
            return {
                'total_chunks': stats['total_chunks'],
                'total_documents': stats['total_documents'],
                'embedded_chunks': stats['embedded_chunks'],
                'by_collection': json.loads(stats['by_collection']) if stats['by_collection'] else {}
            }
