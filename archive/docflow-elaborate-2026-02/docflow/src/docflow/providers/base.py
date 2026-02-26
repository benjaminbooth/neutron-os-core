"""Abstract base classes for provider implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional, TypedDict
import enum


class SharePermission(enum.Enum):
    """Permission level for shared documents."""
    
    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"


class ShareScope(enum.Enum):
    """Scope of document sharing."""
    
    LINK = "link"  # Anyone with link
    PEOPLE = "people"  # Specific people only
    DOMAIN = "domain"  # Entire domain/organization


class CommentData(TypedDict, total=False):
    """Comment metadata extracted from document."""
    
    comment_id: str
    author: str
    author_email: str
    timestamp: str  # ISO format
    text: str
    context: str
    resolved: bool


@dataclass
class UploadResult:
    """Result of uploading a file to storage."""
    
    success: bool
    file_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    file_size: int = 0


class StorageProvider(ABC):
    """Abstract base class for document storage implementations."""
    
    @abstractmethod
    def upload(self, file_path: Path, destination_path: str) -> UploadResult:
        """Upload a local file to cloud storage.
        
        Args:
            file_path: Path to local .docx file
            destination_path: Target path in storage (e.g., /Documents/foo.docx)
        
        Returns:
            UploadResult with file_id and public URL
        """
        pass
    
    @abstractmethod
    def download(self, file_id: str, dest_path: Path) -> bool:
        """Download a file from cloud storage.
        
        Args:
            file_id: Cloud storage file ID
            dest_path: Local destination path
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_comments(self, file_id: str) -> list[CommentData]:
        """Retrieve all comments on a document.
        
        Args:
            file_id: Cloud storage file ID
        
        Returns:
            List of comments with metadata
        """
        pass
    
    @abstractmethod
    def create_share_link(self, file_id: str, scope: ShareScope = ShareScope.LINK,
                         permission: SharePermission = SharePermission.VIEW) -> str:
        """Create a shareable link to a document.
        
        Args:
            file_id: Cloud storage file ID
            scope: Who can access
            permission: What permissions they have
        
        Returns:
            Public URL to document
        """
        pass
    
    @abstractmethod
    def move(self, file_id: str, new_path: str) -> bool:
        """Move a file to a new location in storage.
        
        Args:
            file_id: Cloud storage file ID
            new_path: Target path
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def delete(self, file_id: str) -> bool:
        """Delete a file from storage.
        
        Args:
            file_id: Cloud storage file ID
        
        Returns:
            True if successful
        """
        pass


class NotificationProvider(ABC):
    """Abstract base class for notification implementations."""
    
    @abstractmethod
    def send_email(self, to: str | list[str], subject: str, body: str,
                   html: Optional[str] = None) -> bool:
        """Send an email notification.
        
        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Plain text body
            html: Optional HTML version
        
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    def send_teams_message(self, channel: str, message: str, card_json: Optional[dict] = None) -> bool:
        """Send a message to a Teams channel.
        
        Args:
            channel: Teams channel ID or name
            message: Message text
            card_json: Optional Adaptive Card JSON
        
        Returns:
            True if sent successfully
        """
        pass
    
    def notify_review_started(self, doc_id: str, deadline: datetime, reviewers: list[str]) -> bool:
        """Notify reviewers that a review period has started."""
        subject = f"Document Review Started: {doc_id}"
        body = f"You've been added as a reviewer for {doc_id}.\n"
        body += f"Review deadline: {deadline.strftime('%Y-%m-%d %H:%M')}\n"
        return self.send_email(reviewers, subject, body)
    
    def notify_review_reminder(self, doc_id: str, deadline: datetime, reviewers: list[str]) -> bool:
        """Send a reminder about an upcoming review deadline."""
        subject = f"Review Reminder: {doc_id}"
        body = f"Reminder: {doc_id} review deadline is approaching.\n"
        body += f"Deadline: {deadline.strftime('%Y-%m-%d %H:%M')}\n"
        return self.send_email(reviewers, subject, body)
    
    def notify_draft_published(self, doc_id: str, draft_url: str, reviewer_count: int) -> bool:
        """Notify that a draft has been published for review."""
        subject = f"Draft Available for Review: {doc_id}"
        body = f"A new draft of {doc_id} is ready for review.\n"
        body += f"View it here: {draft_url}\n"
        body += f"Reviewers: {reviewer_count}\n"
        return self.send_email("", subject, body)  # Reviewer list set elsewhere


