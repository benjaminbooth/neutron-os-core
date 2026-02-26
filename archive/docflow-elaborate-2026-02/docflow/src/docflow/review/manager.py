"""Review period management and feedback workflow."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..core import (
    DocumentState,
    ReviewPeriod,
    ReviewStatus,
    ReviewerResponse,
    CommentData,
    CommentResolution,
)
from ..providers import StorageProvider, NotificationProvider

logger = logging.getLogger(__name__)


class ReviewManager:
    """Manages document review cycles and feedback tracking."""
    
    def __init__(self, storage: StorageProvider, notifications: NotificationProvider):
        """Initialize review manager with storage and notification providers."""
        self.storage = storage
        self.notifications = notifications
    
    def start_review(self, doc_state: DocumentState, reviewers: list[str],
                    required_count: Optional[int] = None,
                    days: int = 7) -> ReviewPeriod:
        """Start a new review period for a document.
        
        Args:
            doc_state: Document being reviewed
            reviewers: List of reviewers to invite
            required_count: How many must respond (default: all)
            days: Review duration (default: 7)
        
        Returns:
            ReviewPeriod object
        """
        now = datetime.now()
        deadline = now + timedelta(days=days)
        
        required_reviewers = reviewers[:required_count] if required_count else reviewers
        optional_reviewers = reviewers[required_count:] if required_count else []
        
        review = ReviewPeriod(
            review_id=f"{doc_state.doc_id}-{now.isoformat()}",
            doc_id=doc_state.doc_id,
            started_at=now,
            ends_at=deadline,
            required_reviewers=required_reviewers,
            optional_reviewers=optional_reviewers,
        )
        
        # Update document state
        doc_state.active_review = review
        
        # Send notifications
        self._notify_review_started(review)
        
        logger.info(f"Started review for {doc_state.doc_id}: {review.review_id}")
        return review
    
    def extend_review(self, review: ReviewPeriod, additional_days: int = 3) -> bool:
        """Extend a review period deadline.
        
        Args:
            review: ReviewPeriod to extend
            additional_days: Additional days to add
        
        Returns:
            True if extended successfully
        """
        if review.status != ReviewStatus.OPEN:
            logger.warning(f"Cannot extend closed review: {review.review_id}")
            return False
        
        old_deadline = review.extended_to or review.ends_at
        new_deadline = old_deadline + timedelta(days=additional_days)
        review.extended_to = new_deadline
        
        logger.info(f"Extended review {review.review_id} to {new_deadline}")
        return True
    
    def fetch_draft_comments(self, review: ReviewPeriod, file_id: str) -> list[CommentData]:
        """Fetch comments from the draft document.
        
        Args:
            review: ReviewPeriod
            file_id: OneDrive file ID of draft
        
        Returns:
            List of CommentData objects
        """
        try:
            # Get comments from storage provider
            raw_comments = self.storage.get_comments(file_id)
            
            comment_data = []
            for comment in raw_comments:
                # Convert raw comment to CommentData
                if isinstance(comment, dict):
                    data = CommentData(
                        comment_id=comment.get('id', ''),
                        author=comment.get('author', 'Unknown'),
                        timestamp=datetime.fromisoformat(
                            comment.get('timestamp', datetime.now().isoformat())
                        ),
                        text=comment.get('text', ''),
                        context=comment.get('context', ''),
                        resolution=CommentResolution.RESOLVED if comment.get('resolved') else CommentResolution.UNRESOLVED,
                    )
                else:
                    data = comment
                
                comment_data.append(data)
                
                # Track reviewer response
                self._track_reviewer_response(review, data.author)
            
            review.draft_comments = comment_data
            return comment_data
        
        except Exception as e:
            logger.error(f"Failed to fetch draft comments: {e}")
            return []
    
    def fetch_published_comments(self, doc_state: DocumentState) -> list[CommentData]:
        """Fetch comments from the published document.
        
        Args:
            doc_state: Document state
        
        Returns:
            List of CommentData objects
        """
        if not doc_state.published_record or not doc_state.published_record.storage_file_id:
            return []
        
        try:
            comments = self.storage.get_comments(doc_state.published_record.storage_file_id)
            comment_data = [
                CommentData(
                    comment_id=c.get('id', '') if isinstance(c, dict) else c.comment_id,
                    author=c.get('author', 'Unknown') if isinstance(c, dict) else c.author,
                    timestamp=datetime.fromisoformat(c.get('timestamp', datetime.now().isoformat()))
                              if isinstance(c, dict) else c.timestamp,
                    text=c.get('text', '') if isinstance(c, dict) else c.text,
                    context=c.get('context', '') if isinstance(c, dict) else c.context,
                )
                for c in comments
            ]
            
            doc_state.published_record.comments = comment_data
            doc_state.pending_comments = [c for c in comment_data if not c.incorporated]
            
            return comment_data
        
        except Exception as e:
            logger.error(f"Failed to fetch published comments: {e}")
            return []
    
    def _track_reviewer_response(self, review: ReviewPeriod, reviewer: str) -> None:
        """Track that a reviewer has responded by adding a comment.
        
        Args:
            review: ReviewPeriod
            reviewer: Reviewer name
        """
        if reviewer not in review.responses:
            review.responses[reviewer] = ReviewerResponse(
                reviewer=reviewer,
                requested_at=review.started_at,
                responded_at=datetime.now(),
                response="commented",  # Implies engagement
            )
        else:
            response = review.responses[reviewer]
            if not response.responded_at:
                response.responded_at = datetime.now()
            response.comments_count = response.comments_count + 1
    
    def check_promotion_readiness(self, review: ReviewPeriod) -> tuple[bool, list[str]]:
        """Check if a review is ready for promotion to published.
        
        Conditions:
        - Deadline passed (or all required responded)
        - All required reviewers have responded
        - No outstanding "needs revision" feedback
        
        Args:
            review: ReviewPeriod
        
        Returns:
            (ready: bool, reasons: list[str])
        """
        reasons = []
        
        # Check deadline
        deadline = review.extended_to or review.ends_at
        if datetime.now() < deadline:
            days_left = (deadline - datetime.now()).days
            reasons.append(f"Review deadline not passed ({days_left} days remaining)")
        
        # Check required responses
        for reviewer in review.required_reviewers:
            if reviewer not in review.responses:
                reasons.append(f"No response from required reviewer: {reviewer}")
        
        # Check for revision requests
        revision_comments = [
            c for c in review.draft_comments
            if "revision" in c.text.lower() or "change" in c.text.lower()
        ]
        
        if revision_comments:
            reasons.append(f"{len(revision_comments)} comments requesting revisions")
        
        ready = len(reasons) == 0
        return ready, reasons
    
    def promote_draft_to_published(self, review: ReviewPeriod, doc_state: DocumentState,
                                  archive_previous: bool = True) -> bool:
        """Promote a draft document to published status.
        
        Moves the draft from /Drafts/ to /Documents/Published/
        Archives the previous version if present.
        
        Args:
            review: ReviewPeriod that was approved
            doc_state: Document state to update
            archive_previous: Whether to archive the previous published version
        
        Returns:
            True if successful
        """
        if not doc_state.draft_record:
            logger.error(f"No draft to promote for {doc_state.doc_id}")
            return False
        
        try:
            # Archive previous version if it exists
            if archive_previous and doc_state.published_record:
                old_record = doc_state.published_record
                archive_path = (
                    f"{doc_state.doc_id}-v{old_record.version}.docx"
                    .replace("/", "_")
                )
                new_archive_path = f"/Documents/Published/Archive/{archive_path}"
                
                if old_record.storage_file_id:
                    self.storage.move(old_record.storage_file_id, new_archive_path)
                
                doc_state.archived_records.append(old_record)
            
            # Move draft to published location
            draft_record = doc_state.draft_record
            if draft_record.storage_file_id:
                new_path = f"/Documents/Published/{doc_state.doc_id}.docx"
                self.storage.move(draft_record.storage_file_id, new_path)
            
            # Update document state
            doc_state.published_record = draft_record
            doc_state.published_record.version = self._next_version(doc_state)
            doc_state.draft_record = None
            doc_state.active_review = None
            
            # Mark review as promoted
            review.status = ReviewStatus.PROMOTED
            review.promoted_at = datetime.now()
            doc_state.review_history.append(review)
            
            logger.info(f"Promoted {doc_state.doc_id} to published")
            
            # Send notification
            self.notifications.send_email(
                doc_state.stakeholders,
                f"Document Published: {doc_state.doc_id}",
                f"'{doc_state.doc_id}' has been approved and published.\n"
                f"URL: {doc_state.published_record.storage_url}"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return False
    
    def _next_version(self, doc_state: DocumentState) -> str:
        """Generate next version number (1.0, 1.1, 2.0, etc.)."""
        if not doc_state.published_record:
            return "1.0"
        
        parts = doc_state.published_record.version.split('.')
        minor = int(parts[-1]) + 1
        return f"{parts[0]}.{minor}"
    
    def _notify_review_started(self, review: ReviewPeriod) -> None:
        """Send review started notifications to reviewers."""
        all_reviewers = review.required_reviewers + review.optional_reviewers
        
        subject = f"Document Review: {review.doc_id}"
        body = f"""You have been invited to review '{review.doc_id}'.

Review Period: {review.started_at.strftime('%Y-%m-%d')} to {review.ends_at.strftime('%Y-%m-%d')}
Required Reviewers: {len(review.required_reviewers)}
Optional Reviewers: {len(review.optional_reviewers)}

Please review the document and add comments/feedback."""
        
        try:
            self.notifications.send_email(all_reviewers, subject, body)
        except Exception as e:
            logger.error(f"Failed to send review notification: {e}")
    
    def send_deadline_reminder(self, review: ReviewPeriod) -> None:
        """Send reminder about upcoming review deadline."""
        all_reviewers = review.required_reviewers + review.optional_reviewers
        
        deadline = review.extended_to or review.ends_at
        days_left = (deadline - datetime.now()).days
        
        subject = f"Review Reminder ({days_left} days): {review.doc_id}"
        body = f"""Reminder: Review deadline for '{review.doc_id}' is in {days_left} days.

Deadline: {deadline.strftime('%Y-%m-%d %H:%M')}

Please complete your review and add feedback."""
        
        try:
            self.notifications.send_email(all_reviewers, subject, body)
        except Exception as e:
            logger.error(f"Failed to send reminder: {e}")
