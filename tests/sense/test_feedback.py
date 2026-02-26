"""Unit tests for the feedback collection system."""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.agents.sense.feedback import (
    FeedbackCollector,
    FeedbackRequest,
    SignalFeedback,
    FEEDBACK_TYPES,
)
from tools.agents.sense.models import Signal


class TestFeedbackTypes:
    """Test feedback type definitions."""

    def test_all_types_have_descriptions(self):
        for feedback_type, description in FEEDBACK_TYPES.items():
            assert isinstance(feedback_type, str)
            assert isinstance(description, str)
            assert len(description) > 0

    def test_required_types_exist(self):
        required = [
            "confirm_relevance",
            "add_initiative",
            "correct_error",
            "add_context",
            "approve",
            "dismiss",
        ]
        for t in required:
            assert t in FEEDBACK_TYPES


class TestFeedbackRequest:
    """Test FeedbackRequest dataclass."""

    def test_auto_timestamp(self):
        request = FeedbackRequest(
            request_id="abc123",
            signal_id="sig456",
            originator="ben@example.com",
            signal_summary="Test signal",
        )
        
        assert request.created_at != ""
        # Should be a valid ISO timestamp
        datetime.fromisoformat(request.created_at.replace("Z", "+00:00"))

    def test_roundtrip(self):
        request = FeedbackRequest(
            request_id="abc123",
            signal_id="sig456",
            originator="ben@example.com",
            signal_summary="Signal about TRIGA",
            routed_to=["endpoint-1", "endpoint-2"],
            suggested_prds=["prd-triga", "prd-netl"],
        )
        
        d = request.to_dict()
        restored = FeedbackRequest.from_dict(d)
        
        assert restored.request_id == request.request_id
        assert restored.originator == request.originator
        assert restored.routed_to == request.routed_to
        assert restored.suggested_prds == request.suggested_prds


class TestSignalFeedback:
    """Test SignalFeedback dataclass."""

    def test_valid_feedback_type(self):
        feedback = SignalFeedback(
            signal_id="sig123",
            feedback_type="add_initiative",
            content="Also relevant to MSR project",
            originator="ben@example.com",
        )
        
        assert feedback.is_valid() is True

    def test_invalid_feedback_type(self):
        feedback = SignalFeedback(
            signal_id="sig123",
            feedback_type="invalid_type_xyz",
            content="test",
            originator="ben@example.com",
        )
        
        assert feedback.is_valid() is False

    def test_auto_timestamp(self):
        feedback = SignalFeedback(
            signal_id="sig123",
            feedback_type="approve",
            content="",
            originator="ben@example.com",
        )
        
        assert feedback.timestamp != ""


class TestFeedbackCollector:
    """Test FeedbackCollector class."""

    @pytest.fixture
    def collector(self, tmp_path):
        feedback_dir = tmp_path / "feedback"
        feedback_dir.mkdir()
        return FeedbackCollector(feedback_dir=feedback_dir)

    @pytest.fixture
    def sample_signal(self):
        return Signal(
            source="voice",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="Discussion about TRIGA thermal limits",
            detail="TRIGA thermal hydraulics need review",
            originator="ben@example.com",
            initiatives=["TRIGA Digital Twin"],
            signal_type="action_item",
        )

    def test_request_feedback(self, collector, sample_signal):
        request = collector.request_feedback(sample_signal)
        
        assert request is not None
        assert request.signal_id == sample_signal.signal_id
        assert request.originator == sample_signal.originator
        assert "TRIGA" in request.signal_summary

    def test_request_saved_to_pending(self, collector, sample_signal):
        request = collector.request_feedback(sample_signal)
        
        # Reload collector and check persistence
        collector2 = FeedbackCollector(feedback_dir=collector.feedback_dir)
        pending = collector2.get_pending_requests()
        
        assert len(pending) >= 1
        assert any(r.request_id == request.request_id for r in pending)

    def test_apply_feedback_updates_signal(self, collector, sample_signal):
        # Create a feedback request first
        request = collector.request_feedback(sample_signal)
        
        # Now apply feedback
        feedback = SignalFeedback(
            signal_id=sample_signal.signal_id,
            feedback_type="add_initiative",
            content="Also relevant to NETL Backpacks",
            originator="ben@example.com",
        )
        
        result = collector.apply_feedback(feedback)
        
        assert result is True
        
        # Check feedback was logged
        log = collector.get_feedback_log()
        assert len(log) >= 1

    def test_dismiss_feedback_marks_noise(self, collector, sample_signal):
        request = collector.request_feedback(sample_signal)
        
        feedback = SignalFeedback(
            signal_id=sample_signal.signal_id,
            feedback_type="dismiss",
            content="This is just noise",
            originator="ben@example.com",
        )
        
        result = collector.apply_feedback(feedback)
        assert result is True

    def test_get_feedback_for_signal(self, collector, sample_signal):
        collector.request_feedback(sample_signal)
        
        feedback1 = SignalFeedback(
            signal_id=sample_signal.signal_id,
            feedback_type="add_context",
            content="Kevin was in the meeting",
            originator="ben@example.com",
        )
        feedback2 = SignalFeedback(
            signal_id=sample_signal.signal_id,
            feedback_type="set_priority",
            content="urgent",
            originator="ben@example.com",
        )
        
        collector.apply_feedback(feedback1)
        collector.apply_feedback(feedback2)
        
        signal_feedback = collector.get_feedback_for_signal(sample_signal.signal_id)
        assert len(signal_feedback) == 2

    def test_no_feedback_without_originator(self, collector):
        signal = Signal(
            source="voice",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="Anonymous signal",
            # No originator set
        )
        
        request = collector.request_feedback(signal)
        
        # Should return None or handle gracefully
        assert request is None or request.originator == ""