class EmbeddingProvider(ABC):
    """Abstract base class for document embedding implementations."""
    
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple text chunks.
        
        Args:
            texts: List of text strings to embed
        
        Returns:
            List of embedding vectors (same length as texts)
        """
        pass
    
    @abstractmethod
    def store(self, texts: list[str], embeddings: list[list[float]],
              metadata: list[dict]) -> bool:
        """Store embeddings and metadata in the vector database.
        
        Args:
            texts: Text chunks (for reference)
            embeddings: Corresponding embeddings
            metadata: Per-chunk metadata (doc_id, page, version, etc.)
        
        Returns:
            True if stored successfully
        """
        pass
    
    @abstractmethod
    def search(self, query: str, k: int = 10, filters: Optional[dict] = None) -> list[dict]:
        """Semantic search for relevant text chunks.
        
        Args:
            query: Search query
            k: Number of results to return
            filters: Optional metadata filters
        
        Returns:
            List of results with text, score, metadata
        """
        pass
    
    @abstractmethod
    def delete_by_doc_id(self, doc_id: str) -> bool:
        """Remove all embeddings for a document (used when re-embedding).
        
        Args:
            doc_id: Document to remove
        
        Returns:
            True if successful
        """
        pass


class LLMProvider(ABC):
    """Abstract base class for LLM implementations."""
    
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        """Generate a text completion for the given prompt.
        
        Args:
            prompt: Input prompt
            **kwargs: Model-specific parameters (temperature, max_tokens, etc.)
        
        Returns:
            Generated text
        """
        pass
    
    @abstractmethod
    def complete_structured(self, prompt: str, schema: dict, **kwargs) -> dict:
        """Generate a structured output matching the given schema.
        
        Args:
            prompt: Input prompt
            schema: JSON schema for output
            **kwargs: Model-specific parameters
        
        Returns:
            Structured output as dictionary
        """
        pass
    
    def categorize_comments(self, comments: list[str]) -> dict[str, list[str]]:
        """Categorize comments into actionable, informational, approval."""
        prompt = f"""Categorize the following comments into three categories:
1. Actionable (requires changes)
2. Informational (context, not changes)
3. Approval (positive feedback)

Comments:
{chr(10).join('- ' + c for c in comments)}

Respond with a JSON dict: {{"actionable": [...], "informational": [...], "approval": [...]}}"""
        
        result = self.complete_structured(prompt, {
            "type": "object",
            "properties": {
                "actionable": {"type": "array", "items": {"type": "string"}},
                "informational": {"type": "array", "items": {"type": "string"}},
                "approval": {"type": "array", "items": {"type": "string"}},
            }
        })
        return result
    
    def extract_action_items(self, text: str) -> list[str]:
        """Extract action items from meeting transcript or comment."""
        prompt = f"""Extract all action items from the following text.
List them as bullet points (one per line), concise, with owner if mentioned.

{text}"""
        
        response = self.complete(prompt)
        return [line.strip() for line in response.strip().split("\n") if line.strip().startswith("-")]
    
    def match_doc_to_content(self, doc_id: str, doc_title: str,
                             meeting_content: str) -> tuple[float, str]:
        """Rate relevance of a meeting to a document.
        
        Returns:
            (confidence_score: 0-1, reasoning: str)
        """
        prompt = f"""Given a document '{doc_id}' (title: {doc_title}), how relevant is the following meeting content?
Rate on a scale of 0-1 (0=not relevant, 1=highly relevant).
Explain your reasoning.

Meeting content:
{meeting_content[:1000]}...

Respond with JSON: {{"score": <float>, "reasoning": "<string>"}}"""
        
        result = self.complete_structured(prompt, {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 1},
                "reasoning": {"type": "string"},
            }
        })
        return result.get("score", 0.0), result.get("reasoning", "")
