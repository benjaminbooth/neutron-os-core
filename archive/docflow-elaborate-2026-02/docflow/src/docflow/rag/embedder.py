"""
Embedding pipeline for DocFlow RAG

Supports local embeddings via vLLM/Ollama or cloud fallback.
"""
import asyncio
import hashlib
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import httpx

from ..core.config import get_config


@dataclass
class EmbeddingConfig:
    """Configuration for embedding models"""
    model: str = "nomic-embed-text-v1.5"
    base_url: str = "http://localhost:8001/v1"
    dimensions: int = 768
    batch_size: int = 32
    max_retries: int = 3
    timeout: float = 30.0
    
    # Fallback to cloud if local unavailable
    fallback_provider: Optional[str] = None  # "openai", "voyage"
    fallback_api_key: Optional[str] = None


class EmbeddingCache:
    """Simple in-memory cache for embeddings"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._cache: Dict[str, List[float]] = {}
        self._access_order: List[str] = []
    
    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:32]
    
    def get(self, text: str) -> Optional[List[float]]:
        key = self._hash_text(text)
        if key in self._cache:
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None
    
    def set(self, text: str, embedding: List[float]) -> None:
        key = self._hash_text(text)
        
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        
        self._cache[key] = embedding
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def clear(self) -> None:
        self._cache.clear()
        self._access_order.clear()


class Embedder:
    """
    Embedding client supporting local and cloud models.
    
    Usage:
        embedder = Embedder(config)
        
        # Single embedding
        vector = await embedder.embed("Hello world")
        
        # Batch embedding
        vectors = await embedder.embed_batch(["Hello", "World"])
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
        self._cache = EmbeddingCache()
        self._local_available: Optional[bool] = None
    
    async def close(self) -> None:
        await self._client.aclose()
    
    async def _check_local_available(self) -> bool:
        """Check if local embedding server is available"""
        if self._local_available is not None:
            return self._local_available
        
        try:
            response = await self._client.get(
                f"{self.config.base_url}/models",
                timeout=5.0
            )
            self._local_available = response.status_code == 200
        except Exception:
            self._local_available = False
        
        return self._local_available
    
    async def embed(self, text: str) -> List[float]:
        """Embed a single text"""
        # Check cache first
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        
        # Embed
        results = await self.embed_batch([text])
        return results[0]
    
    async def embed_batch(
        self,
        texts: List[str],
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        Embed a batch of texts.
        
        Automatically batches requests to respect model limits.
        """
        if not texts:
            return []
        
        # Check cache and find texts that need embedding
        results = [None] * len(texts)
        to_embed = []
        to_embed_indices = []
        
        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                results[i] = cached
            else:
                to_embed.append(text)
                to_embed_indices.append(i)
        
        if not to_embed:
            return results
        
        # Embed in batches
        batch_size = self.config.batch_size
        embeddings = []
        
        for batch_start in range(0, len(to_embed), batch_size):
            batch = to_embed[batch_start:batch_start + batch_size]
            batch_embeddings = await self._embed_batch_internal(batch)
            embeddings.extend(batch_embeddings)
            
            if show_progress:
                print(f"Embedded {min(batch_start + batch_size, len(to_embed))}/{len(to_embed)}")
        
        # Fill in results and cache
        for i, idx in enumerate(to_embed_indices):
            results[idx] = embeddings[i]
            self._cache.set(to_embed[i], embeddings[i])
        
        return results
    
    async def _embed_batch_internal(self, texts: List[str]) -> List[List[float]]:
        """Internal batch embedding with retry logic"""
        # Try local first
        if await self._check_local_available():
            try:
                return await self._embed_local(texts)
            except Exception as e:
                print(f"Local embedding failed: {e}, trying fallback...")
                self._local_available = False
        
        # Fallback to cloud
        if self.config.fallback_provider:
            return await self._embed_cloud(texts)
        
        raise RuntimeError(
            "Local embedding unavailable and no fallback configured. "
            f"Start local server at {self.config.base_url} or configure fallback."
        )
    
    async def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Embed using local vLLM/Ollama server"""
        # OpenAI-compatible API
        response = await self._client.post(
            f"{self.config.base_url}/embeddings",
            json={
                "model": self.config.model,
                "input": texts,
                "encoding_format": "float"
            }
        )
        response.raise_for_status()
        
        data = response.json()
        # Sort by index to ensure order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]
    
    async def _embed_cloud(self, texts: List[str]) -> List[List[float]]:
        """Embed using cloud provider (OpenAI, Voyage, etc.)"""
        if self.config.fallback_provider == "openai":
            return await self._embed_openai(texts)
        elif self.config.fallback_provider == "voyage":
            return await self._embed_voyage(texts)
        else:
            raise ValueError(f"Unknown fallback provider: {self.config.fallback_provider}")
    
    async def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Embed using OpenAI API"""
        response = await self._client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.config.fallback_api_key}"},
            json={
                "model": "text-embedding-3-small",
                "input": texts
            }
        )
        response.raise_for_status()
        
        data = response.json()
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]
    
    async def _embed_voyage(self, texts: List[str]) -> List[List[float]]:
        """Embed using Voyage AI API"""
        response = await self._client.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.config.fallback_api_key}"},
            json={
                "model": "voyage-2",
                "input": texts
            }
        )
        response.raise_for_status()
        
        data = response.json()
        return [item["embedding"] for item in data["data"]]


class CodeEmbedder(Embedder):
    """
    Specialized embedder for code content.
    
    Uses jina-embeddings-v3 or similar code-optimized model.
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        code_config = config or EmbeddingConfig(
            model="jina-embeddings-v3",
            dimensions=1024,
            base_url="http://localhost:8001/v1"
        )
        super().__init__(code_config)
    
    async def embed_code(
        self,
        code: str,
        language: Optional[str] = None,
        context: Optional[str] = None
    ) -> List[float]:
        """
        Embed code with optional language and context hints.
        """
        # Prepend language hint if provided
        if language:
            code = f"# Language: {language}\n{code}"
        
        # Add context (like surrounding code or docstring)
        if context:
            code = f"{context}\n\n{code}"
        
        return await self.embed(code)
