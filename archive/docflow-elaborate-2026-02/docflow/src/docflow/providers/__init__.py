"""Provider pattern for extensible storage, notification, embedding, and LLM backends."""

from .base import (
    StorageProvider,
    NotificationProvider,
    EmbeddingProvider,
    LLMProvider,
    UploadResult,
    CommentData,
)
from .factory import (
    get_storage_provider,
    get_notification_provider,
    get_embedding_provider,
    get_llm_provider,
)

__all__ = [
    "StorageProvider",
    "NotificationProvider",
    "EmbeddingProvider",
    "LLMProvider",
    "UploadResult",
    "CommentData",
    "get_storage_provider",
    "get_notification_provider",
    "get_embedding_provider",
    "get_llm_provider",
]
