"""Core state management and data structures for DocFlow."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, Enum
from typing import Optional, TypedDict
from pathlib import Path


class AutonomyLevel(IntEnum):
    """RACI-based autonomy levels for automated actions."""
    
    MANUAL = 0          # Human does the work
    SUGGEST = 1         # AI proposes, human approves
    CONFIRM = 2         # AI acts after timeout (unless vetoed)
    NOTIFY = 3          # AI acts, human notified after
    AUTONOMOUS = 4      # AI acts silently


class ReviewStatus(Enum):
    """Status of a document review period."""
    
    OPEN = "open"
    EXTENDED = "extended"
    CLOSED = "closed"
    PROMOTED = "promoted"


class CommentResolution(Enum):
    """Resolution status of a comment."""
    
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"
    DUPLICATE = "duplicate"


@dataclass
class CommentData:
    """Represents a single comment from a document."""
    
    comment_id: str
    author: str
    timestamp: datetime
    text: str
    context: str  # Surrounding text for context
    
    # Location in document
    page_number: Optional[int] = None
    paragraph_index: Optional[int] = None
    
    # Resolution
    resolution: CommentResolution = CommentResolution.UNRESOLVED
    resolution_notes: str = ""
    
    # Tracking
    extracted_at: datetime = field(default_factory=datetime.now)
    incorporated: bool = False
    incorporated_as: Optional[str] = None  # Ref to .md commit hash


@dataclass
class ReviewerResponse:
    """Tracks a single reviewer's response to a review request."""
    
    reviewer: str
    requested_at: datetime
    responded_at: Optional[datetime] = None
    response: Optional[str] = None  # "approved", "needs_revision", "approved_with_changes"
    comments_count: int = 0
    

@dataclass
class ReviewPeriod:
    """Represents a formal review cycle for a document."""
    
    review_id: str
    doc_id: str
    started_at: datetime
    ends_at: datetime
    
    required_reviewers: list[str]  # Must respond
    optional_reviewers: list[str] = field(default_factory=list)  # Nice-to-have
    
    responses: dict[str, ReviewerResponse] = field(default_factory=dict)
    status: ReviewStatus = ReviewStatus.OPEN
    outcome: Optional[str] = None  # "approved", "approved_with_changes", "needs_revision"
    
    # Tracking
    extended_to: Optional[datetime] = None
    promoted_at: Optional[datetime] = None
    promoted_to_commit: Optional[str] = None
    
    # Comments during this review
    draft_comments: list[CommentData] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        """Check if review deadline has passed."""
        effective_deadline = self.extended_to or self.ends_at
        return datetime.now() > effective_deadline
    
    def all_required_responded(self) -> bool:
        """Check if all required reviewers have responded."""
        return all(
            reviewer in self.responses
            for reviewer in self.required_reviewers
        )


@dataclass
class PublicationRecord:
    """Records when and where a document was published."""
    
    version: str  # e.g., "1.0", "1.1", "2.0"
    published_at: datetime
    published_by: str
    
    # Location
    local_path: Optional[str] = None  # Path to generated .docx
    storage_url: Optional[str] = None  # OneDrive / Google Drive URL
    storage_provider: str = "onedrive"
    storage_file_id: Optional[str] = None
    
    # Source
    source_commit: str = ""  # Git commit SHA
    source_file_path: str = ""  # docs/prd/foo.md
    
    # Metadata
    page_count: int = 0
    file_size: int = 0
    
    # Feedback
    comments: list[CommentData] = field(default_factory=list)
    last_comment_at: Optional[datetime] = None


@dataclass
class DocumentState:
    """Complete state of a single document in the DocFlow system."""
    
    doc_id: str
    source_path: str  # Relative path: docs/prd/foo.md
    
    # Publication history
    published_record: Optional[PublicationRecord] = None
    draft_record: Optional[PublicationRecord] = None  # Current draft if in review
    archived_records: list[PublicationRecord] = field(default_factory=list)
    
    # Review
    active_review: Optional[ReviewPeriod] = None
    review_history: list[ReviewPeriod] = field(default_factory=list)
    
    # Feedback
    pending_comments: list[CommentData] = field(default_factory=list)
    
    # Git tracking
    current_branch: str = ""
    current_commit: str = ""
    last_published_commit: Optional[str] = None
    
    # Settings
    approval_required: bool = True
    auto_republish: bool = False
    stakeholders: list[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_sync_at: Optional[datetime] = None
    
    def is_published(self) -> bool:
        """Check if document has been published at least once."""
        return self.published_record is not None
    
    def is_in_review(self) -> bool:
        """Check if document is currently in draft review."""
        return self.active_review is not None and self.active_review.status == ReviewStatus.OPEN
    
    def has_pending_feedback(self) -> bool:
        """Check if there are unincorporated comments."""
        return any(
            not comment.incorporated
            for comment in self.pending_comments
        )


class WorkflowStateDict(TypedDict, total=False):
    """Type hint for workflow state dictionary (serializable)."""
    
    documents: dict[str, DocumentState]
    git_context: dict
    last_poll: str  # ISO datetime
    pending_actions: dict[str, dict]


@dataclass
class WorkflowState:
    """Complete workflow state, serializable to JSON/YAML."""
    
    documents: dict[str, DocumentState] = field(default_factory=dict)
    
    # Git tracking
    current_branch: str = ""
    current_commit: str = ""
    git_root: Path = field(default_factory=Path.cwd)
    
    # Polling/scheduling
    last_poll: Optional[datetime] = None
    last_poll_error: Optional[str] = None
    
    # Pending actions (need human approval)
    pending_actions: dict[str, dict] = field(default_factory=dict)
    
    # Timestamps
    initialized_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def mark_updated(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()
    
    def get_document(self, doc_id: str) -> Optional[DocumentState]:
        """Retrieve a document state by ID."""
        return self.documents.get(doc_id)
    
    def add_document(self, doc_state: DocumentState) -> None:
        """Register a new document."""
        self.documents[doc_state.doc_id] = doc_state
        self.mark_updated()
