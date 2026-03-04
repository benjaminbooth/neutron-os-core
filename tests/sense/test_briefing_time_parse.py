"""Tests for _parse_since() — natural language time parsing for --since."""

from datetime import datetime, timedelta, timezone

import pytest

from tools.pipelines.sense.briefing import _parse_since


# --- ISO passthrough ---

class TestISOParsing:
    def test_date_only(self):
        result = _parse_since("2026-02-01")
        assert result == datetime(2026, 2, 1, tzinfo=timezone.utc)

    def test_datetime(self):
        result = _parse_since("2026-02-01T14:30:00")
        assert result == datetime(2026, 2, 1, 14, 30, tzinfo=timezone.utc)

    def test_datetime_with_z(self):
        result = _parse_since("2026-02-01T14:30:00Z")
        assert result == datetime(2026, 2, 1, 14, 30, tzinfo=timezone.utc)

    def test_datetime_with_offset(self):
        result = _parse_since("2026-02-01T14:30:00+05:00")
        assert result.tzinfo is not None
        assert result.utcoffset() == timedelta(hours=5)

    def test_whitespace_stripped(self):
        result = _parse_since("  2026-02-01  ")
        assert result == datetime(2026, 2, 1, tzinfo=timezone.utc)


# --- Shorthand ---

class TestShorthand:
    def test_days(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("2d")
        after = datetime.now(timezone.utc)
        assert before - timedelta(days=2, seconds=1) < result < after - timedelta(days=2) + timedelta(seconds=1)

    def test_hours(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("3h")
        after = datetime.now(timezone.utc)
        assert before - timedelta(hours=3, seconds=1) < result < after - timedelta(hours=3) + timedelta(seconds=1)

    def test_weeks(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("1w")
        after = datetime.now(timezone.utc)
        assert before - timedelta(weeks=1, seconds=1) < result < after - timedelta(weeks=1) + timedelta(seconds=1)

    def test_months(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("2m")
        after = datetime.now(timezone.utc)
        expected_delta = timedelta(days=60)
        assert before - expected_delta - timedelta(seconds=1) < result < after - expected_delta + timedelta(seconds=1)

    def test_months_mo(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("2mo")
        after = datetime.now(timezone.utc)
        expected_delta = timedelta(days=60)
        assert before - expected_delta - timedelta(seconds=1) < result < after - expected_delta + timedelta(seconds=1)


# --- Named keywords ---

class TestKeywords:
    def test_yesterday(self):
        result = _parse_since("yesterday")
        expected = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        expected_utc = expected.astimezone(timezone.utc)
        assert abs((result - expected_utc).total_seconds()) < 2

    def test_today(self):
        result = _parse_since("today")
        expected = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expected_utc = expected.astimezone(timezone.utc)
        assert abs((result - expected_utc).total_seconds()) < 2

    def test_case_insensitive(self):
        result = _parse_since("Yesterday")
        assert result.tzinfo is not None

    def test_today_is_tz_aware(self):
        result = _parse_since("today")
        assert result.tzinfo is not None


# --- Phrases ---

class TestPhrases:
    def test_last_week(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("last week")
        after = datetime.now(timezone.utc)
        assert before - timedelta(weeks=1, seconds=1) < result < after - timedelta(weeks=1) + timedelta(seconds=1)

    def test_last_month(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("last month")
        after = datetime.now(timezone.utc)
        assert before - timedelta(days=30, seconds=1) < result < after - timedelta(days=30) + timedelta(seconds=1)

    def test_n_days_ago(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("2 days ago")
        after = datetime.now(timezone.utc)
        assert before - timedelta(days=2, seconds=1) < result < after - timedelta(days=2) + timedelta(seconds=1)

    def test_n_hours_ago(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("3 hours ago")
        after = datetime.now(timezone.utc)
        assert before - timedelta(hours=3, seconds=1) < result < after - timedelta(hours=3) + timedelta(seconds=1)

    def test_n_weeks_ago(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("1 week ago")
        after = datetime.now(timezone.utc)
        assert before - timedelta(weeks=1, seconds=1) < result < after - timedelta(weeks=1) + timedelta(seconds=1)

    def test_n_months_ago(self):
        before = datetime.now(timezone.utc)
        result = _parse_since("2 months ago")
        after = datetime.now(timezone.utc)
        expected_delta = timedelta(days=60)
        assert before - expected_delta - timedelta(seconds=1) < result < after - expected_delta + timedelta(seconds=1)

    def test_singular_day(self):
        result = _parse_since("1 day ago")
        assert result.tzinfo is not None


# --- All results are tz-aware ---

class TestTzAware:
    @pytest.mark.parametrize("expr", [
        "2026-02-01",
        "yesterday",
        "today",
        "2d",
        "3h",
        "last week",
        "2 days ago",
    ])
    def test_always_tz_aware(self, expr):
        result = _parse_since(expr)
        assert result.tzinfo is not None, f"'{expr}' returned naive datetime"


# --- Error handling ---

class TestErrors:
    def test_invalid_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unrecognized time expression"):
            _parse_since("gobbledygook")

    def test_error_message_lists_formats(self):
        with pytest.raises(ValueError, match="ISO date"):
            _parse_since("not a date")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _parse_since("")
