"""Configuration management for DocFlow."""

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
import yaml


@dataclass
class GitConfig:
    """Git-related configuration."""
    
    publish_branches: list[str] = field(default_factory=lambda: ["main", "release/*"])
    draft_branches: list[str] = field(default_factory=lambda: ["feature/*", "dev"])
    require_clean: bool = True
    require_pushed: bool = True


@dataclass
class StorageConfig:
    """Storage provider configuration."""
    
    provider: str = "onedrive"  # onedrive, google, local
    
    # OneDrive settings
    onedrive_client_id: Optional[str] = None
    onedrive_client_secret: Optional[str] = None
    onedrive_tenant_id: Optional[str] = None
    onedrive_draft_folder: str = "/Documents/Drafts/"
    onedrive_published_folder: str = "/Documents/Published/"
    onedrive_archive_folder: str = "/Documents/Published/Archive/"
    
    # Google Drive settings
    google_service_account_json: Optional[str] = None
    google_draft_folder_id: Optional[str] = None
    google_published_folder_id: Optional[str] = None
    
    # Local filesystem (testing)
    local_root: Optional[str] = None
    
    def __post_init__(self):
        """Expand environment variables in secrets."""
        if self.onedrive_client_id and "$" in self.onedrive_client_id:
            self.onedrive_client_id = os.path.expandvars(self.onedrive_client_id)
        if self.onedrive_client_secret and "$" in self.onedrive_client_secret:
            self.onedrive_client_secret = os.path.expandvars(self.onedrive_client_secret)
        if self.onedrive_tenant_id and "$" in self.onedrive_tenant_id:
            self.onedrive_tenant_id = os.path.expandvars(self.onedrive_tenant_id)


@dataclass
class NotificationConfig:
    """Notification provider configuration."""
    
    provider: str = "smtp"  # smtp, sendgrid, teams
    
    # SMTP
    smtp_host: str = "smtp.utexas.edu"
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_address: str = "docflow@utexas.edu"
    
    # Teams
    teams_webhook_url: Optional[str] = None
    
    # Sendgrid
    sendgrid_api_key: Optional[str] = None


@dataclass
class ReviewConfig:
    """Review period configuration."""
    
    default_review_days: int = 7
    auto_extend_on_request: bool = True
    remind_days_before: list[int] = field(default_factory=lambda: [3, 1])


@dataclass
class EmbeddingConfig:
    """Embedding/RAG configuration."""
    
    enabled: bool = True
    provider: str = "chromadb"  # chromadb, pinecone, pgvector
    collection_name: str = "neutron_os_docs"
    
    # ChromaDB
    chromadb_path: Optional[str] = None
    
    # Pinecone
    pinecone_api_key: Optional[str] = None
    pinecone_environment: str = "production"
    
    # pgvector (PostgreSQL)
    pgvector_connection_string: Optional[str] = None
    
    # Embedding model
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    batch_size: int = 10


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    
    provider: str = "anthropic"  # anthropic, openai
    model: str = "claude-3-5-haiku-20241022"
    
    # Anthropic
    anthropic_api_key: Optional[str] = None
    
    # OpenAI
    openai_api_key: Optional[str] = None
    
    # Settings
    temperature: float = 0.3
    max_tokens: int = 2048


@dataclass
class AutonomyConfig:
    """Autonomy level defaults per action."""
    
    default_level: str = "suggest"  # manual, suggest, confirm, notify, autonomous
    
    # Per-action overrides
    actions: dict[str, str] = field(default_factory=lambda: {
        "poll_for_comments": "autonomous",
        "fetch_comments": "autonomous",
        "analyze_feedback": "notify",
        "update_source_file": "suggest",
        "republish_approved_doc": "confirm",
        "republish_new_doc": "suggest",
        "promote_draft": "suggest",
        "archive_version": "notify",
    })


@dataclass
class Config:
    """Complete DocFlow configuration."""
    
    git: GitConfig = field(default_factory=GitConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    autonomy: AutonomyConfig = field(default_factory=AutonomyConfig)
    
    # Polling
    poll_interval_seconds: int = 900  # 15 minutes
    
    # Paths
    docs_root: Path = field(default_factory=lambda: Path("docs"))
    state_file: Path = field(default_factory=lambda: Path(".docflow/state.db"))
    registry_file: Path = field(default_factory=lambda: Path(".doc-registry.json"))
    
    # Logging
    log_level: str = "INFO"
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()
        
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        
        return cls._from_dict(data)
    
    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Recursively construct Config from nested dict."""
        config = cls()
        
        if "git" in data:
            config.git = GitConfig(**{k: v for k, v in data["git"].items() 
                                     if k in GitConfig.__dataclass_fields__})
        
        if "storage" in data:
            config.storage = StorageConfig(**{k: v for k, v in data["storage"].items() 
                                             if k in StorageConfig.__dataclass_fields__})
        
        if "notifications" in data:
            config.notifications = NotificationConfig(**{k: v for k, v in data["notifications"].items() 
                                                        if k in NotificationConfig.__dataclass_fields__})
        
        if "review" in data:
            config.review = ReviewConfig(**{k: v for k, v in data["review"].items() 
                                           if k in ReviewConfig.__dataclass_fields__})
        
        if "embedding" in data:
            config.embedding = EmbeddingConfig(**{k: v for k, v in data["embedding"].items() 
                                                 if k in EmbeddingConfig.__dataclass_fields__})
        
        if "llm" in data:
            config.llm = LLMConfig(**{k: v for k, v in data["llm"].items() 
                                     if k in LLMConfig.__dataclass_fields__})
        
        if "autonomy" in data:
            autonomy_data = data["autonomy"]
            config.autonomy = AutonomyConfig(
                default_level=autonomy_data.get("default_level", "suggest"),
                actions={**config.autonomy.actions, **(autonomy_data.get("actions", {}))}
            )
        
        if "poll_interval_seconds" in data:
            config.poll_interval_seconds = data["poll_interval_seconds"]
        
        if "docs_root" in data:
            config.docs_root = Path(data["docs_root"])
        
        if "state_file" in data:
            config.state_file = Path(data["state_file"])
        
        if "registry_file" in data:
            config.registry_file = Path(data["registry_file"])
        
        if "log_level" in data:
            config.log_level = data["log_level"]
        
        return config
    
    def to_yaml(self) -> str:
        """Convert configuration to YAML string."""
        data = {
            "git": asdict(self.git),
            "storage": asdict(self.storage),
            "notifications": asdict(self.notifications),
            "review": asdict(self.review),
            "embedding": asdict(self.embedding),
            "llm": asdict(self.llm),
            "autonomy": asdict(self.autonomy),
            "poll_interval_seconds": self.poll_interval_seconds,
            "docs_root": str(self.docs_root),
            "state_file": str(self.state_file),
            "registry_file": str(self.registry_file),
            "log_level": self.log_level,
        }
        return yaml.dump(data, default_flow_style=False)


def load_config(path: Optional[Path] = None) -> Config:
    """Load DocFlow configuration from file or return defaults."""
    if path is None:
        path = Path.cwd() / ".doc-workflow.yaml"
    
    return Config.from_yaml(path)


def save_config(config: Config, path: Optional[Path] = None) -> None:
    """Save DocFlow configuration to file."""
    if path is None:
        path = Path.cwd() / ".doc-workflow.yaml"
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(config.to_yaml())
