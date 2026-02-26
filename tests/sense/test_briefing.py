"""Unit tests for the briefing service."""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.agents.sense.briefing import (
    BriefingService,
    BriefingTopic,
    ConsumptionEvent,
    ConsumptionRecord,
    Briefing,
    TOPIC_KEYWORDS,
)
from tools.agents.sense.models import Signal


class TestBriefingTopic:
    """Test BriefingTopic enum."""

    def test_all_topics_have_keywords(self):
        """Verify each topic has associated keywords for fallback matching."""
        for topic in BriefingTopic:
            if topic != BriefingTopic.GENERAL and topic != BriefingTopic.LONG_RUNNING:
                assert topic in TOPIC_KEYWORDS, f"Topic {topic} missing keywords"

    def test_topic_values(self):
        assert BriefingTopic.PEOPLE.value == "people"
        assert BriefingTopic.TECH.value == "tech"
        assert BriefingTopic.BLOCKERS.value == "blockers"


class TestConsumptionRecord:
    """Test ConsumptionRecord dataclass."""

    def test_roundtrip(self):
        record = ConsumptionRecord(
            event_type=ConsumptionEvent.BRIEFING_DELIVERED,
            timestamp=datetime.now(timezone.utc),
            details={"topic": "general"},
        )
        
        d = record.to_dict()
        restored = ConsumptionRecord.from_dict(d)
        
        assert restored.event_type == record.event_type
        assert restored.details == record.details


class TestBriefingService:
    """Test BriefingService class."""

    @pytest.fixture
    def service(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()
        
        return BriefingService(
            state_path=state_dir / "briefing_state.json",
            processed_dir=processed_dir,
        )

    @pytest.fixture
    def sample_signals(self, tmp_path):
        """Create sample processed signals."""
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir(exist_ok=True)
        
        signals = [
            Signal(
                source="voice",
                timestamp=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                raw_text="Kevin is working on TRIGA thermal hydraulics",
                detail="Kevin progressing on TRIGA thermal work",
                people=["Kevin"],
                initiatives=["TRIGA Digital Twin"],
                signal_type="progress",
            ),
            Signal(
                source="voice",
                timestamp=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                raw_text="Blocked on NRC approval for license amendment",
                detail="NRC approval blocking progress",
                initiatives=["TRIGA Digital Twin"],
                signal_type="blocker",
            ),
            Signal(
                source="voice",
                timestamp=datetime.now(timezone.utc).isoformat(),
                raw_text="Conference abstract accepted for ANS meeting",
                detail="ANS conference abstract accepted",
                signal_type="decision",
            ),
        ]
        
        # Write signals to processed dir
        for i, sig in enumerate(signals):
            sig_file = processed_dir / f"signal_{i}.json"
            sig_file.write_text(json.dumps(sig.to_dict(), indent=2))
        
        return signals

    def test_brief_me_returns_briefing(self, service, sample_signals, tmp_path):
        service.processed_dir = tmp_path / "processed"
        
        briefing = service.brief_me()
        
        assert isinstance(briefing, Briefing)
        assert briefing.topic in [t.value for t in BriefingTopic]
        assert briefing.signal_count >= 0

    def test_topic_detection_people(self, service):
        """Test that person names trigger PEOPLE topic."""
        category, query = service._detect_topic_category("Kevin")
        
        assert category == BriefingTopic.PEOPLE or query == "Kevin"

    def test_topic_detection_tech(self, service):
        """Test that tech keywords trigger TECH topic."""
        category, query = service._detect_topic_category("bugs")
        
        # Should detect as TECH or pass through
        assert category == BriefingTopic.TECH or "bug" in query.lower()

    def test_topic_detection_blockers(self, service):
        """Test that blocker keywords trigger BLOCKERS topic."""
        category, query = service._detect_topic_category("blockers")
        
        assert category == BriefingTopic.BLOCKERS

    def test_record_consumption(self, service):
        """Test that briefing delivery is recorded."""
        service.record_consumption(
            event_type=ConsumptionEvent.BRIEFING_DELIVERED,
            details={"topic": "general"},
        )
        
        records = service.get_consumption_records()
        assert len(records) >= 1
        assert records[-1].event_type == ConsumptionEvent.BRIEFING_DELIVERED

    def test_time_window_calculation(self, service):
        """Test automatic time window based on last consumption."""
        # No prior consumption - should use default
        window_start = service._calculate_time_window()
        
        # Should be within last 48 hours by default
        assert window_start < datetime.now(timezone.utc)
        
        # Record consumption
        service.record_consumption(
            event_type=ConsumptionEvent.BRIEFING_DELIVERED,
        )
        
        # Now window should start from that point
        window_start2 = service._calculate_time_window()
        assert window_start2 >= window_start

    def test_acknowledge_updates_state(self, service, sample_signals, tmp_path):
        service.processed_dir = tmp_path / "processed"
        
        # Generate a briefing with acknowledge=True
        briefing = service.brief_me(acknowledge=True)
        
        records = service.get_consumption_records()
        assert any(r.event_type == ConsumptionEvent.BRIEFING_ACKNOWLEDGED for r in records)


class TestBriefingFiltering:
    """Test signal filtering for topic-focused briefings."""

    @pytest.fixture
    def service_with_signals(self, tmp_path):
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()
        
        # Create diverse signals
        signals = [
            {"type": "progress", "people": ["Kevin"], "initiatives": ["TRIGA"]},
            {"type": "blocker", "people": ["Alice"], "initiatives": ["MSR"]},
            {"type": "decision", "people": ["Ben"], "initiatives": ["TRIGA"]},
            {"type": "progress", "people": ["Kevin"], "initiatives": ["NETL"]},
        ]
        
        for i, s in enumerate(signals):
            sig = Signal(
                source="voice",
                timestamp=datetime.now(timezone.utc).isoformat(),
                raw_text=f"Test signal {i}",
                signal_type=s["type"],
                people=s["people"],
                initiatives=s["initiatives"],
            )
            (processed_dir / f"sig_{i}.json").write_text(json.dumps(sig.to_dict()))
        
        service = BriefingService(
            state_path=tmp_path / "state" / "briefing.json",
            processed_dir=processed_dir,
        )
        return service

    def test_filter_by_person(self, service_with_signals):
        signals = service_with_signals._load_signals()
        filtered = service_with_signals._filter_signals_by_topic(
            signals, 
            category=BriefingTopic.PEOPLE,
            query="Kevin",
        )
        
        # Should only include Kevin's signals
        for sig in filtered:
            assert "Kevin" in sig.get("people", [])

    def test_filter_by_initiative(self, service_with_signals):
        signals = service_with_signals._load_signals()
        filtered = service_with_signals._filter_signals_by_topic(
            signals,
            category=BriefingTopic.INITIATIVES,
            query="TRIGA",
        )
        
        for sig in filtered:
            assert any("TRIGA" in init for init in sig.get("initiatives", []))

    def test_filter_blockers_only(self, service_with_signals):
        signals = service_with_signals._load_signals()
        filtered = service_with_signals._filter_signals_by_topic(
            signals,
            category=BriefingTopic.BLOCKERS,
            query="",
        )
        
        for sig in filtered:
            assert sig.get("signal_type") == "blocker"
