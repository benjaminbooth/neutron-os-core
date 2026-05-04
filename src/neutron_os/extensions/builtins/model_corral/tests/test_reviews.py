"""Tests for the Model Corral review/comment system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neutron_os.extensions.builtins.model_corral.service import ModelCorralService


@pytest.fixture()
def svc(tmp_path: Path) -> ModelCorralService:
    """Create a ModelCorralService with a mock engine and storage."""
    engine = MagicMock()
    storage = MagicMock()
    return ModelCorralService(engine=engine, storage=storage)


@pytest.fixture()
def reviews_dir(tmp_path: Path) -> Path:
    d = tmp_path / "model-reviews"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Service: add_review
# ---------------------------------------------------------------------------


class TestAddReview:
    def test_creates_review_with_correct_fields(self, svc, reviews_dir):
        review = svc.add_review(
            "test-model",
            reviewer="cole@utexas.edu",
            comment="Water temp should be 300K",
            reviews_dir=reviews_dir,
        )
        assert review["model_id"] == "test-model"
        assert review["reviewer"] == "cole@utexas.edu"
        assert review["comment"] == "Water temp should be 300K"
        assert review["status"] == "open"
        assert review["created_at"]

    def test_auto_generates_review_id(self, svc, reviews_dir):
        review = svc.add_review(
            "test-model",
            reviewer="cole",
            comment="test",
            reviews_dir=reviews_dir,
        )
        assert review["review_id"].startswith("rev-")
        assert len(review["review_id"]) == 16  # "rev-" + 12 hex chars

    def test_stores_version(self, svc, reviews_dir):
        review = svc.add_review(
            "test-model",
            reviewer="cole",
            comment="test",
            version="1.2.0",
            reviews_dir=reviews_dir,
        )
        assert review["version"] == "1.2.0"

    def test_version_defaults_to_none(self, svc, reviews_dir):
        review = svc.add_review(
            "test-model",
            reviewer="cole",
            comment="test",
            reviews_dir=reviews_dir,
        )
        assert review["version"] is None

    def test_multiple_reviews_accumulate(self, svc, reviews_dir):
        svc.add_review("m1", reviewer="a", comment="first", reviews_dir=reviews_dir)
        svc.add_review("m1", reviewer="b", comment="second", reviews_dir=reviews_dir)
        svc.add_review("m1", reviewer="c", comment="third", reviews_dir=reviews_dir)

        reviews = svc.get_reviews("m1", reviews_dir=reviews_dir)
        assert len(reviews) == 3


# ---------------------------------------------------------------------------
# Service: get_reviews
# ---------------------------------------------------------------------------


class TestGetReviews:
    def test_returns_all_reviews(self, svc, reviews_dir):
        svc.add_review("m1", reviewer="a", comment="c1", reviews_dir=reviews_dir)
        svc.add_review("m1", reviewer="b", comment="c2", reviews_dir=reviews_dir)

        reviews = svc.get_reviews("m1", reviews_dir=reviews_dir)
        assert len(reviews) == 2

    def test_filters_by_status(self, svc, reviews_dir):
        r1 = svc.add_review("m1", reviewer="a", comment="c1", reviews_dir=reviews_dir)
        svc.add_review("m1", reviewer="b", comment="c2", reviews_dir=reviews_dir)
        svc.resolve_review("m1", r1["review_id"], reviews_dir=reviews_dir)

        open_reviews = svc.get_reviews("m1", status="open", reviews_dir=reviews_dir)
        assert len(open_reviews) == 1
        assert open_reviews[0]["reviewer"] == "b"

        addressed = svc.get_reviews("m1", status="addressed", reviews_dir=reviews_dir)
        assert len(addressed) == 1
        assert addressed[0]["reviewer"] == "a"

    def test_returns_empty_for_unknown_model(self, svc, reviews_dir):
        reviews = svc.get_reviews("nonexistent", reviews_dir=reviews_dir)
        assert reviews == []


# ---------------------------------------------------------------------------
# Service: resolve_review
# ---------------------------------------------------------------------------


class TestResolveReview:
    def test_changes_status_to_addressed(self, svc, reviews_dir):
        r = svc.add_review("m1", reviewer="a", comment="fix this", reviews_dir=reviews_dir)
        ok = svc.resolve_review("m1", r["review_id"], reviews_dir=reviews_dir)
        assert ok is True

        reviews = svc.get_reviews("m1", reviews_dir=reviews_dir)
        assert reviews[0]["status"] == "addressed"

    def test_dismiss_changes_status(self, svc, reviews_dir):
        r = svc.add_review("m1", reviewer="a", comment="nit", reviews_dir=reviews_dir)
        ok = svc.resolve_review(
            "m1",
            r["review_id"],
            resolution="dismissed",
            reviews_dir=reviews_dir,
        )
        assert ok is True

        reviews = svc.get_reviews("m1", reviews_dir=reviews_dir)
        assert reviews[0]["status"] == "dismissed"

    def test_returns_false_for_unknown_review_id(self, svc, reviews_dir):
        svc.add_review("m1", reviewer="a", comment="c1", reviews_dir=reviews_dir)
        ok = svc.resolve_review("m1", "rev-doesnotexist", reviews_dir=reviews_dir)
        assert ok is False

    def test_returns_false_for_unknown_model(self, svc, reviews_dir):
        ok = svc.resolve_review("nonexistent", "rev-abc", reviews_dir=reviews_dir)
        assert ok is False


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestCLIReview:
    @patch("neutron_os.extensions.builtins.model_corral.cli._get_service")
    def test_review_command(self, mock_get_svc, tmp_path, capsys):
        mock_svc = MagicMock()
        mock_svc.add_review.return_value = {
            "review_id": "rev-abc123def456",
            "model_id": "test-model",
            "reviewer": "cole@utexas.edu",
            "comment": "Water temp should be 300K",
            "status": "open",
            "created_at": "2026-04-02T00:00:00+00:00",
            "version": None,
        }
        mock_get_svc.return_value = mock_svc

        from neutron_os.extensions.builtins.model_corral.cli import main

        rc = main(["review", "test-model", "-c", "Water temp should be 300K"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Review added" in out
        assert "rev-abc123def456" in out

    @patch("neutron_os.extensions.builtins.model_corral.cli._get_service")
    def test_reviews_command_shows_open_count(self, mock_get_svc, capsys):
        mock_svc = MagicMock()
        mock_svc.get_reviews.return_value = [
            {
                "review_id": "rev-1",
                "reviewer": "cole",
                "comment": "fix this",
                "status": "open",
                "version": None,
            },
            {
                "review_id": "rev-2",
                "reviewer": "nick",
                "comment": "done",
                "status": "addressed",
                "version": None,
            },
        ]
        mock_get_svc.return_value = mock_svc

        from neutron_os.extensions.builtins.model_corral.cli import main

        rc = main(["reviews", "test-model"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 open" in out

    @patch("neutron_os.extensions.builtins.model_corral.cli._get_service")
    def test_resolve_command(self, mock_get_svc, capsys):
        mock_svc = MagicMock()
        mock_svc.resolve_review.return_value = True
        mock_get_svc.return_value = mock_svc

        from neutron_os.extensions.builtins.model_corral.cli import main

        rc = main(["resolve", "test-model", "rev-abc123"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "addressed" in out

    @patch("neutron_os.extensions.builtins.model_corral.cli._get_service")
    def test_resolve_dismiss(self, mock_get_svc, capsys):
        mock_svc = MagicMock()
        mock_svc.resolve_review.return_value = True
        mock_get_svc.return_value = mock_svc

        from neutron_os.extensions.builtins.model_corral.cli import main

        rc = main(["resolve", "test-model", "rev-abc123", "--dismiss"])
        assert rc == 0
        mock_svc.resolve_review.assert_called_with("test-model", "rev-abc123", "dismissed")


class TestShowIncludesReviews:
    @patch("neutron_os.extensions.builtins.model_corral.cli._get_service")
    def test_show_displays_open_reviews(self, mock_get_svc, capsys):
        mock_svc = MagicMock()
        mock_svc.show.return_value = {
            "model_id": "test-model",
            "name": "Test",
            "reactor_type": "TRIGA",
            "physics_code": "MCNP",
            "status": "draft",
            "access_tier": "facility",
            "facility": "NETL",
            "created_by": "nick",
            "description": "",
            "tags": [],
            "versions": [],
        }
        mock_svc.get_reviews.return_value = [
            {
                "review_id": "rev-1",
                "reviewer": "cole@utexas.edu",
                "comment": "Water temp should be 300K not 293K",
                "status": "open",
            },
        ]
        mock_get_svc.return_value = mock_svc

        from neutron_os.extensions.builtins.model_corral.cli import main

        rc = main(["show", "test-model"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Reviews (1 open)" in out
        assert "cole@utexas.edu" in out
        assert "Water temp" in out
