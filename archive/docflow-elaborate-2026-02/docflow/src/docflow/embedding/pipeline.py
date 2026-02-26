"""RAG embedding pipeline for document indexing."""

import logging
from pathlib import Path
from typing import Optional
import hashlib

from ..providers import EmbeddingProvider
from ..core import DocumentState

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Chunk documents intelligently for embedding."""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        """Initialize chunker.
        
        Args:
            chunk_size: Target characters per chunk
            overlap: Character overlap between chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_by_sections(self, markdown_content: str) -> list[dict]:
        """Chunk markdown by sections (headers).
        
        Preserves document structure, chunks at header boundaries.
        
        Args:
            markdown_content: Full markdown text
        
        Returns:
            List of chunks with metadata:
            - text: Chunk content
            - section: Header/section name
            - level: Header level (1-6)
            - index: Chunk number
        """
        chunks = []
        current_section = "Introduction"
        current_level = 0
        buffer = []
        
        for line in markdown_content.split("\n"):
            # Check for headers
            if line.startswith("#"):
                # Flush buffer if it has content
                if buffer:
                    chunk_text = "\n".join(buffer)
                    if len(chunk_text.strip()) > 10:  # Skip tiny chunks
                        chunks.append({
                            "text": chunk_text,
                            "section": current_section,
                            "level": current_level,
                            "index": len(chunks),
                        })
                    buffer = []
                
                # Parse new header
                level = len(line) - len(line.lstrip("#"))
                current_level = level
                current_section = line.lstrip("#").strip()
                buffer.append(line)
            else:
                buffer.append(line)
                
                # Split long buffers
                if len("\n".join(buffer)) > self.chunk_size:
                    chunk_text = "\n".join(buffer)
                    if len(chunk_text.strip()) > 10:
                        chunks.append({
                            "text": chunk_text,
                            "section": current_section,
                            "level": current_level,
                            "index": len(chunks),
                        })
                    buffer = []
        
        # Flush remaining buffer
        if buffer:
            chunk_text = "\n".join(buffer)
            if len(chunk_text.strip()) > 10:
                chunks.append({
                    "text": chunk_text,
                    "section": current_section,
                    "level": current_level,
                    "index": len(chunks),
                })
        
        return chunks


class EmbeddingPipeline:
    """Pipeline for embedding documents into vector store."""
    
    def __init__(self, embedding_provider: Optional[EmbeddingProvider]):
        """Initialize embedding pipeline.
        
        Args:
            embedding_provider: Provider for generating and storing embeddings
        """
        self.provider = embedding_provider
        self.chunker = DocumentChunker()
    
    def embed_document(self, doc_state: DocumentState, markdown_content: str,
                      metadata: Optional[dict] = None) -> bool:
        """Embed a document and store vectors.
        
        Args:
            doc_state: Document state
            markdown_content: Markdown content to embed
            metadata: Additional metadata (version, branch, etc.)
        
        Returns:
            True if successful
        """
        if not self.provider:
            logger.debug("Embedding disabled")
            return True
        
        try:
            # Chunk document
            chunks = self.chunker.chunk_by_sections(markdown_content)
            
            if not chunks:
                logger.warning(f"No chunks to embed for {doc_state.doc_id}")
                return True
            
            # Extract text for embedding
            texts = [chunk["text"] for chunk in chunks]
            
            # Generate embeddings
            embeddings = self.provider.embed_texts(texts)
            
            # Build metadata for each chunk
            chunk_metadata = []
            for i, chunk in enumerate(chunks):
                meta = {
                    "doc_id": doc_state.doc_id,
                    "source_file": doc_state.source_path,
                    "section": chunk["section"],
                    "level": chunk["level"],
                    "index": chunk["index"],
                    **(metadata or {})
                }
                chunk_metadata.append(meta)
            
            # Store embeddings
            success = self.provider.store(texts, embeddings, chunk_metadata)
            
            if success:
                logger.info(f"Embedded {len(texts)} chunks from {doc_state.doc_id}")
            else:
                logger.error(f"Failed to store embeddings for {doc_state.doc_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Embedding pipeline error: {e}")
            return False
    
    def re_embed_document(self, doc_id: str, markdown_content: str,
                         metadata: Optional[dict] = None) -> bool:
        """Re-embed a document (removes old embeddings first).
        
        Args:
            doc_id: Document ID
            markdown_content: Updated markdown content
            metadata: Additional metadata
        
        Returns:
            True if successful
        """
        if not self.provider:
            return True
        
        try:
            # Delete old embeddings
            self.provider.delete_by_doc_id(doc_id)
            
            # Create temp document state for embedding
            temp_state = DocumentState(
                doc_id=doc_id,
                source_path=f"docs/{doc_id}.md",
            )
            
            # Re-embed
            return self.embed_document(temp_state, markdown_content, metadata)
        
        except Exception as e:
            logger.error(f"Re-embedding failed: {e}")
            return False
    
    def search(self, query: str, k: int = 10, filters: Optional[dict] = None) -> list[dict]:
        """Search for relevant document sections.
        
        Args:
            query: Search query
            k: Number of results
            filters: Optional filters (e.g., doc_id, section)
        
        Returns:
            List of results with text, score, metadata
        """
        if not self.provider:
            return []
        
        try:
            results = self.provider.search(query, k=k, filters=filters)
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
