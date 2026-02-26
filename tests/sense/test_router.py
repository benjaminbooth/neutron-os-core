"""Unit tests for the signal router."""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from tools.agents.sense.router import Router, Endpoint, TransitRecord
from tools.agents.sense.models import Signal


class TestEndpoint:
    """Test Endpoint dataclass and matching logic."""

    def test_default_endpoint_matches_all(self):
        endpoint = Endpoint(id="test", name="Test Endpoint")
        
        signal = Signal(
            source="voice",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="hello world",
            signal_type="progress",
            confidence=0.8,
        )
        
        assert endpoint.matches(signal) is True

    def test_disabled_endpoint_matches_nothing(self):
        endpoint = Endpoint(id="test", name="Test", enabled=False)
        
        signal = Signal(
            source="voice",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="hello",
        )
        
        assert endpoint.matches(signal) is False

    def test_confidence_filter_min(self):
        endpoint = Endpoint(id="test", name="Test", min_confidence=0.7)
        
        low_conf = Signal(source="voice", timestamp="2026-02-15T10:00:00Z", 
                          raw_text="a", confidence=0.5)
        high_conf = Signal(source="voice", timestamp="2026-02-15T10:00:00Z",
                           raw_text="b", confidence=0.9)
        
        assert endpoint.matches(low_conf) is False
        assert endpoint.matches(high_conf) is True

    def test_confidence_filter_max(self):
        endpoint = Endpoint(id="test", name="Test", max_confidence=0.6)
        
        low_conf = Signal(source="voice", timestamp="2026-02-15T10:00:00Z",
                          raw_text="a", confidence=0.5)
        high_conf = Signal(source="voice", timestamp="2026-02-15T10:00:00Z",
                           raw_text="b", confidence=0.9)
        
        assert endpoint.matches(low_conf) is True
        assert endpoint.matches(high_conf) is False

    def test_signal_type_filter(self):
        endpoint = Endpoint(
            id="blockers",
            name="Blocker Collector",
            signal_types=["blocker", "decision"],
        )
        
        blocker = Signal(source="voice", timestamp="2026-02-15T10:00:00Z",
                         raw_text="a", signal_type="blocker")
        progress = Signal(source="voice", timestamp="2026-02-15T10:00:00Z",
                          raw_text="b", signal_type="progress")
        
        assert endpoint.matches(blocker) is True
        assert endpoint.matches(progress) is False

    def test_initiative_filter(self):
        endpoint = Endpoint(
            id="triga",
            name="TRIGA Channel",
            initiatives=["TRIGA Digital Twin", "NETL Backpacks"],
        )
        
        triga_signal = Signal(
            source="voice", timestamp="2026-02-15T10:00:00Z", raw_text="a",
            initiatives=["TRIGA Digital Twin"],
        )
        other_signal = Signal(
            source="voice", timestamp="2026-02-15T10:00:00Z", raw_text="b",
            initiatives=["MSR Project"],
        )
        no_init = Signal(
            source="voice", timestamp="2026-02-15T10:00:00Z", raw_text="c",
        )
        
        assert endpoint.matches(triga_signal) is True
        assert endpoint.matches(other_signal) is False
        assert endpoint.matches(no_init) is False

    def test_people_filter(self):
        endpoint = Endpoint(
            id="ben-channel",
            name="Ben's Channel",
            people=["Ben Booth", "Kevin"],
        )
        
        ben_signal = Signal(
            source="voice", timestamp="2026-02-15T10:00:00Z", raw_text="a",
            people=["Ben Booth"],
        )
        other_signal = Signal(
            source="voice", timestamp="2026-02-15T10:00:00Z", raw_text="b",
            people=["Alice"],
        )
        
        assert endpoint.matches(ben_signal) is True
        assert endpoint.matches(other_signal) is False


class TestTransitRecord:
    """Test TransitRecord dataclass."""

    def test_roundtrip(self):
        record = TransitRecord(
            signal_id="abc123",
            endpoint_id="test-endpoint",
            status="delivered",
            timestamp="2026-02-15T10:00:00Z",
        )
        
        d = record.to_dict()
        restored = TransitRecord.from_dict(d)
        
        assert restored.signal_id == record.signal_id
        assert restored.endpoint_id == record.endpoint_id
        assert restored.status == record.status


class TestRouter:
    """Test Router class."""

    @pytest.fixture
    def router_with_config(self, tmp_path):
        """Create a router with a test endpoints.yaml."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        endpoints_yaml = config_dir / "endpoints.yaml"
        endpoints_yaml.write_text("""
endpoints:
  - id: all-signals
    name: All Signals
    description: Catch-all for everything
    enabled: true
    signal_types: all
    delivery_method: file
    
  - id: blockers-only
    name: Blocker Channel
    description: Only blocker signals
    enabled: true
    signal_types:
      - blocker
    min_confidence: 0.7
    delivery_method: file
    
  - id: disabled
    name: Disabled Endpoint
    enabled: false
""")
        
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()
        
        return Router(config_path=endpoints_yaml, transit_log_path=processed_dir / "transit.json")

    def test_load_endpoints(self, router_with_config):
        endpoints = router_with_config.endpoints
        assert len(endpoints) == 3
        assert endpoints[0].id == "all-signals"
        assert endpoints[2].enabled is False

    def test_route_signal_to_matching_endpoints(self, router_with_config):
        signal = Signal(
            source="voice",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="Need help with thermal hydraulics code",
            signal_type="blocker",
            confidence=0.85,
        )
        
        matches = router_with_config.match(signal)
        
        # Should match all-signals and blockers-only
        endpoint_ids = [e.id for e in matches]
        assert "all-signals" in endpoint_ids
        assert "blockers-only" in endpoint_ids
        assert "disabled" not in endpoint_ids

    def test_route_excludes_low_confidence(self, router_with_config):
        signal = Signal(
            source="voice",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="Maybe a blocker?",
            signal_type="blocker",
            confidence=0.5,  # Below blockers-only threshold
        )
        
        matches = router_with_config.match(signal)
        endpoint_ids = [e.id for e in matches]
        
        assert "all-signals" in endpoint_ids
        assert "blockers-only" not in endpoint_ids  # Excluded due to confidence

    def test_queue_and_status(self, router_with_config):
        signals = [
            Signal(source="voice", timestamp="2026-02-15T10:00:00Z", raw_text="a"),
            Signal(source="voice", timestamp="2026-02-15T10:01:00Z", raw_text="b"),
        ]
        
        router_with_config.route(signals)
        status = router_with_config.status()
        
        assert status["queued"] >= 2  # At least 2 signals queued

    def test_empty_config_fallback(self, tmp_path):
        """Router should work with no config file (empty endpoints)."""
        router = Router(config_path=tmp_path / "nonexistent.yaml")
        endpoints = router.endpoints
        
        assert endpoints == []


class TestRouterIntegration:
    """Integration tests for router with file delivery."""

    def test_file_delivery(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        endpoints_yaml = config_dir / "endpoints.yaml"
        endpoints_yaml.write_text(f"""
endpoints:
  - id: file-output
    name: File Output
    enabled: true
    delivery_method: file
    delivery_config:
      path: {output_dir / 'signals.json'}
      format: json
""")
        
        router = Router(
            config_path=endpoints_yaml,
            transit_log_path=tmp_path / "transit.json",
        )
        
        signal = Signal(
            source="test",
            timestamp="2026-02-15T10:00:00Z",
            raw_text="Test signal content",
            detail="Test detail",
        )
        
        router.route([signal])
        router.deliver()
        
        # Verify file was created
        output_file = output_dir / "signals.json"
        assert output_file.exists()
