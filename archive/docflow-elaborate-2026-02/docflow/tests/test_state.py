"""Unit tests for core state management."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from docflow.core.state import (
    DocumentState, WorkflowState, ReviewPeriod, ReviewerResponse,
    PublicationRecord, ReviewStatus, AutonomyLevel, CommentResolution
)


class TestDocumentState:
    """Test DocumentState class."""
    
    def test_create_document_state(self):
        """Test creating a document state."""
        doc = DocumentState(
            source_path=Path("/test/doc.md"),
            markdown="# Test Document",
        )
        
        assert doc.source_path == Path("/test/doc.md")
        assert doc.markdown == "# Test Document"
        assert doc.id is not None
        assert doc.last_modified is not None
    
    def test_document_state_with_review(self):
        """Test document state with review period."""
        review = ReviewPeriod(
            document_id="doc123",
            deadline=datetime.now() + timedelta(days=7),
            reviewers=["user1@test.com", "user2@test.com"],
        )
        
        doc = DocumentState(
            source_path=Path("/test/doc.md"),
            markdown="# Test",
            review_period=review,
        )
        
        assert doc.review_period is not None
        assert len(doc.review_period.reviewers) == 2
        assert doc.review_period.status == ReviewStatus.PENDING
    
    def test_document_state_serialization(self):
        """Test serializing document state to dict."""
        doc = DocumentState(
            source_path=Path("/test/doc.md"),
            markdown="# Test",
        )
        
        data = doc.to_dict()
        assert data["source_path"] == "/test/doc.md"
        assert data["markdown"] == "# Test"
        assert "id" in data
        assert "last_modified" in data
    
    def test_document_state_from_dict(self):
        """Test creating document state from dict."""
        data = {
            "id": "doc123",
            "source_path": "/test/doc.md",
            "markdown": "# Test",
            "last_modified": datetime.now().isoformat(),
        }
        
        doc = DocumentState.from_dict(data)
        assert doc.id == "doc123"
        assert doc.source_path == Path("/test/doc.md")
        assert doc.markdown == "# Test"


class TestReviewPeriod:
    """Test ReviewPeriod class."""
    
    def test_create_review_period(self):
        """Test creating a review period."""
        review = ReviewPeriod(
            document_id="doc123",
            deadline=datetime.now() + timedelta(days=7),
            reviewers=["user1@test.com"],
        )
        
        assert review.document_id == "doc123"
        assert review.status == ReviewStatus.PENDING
        assert len(review.reviewers) == 1
    
    def test_add_reviewer_response(self):
        """Test adding reviewer responses."""
        review = ReviewPeriod(
            document_id="doc123",
            deadline=datetime.now() + timedelta(days=7),
            reviewers=["user1@test.com"],
        )
        
        response = ReviewerResponse(
            reviewer="user1@test.com",
            approved=True,
            comments="Looks good",
            timestamp=datetime.now(),
        )
        
        review.responses.append(response)
        
        assert len(review.responses) == 1
        assert review.responses[0].approved is True
    
    def test_review_eligibility_for_promotion(self):
        """Test checking if review is eligible for promotion."""
        review = ReviewPeriod(
            document_id="doc123",
            deadline=datetime.now() + timedelta(days=7),
            reviewers=["user1@test.com", "user2@test.com"],
            required_reviewers=["user1@test.com"],
        )
        
        # Not eligible without required reviewer
        assert not review.is_eligible_for_promotion()
        
        # Add required reviewer approval
        review.responses.append(ReviewerResponse(
            reviewer="user1@test.com",
            approved=True,
            timestamp=datetime.now(),
        ))
        
        # Now eligible
        assert review.is_eligible_for_promotion()
    
    def test_review_deadline_extension(self):
        """Test extending review deadline."""
        original_deadline = datetime.now() + timedelta(days=7)
        review = ReviewPeriod(
            document_id="doc123",
            deadline=original_deadline,
            reviewers=["user1@test.com"],
        )
        
        # Extend by 3 days
        review.extend_deadline(days=3)
        
        assert review.deadline > original_deadline
        assert review.deadline == original_deadline + timedelta(days=3)


class TestWorkflowState:
    """Test WorkflowState class."""
    
    def test_create_workflow_state(self):
        """Test creating workflow state."""
        workflow = WorkflowState(
            repository_root=Path("/repo"),
        )
        
        assert workflow.repository_root == Path("/repo")
        assert workflow.documents == {}
        assert workflow.autonomy_level == AutonomyLevel.MANUAL
    
    def test_add_document_to_workflow(self):
        """Test adding document to workflow."""
        workflow = WorkflowState(
            repository_root=Path("/repo"),
        )
        
        doc = DocumentState(
            source_path=Path("/repo/doc.md"),
            markdown="# Test",
        )
        
        workflow.documents[doc.id] = doc
        
        assert len(workflow.documents) == 1
        assert doc.id in workflow.documents
    
    def test_workflow_autonomy_levels(self):
        """Test different autonomy levels."""
        for level in AutonomyLevel:
            workflow = WorkflowState(
                repository_root=Path("/repo"),
                autonomy_level=level,
            )
            assert workflow.autonomy_level == level
    
    def test_workflow_active_reviews(self):
        """Test getting active reviews from workflow."""
        workflow = WorkflowState(
            repository_root=Path("/repo"),
        )
        
        # Add document with active review
        doc1 = DocumentState(
            source_path=Path("/repo/doc1.md"),
            markdown="# Doc 1",
            review_period=ReviewPeriod(
                document_id="doc1",
                deadline=datetime.now() + timedelta(days=7),
                reviewers=["user1@test.com"],
                status=ReviewStatus.PENDING,
            )
        )
        
        # Add document without review
        doc2 = DocumentState(
            source_path=Path("/repo/doc2.md"),
            markdown="# Doc 2",
        )
        
        workflow.documents[doc1.id] = doc1
        workflow.documents[doc2.id] = doc2
        
        # Get active reviews
        active_reviews = workflow.get_active_reviews()
        
        assert len(active_reviews) == 1
        assert active_reviews[0].document_id == "doc1"


class TestPublicationRecord:
    """Test PublicationRecord class."""
    
    def test_create_publication_record(self):
        """Test creating publication record."""
        record = PublicationRecord(
            document_id="doc123",
            version="1.0.0",
            published_at=datetime.now(),
            published_by="user@test.com",
            remote_path="https://storage/doc.docx",
        )
        
        assert record.document_id == "doc123"
        assert record.version == "1.0.0"
        assert record.published_by == "user@test.com"
    
    def test_publication_record_with_metadata(self):
        """Test publication record with metadata."""
        record = PublicationRecord(
            document_id="doc123",
            version="1.0.0",
            published_at=datetime.now(),
            published_by="user@test.com",
            remote_path="https://storage/doc.docx",
            metadata={
                "review_score": 4.5,
                "comments_resolved": 10,
            }
        )
        
        assert "review_score" in record.metadata
        assert record.metadata["review_score"] == 4.5


class TestEnums:
    """Test enum values."""
    
    def test_review_status_values(self):
        """Test ReviewStatus enum values."""
        assert ReviewStatus.PENDING.value == "pending"
        assert ReviewStatus.APPROVED.value == "approved"
        assert ReviewStatus.REJECTED.value == "rejected"
        assert ReviewStatus.EXPIRED.value == "expired"
    
    def test_autonomy_level_values(self):
        """Test AutonomyLevel enum values."""
        levels = list(AutonomyLevel)
        assert AutonomyLevel.MANUAL in levels
        assert AutonomyLevel.ASSISTED in levels
        assert AutonomyLevel.REVIEW in levels
        assert AutonomyLevel.NOTIFY in levels
        assert AutonomyLevel.AUTONOMOUS in levels
        
        # Test ordering (manual < autonomous)
        assert AutonomyLevel.MANUAL.value < AutonomyLevel.AUTONOMOUS.value
    
    def test_comment_resolution_values(self):
        """Test CommentResolution enum values."""
        assert CommentResolution.UNRESOLVED.value == "unresolved"
        assert CommentResolution.ACCEPTED.value == "accepted"
        assert CommentResolution.REJECTED.value == "rejected"
        assert CommentResolution.DEFERRED.value == "deferred"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])