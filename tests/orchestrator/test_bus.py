"""Tests for the EventBus."""

import json
import pytest
from pathlib import Path

from tools.agents.orchestrator.bus import EventBus, Event


class TestEventBus:
    """Test in-process pub/sub."""

    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("test.*", lambda topic, data: received.append((topic, data)))

        bus.publish("test.hello", {"msg": "hi"})

        assert len(received) == 1
        assert received[0] == ("test.hello", {"msg": "hi"})

    def test_glob_matching(self):
        bus = EventBus()
        received = []
        bus.subscribe("sense.*", lambda t, d: received.append(t))

        bus.publish("sense.ingest_complete", {})
        bus.publish("sense.draft_ready", {})
        bus.publish("doc.publish_complete", {})  # Should not match

        assert received == ["sense.ingest_complete", "sense.draft_ready"]

    def test_wildcard_subscription(self):
        bus = EventBus()
        received = []
        bus.subscribe("*", lambda t, d: received.append(t))

        bus.publish("a", {})
        bus.publish("b.c", {})

        assert len(received) == 2

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda t, d: received.append(t)
        bus.subscribe("*", handler)

        bus.publish("first", {})
        bus.unsubscribe(handler)
        bus.publish("second", {})

        assert received == ["first"]

    def test_history(self):
        bus = EventBus()
        bus.publish("a", {"x": 1})
        bus.publish("b", {"y": 2})

        assert len(bus.history) == 2
        assert bus.history[0].topic == "a"
        assert bus.history[1].topic == "b"

    def test_handler_error_does_not_break_bus(self):
        bus = EventBus()
        good_received = []

        def bad_handler(t, d):
            raise RuntimeError("boom")

        bus.subscribe("*", bad_handler)
        bus.subscribe("*", lambda t, d: good_received.append(t))

        bus.publish("test", {})

        assert good_received == ["test"]


class TestEventBusLogging:
    """Test durable .jsonl logging."""

    def test_log_written(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)

        bus.publish("sense.ingest", {"count": 5})
        bus.publish("doc.publish", {"url": "http://example.com"})

        lines = log.read_text().strip().splitlines()
        assert len(lines) == 2
        e1 = json.loads(lines[0])
        assert e1["topic"] == "sense.ingest"
        assert e1["data"]["count"] == 5

    def test_replay(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus1 = EventBus(log_path=log)
        bus1.publish("a", {"v": 1})
        bus1.publish("b", {"v": 2})

        # New bus replays from log
        bus2 = EventBus(log_path=log)
        replayed = []
        bus2.subscribe("*", lambda t, d: replayed.append(t))
        events = bus2.replay()

        assert len(events) == 2
        assert replayed == ["a", "b"]

    def test_replay_with_since_filter(self, tmp_path):
        log = tmp_path / "events.jsonl"
        # Write events with known timestamps
        with open(log, "w") as f:
            f.write(json.dumps({"topic": "old", "data": {}, "timestamp": "2026-01-01T00:00:00"}) + "\n")
            f.write(json.dumps({"topic": "new", "data": {}, "timestamp": "2026-02-18T00:00:00"}) + "\n")

        bus = EventBus(log_path=log)
        replayed = []
        bus.subscribe("*", lambda t, d: replayed.append(t))
        events = bus.replay(since="2026-02-01T00:00:00")

        assert replayed == ["new"]


class TestEvent:
    """Test Event data model."""

    def test_roundtrip(self):
        e = Event(topic="test", data={"key": "val"}, source="unit_test")
        d = e.to_dict()
        e2 = Event.from_dict(d)
        assert e2.topic == "test"
        assert e2.data == {"key": "val"}
        assert e2.source == "unit_test"

    def test_auto_timestamp(self):
        e = Event(topic="test", data={})
        assert e.timestamp  # Should be set automatically
