"""Factory functions for provider instantiation."""

from typing import Optional, Type
from .base import StorageProvider, NotificationProvider, EmbeddingProvider, LLMProvider
from ..core import Config


# Provider registries
_storage_providers: dict[str, Type[StorageProvider]] = {}
_notification_providers: dict[str, Type[NotificationProvider]] = {}
_embedding_providers: dict[str, Type[EmbeddingProvider]] = {}
_llm_providers: dict[str, Type[LLMProvider]] = {}


def register_storage_provider(name: str, provider_class: Type[StorageProvider]) -> None:
    """Register a storage provider implementation."""
    _storage_providers[name] = provider_class


def register_notification_provider(name: str, provider_class: Type[NotificationProvider]) -> None:
    """Register a notification provider implementation."""
    _notification_providers[name] = provider_class


def register_embedding_provider(name: str, provider_class: Type[EmbeddingProvider]) -> None:
    """Register an embedding provider implementation."""
    _embedding_providers[name] = provider_class


def register_llm_provider(name: str, provider_class: Type[LLMProvider]) -> None:
    """Register an LLM provider implementation."""
    _llm_providers[name] = provider_class


def get_storage_provider(config: Config) -> StorageProvider:
    """Get a configured storage provider instance."""
    provider_name = config.storage.provider.lower()
    
    if provider_name not in _storage_providers:
        raise ValueError(f"Unknown storage provider: {provider_name}")
    
    provider_class = _storage_providers[provider_name]
    return provider_class(config.storage)


def get_notification_provider(config: Config) -> NotificationProvider:
    """Get a configured notification provider instance."""
    provider_name = config.notifications.provider.lower()
    
    if provider_name not in _notification_providers:
        raise ValueError(f"Unknown notification provider: {provider_name}")
    
    provider_class = _notification_providers[provider_name]
    return provider_class(config.notifications)


def get_embedding_provider(config: Config) -> Optional[EmbeddingProvider]:
    """Get a configured embedding provider instance."""
    if not config.embedding.enabled:
        return None
    
    provider_name = config.embedding.provider.lower()
    
    if provider_name not in _embedding_providers:
        raise ValueError(f"Unknown embedding provider: {provider_name}")
    
    provider_class = _embedding_providers[provider_name]
    return provider_class(config.embedding)


def get_llm_provider(config: Config) -> LLMProvider:
    """Get a configured LLM provider instance."""
    provider_name = config.llm.provider.lower()
    
    if provider_name not in _llm_providers:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
    
    provider_class = _llm_providers[provider_name]
    return provider_class(config.llm)
