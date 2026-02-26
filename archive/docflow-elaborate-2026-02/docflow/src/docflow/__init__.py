"""DocFlow: Document Lifecycle Management System.

Treats markdown files as source code and published Word documents as deployment artifacts.
"""

__version__ = "0.1.0a1"

from .core import (
    DocumentState,
    WorkflowState,
    PublicationRecord,
    ReviewPeriod,
    ReviewerResponse,
    ReviewStatus,
    AutonomyLevel,
    CommentData,
    Config,
    load_config,
    save_config,
    LinkRegistry,
    GitContext,
)
from .providers import (
    StorageProvider,
    NotificationProvider,
    EmbeddingProvider,
    LLMProvider,
    get_storage_provider,
    get_notification_provider,
    get_embedding_provider,
    get_llm_provider,
)

__all__ = [
    "__version__",
    "DocumentState",
    "WorkflowState",
    "PublicationRecord",
    "ReviewPeriod",
    "ReviewerResponse",
    "ReviewStatus",
    "AutonomyLevel",
    "CommentData",
    "Config",
    "load_config",
    "save_config",
    "LinkRegistry",
    "GitContext",
    "StorageProvider",
    "NotificationProvider",
    "EmbeddingProvider",
    "LLMProvider",
    "get_storage_provider",
    "get_notification_provider",
    "get_embedding_provider",
    "get_llm_provider",
]
