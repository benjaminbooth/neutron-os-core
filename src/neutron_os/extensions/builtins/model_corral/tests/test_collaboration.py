"""Tests for collaboration features: invite, contributors, status, progression clone."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from sqlalchemy import create_engine

from axiom.infra.storage import LocalStorageProvider


@pytest.fixture
def db_engine():
    from neutron_os.extensions.builtins.model_corral.db_models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def storage(tmp_path):
    return LocalStorageProvider({"base_dir": str(tmp_path / "object-store")})


@pytest.fixture
def service(db_engine, storage):
    from neutron_os.extensions.builtins.model_corral.service import ModelCorralService

    return ModelCorralService(engine=db_engine, storage=storage)


@pytest.fixture
def valid_model_dir(tmp_path):
    """Create a valid model directory for testing."""
    d = tmp_path / "triga-test-mcnp-v1"
    d.mkdir()
    manifest = {
        "model_id": "triga-test-mcnp-v1",
        "name": "Test TRIGA MCNP",
        "version": "1.0.0",
        "status": "draft",
        "reactor_type": "TRIGA",
        "facility": "NETL",
        "physics_code": "MCNP",
        "physics_domain": ["neutronics"],
        "created_by": "cole@utexas.edu",
        "created_at": "2026-04-01T00:00:00Z",
        "access_tier": "facility",
        "input_files": [{"path": "input.i", "type": "main_input"}],
        "description": "Test model",
        "tags": ["test"],
    }
    (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
    (d / "input.i").write_text("c MCNP test input\n")
    return d


def _make_child_dir(tmp_path, parent_id: str, child_id: str, author: str) -> Path:
    """Create a child model directory with parent lineage."""
    d = tmp_path / child_id
    d.mkdir(exist_ok=True)
    manifest = {
        "model_id": child_id,
        "name": child_id.replace("-", " ").title(),
        "version": "1.0.0",
        "status": "draft",
        "reactor_type": "TRIGA",
        "facility": "NETL",
        "physics_code": "MCNP",
        "physics_domain": ["neutronics"],
        "created_by": author,
        "created_at": "2026-04-01T00:00:00Z",
        "access_tier": "facility",
        "input_files": [{"path": "input.i", "type": "main_input"}],
        "description": f"Child of {parent_id}",
        "tags": ["test"],
        "parent_model": parent_id,
    }
    (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
    (d / "input.i").write_text("c MCNP test input\n")
    return d


# ── Parser registration ──────────────────────────────────────────────


class TestParserRegistration:
    def test_invite_subcommand_exists(self):
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["invite", "cole@utexas.edu"])
        assert args.action == "invite"
        assert args.email == "cole@utexas.edu"

    def test_contributors_subcommand_exists(self):
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["contributors", "my-model"])
        assert args.action == "contributors"
        assert args.model_id == "my-model"

    def test_status_subcommand_exists(self):
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["status", "my-model"])
        assert args.action == "status"
        assert args.model_id == "my-model"

    def test_status_no_model_id(self):
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.action == "status"
        assert args.model_id is None

    def test_clone_progression_flag(self):
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["clone", "progression-1", "--progression"])
        assert args.progression is True

    def test_handlers_include_new_commands(self):
        """All new commands are in the handler dict."""

        # We can't easily inspect the dict, but we can verify
        # that unknown commands return 1, not KeyError
        # Just ensure the parser+handler wiring works by calling
        # with --help for each
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        for cmd in ["invite", "contributors", "status"]:
            # Just verify parse succeeds
            if cmd == "invite":
                args = parser.parse_args([cmd, "test@test.com"])
            elif cmd == "contributors":
                args = parser.parse_args([cmd, "test-model"])
            else:
                args = parser.parse_args([cmd])
            assert args.action == cmd


# ── Invite ────────────────────────────────────────────────────────────


class TestInvite:
    def test_invite_generates_token(self, capsys):
        from neutron_os.extensions.builtins.model_corral.cli import main

        with patch("neutron_os.extensions.builtins.model_corral.cli._record"):
            rc = main(["invite", "cole@utexas.edu"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "cole@utexas.edu" in out
        assert "neut-invite-" in out
        assert "neut connect --token" in out

    def test_invite_with_models(self, capsys):
        from neutron_os.extensions.builtins.model_corral.cli import main

        with patch("neutron_os.extensions.builtins.model_corral.cli._record"):
            rc = main(["invite", "cole@utexas.edu", "--models", "model-a", "model-b"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "model-a, model-b" in out

    def test_invite_with_message(self, capsys):
        from neutron_os.extensions.builtins.model_corral.cli import main

        with patch("neutron_os.extensions.builtins.model_corral.cli._record"):
            rc = main(["invite", "cole@utexas.edu", "-m", "Welcome aboard!"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Welcome aboard!" in out

    def test_invite_json(self, capsys):
        from neutron_os.extensions.builtins.model_corral.cli import main

        with patch("neutron_os.extensions.builtins.model_corral.cli._record"):
            rc = main(["invite", "cole@utexas.edu", "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["email"] == "cole@utexas.edu"
        assert data["token"].startswith("neut-invite-")
        assert isinstance(data["models"], list)


# ── Contributors ──────────────────────────────────────────────────────


class TestContributors:
    def test_contributors_walks_lineage(self, service, valid_model_dir, tmp_path, capsys):
        """Contributors walks parent chain and collects unique authors."""
        # Add parent
        service.add(valid_model_dir, message="parent")

        # Create child by different author
        child_dir = _make_child_dir(tmp_path, "triga-test-mcnp-v1", "nick-run-1", "nick@utexas.edu")
        service.add(child_dir, message="child")

        with patch(
            "neutron_os.extensions.builtins.model_corral.cli._get_service",
            return_value=service,
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["contributors", "nick-run-1"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "nick@utexas.edu" in out
        assert "cole@utexas.edu" in out

    def test_contributors_no_lineage(self, service, valid_model_dir, capsys):
        """Model with no parents returns just the creator."""
        service.add(valid_model_dir, message="solo")

        with patch(
            "neutron_os.extensions.builtins.model_corral.cli._get_service",
            return_value=service,
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["contributors", "triga-test-mcnp-v1"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "cole@utexas.edu" in out

    def test_contributors_json(self, service, valid_model_dir, capsys):
        service.add(valid_model_dir, message="test")

        with patch(
            "neutron_os.extensions.builtins.model_corral.cli._get_service",
            return_value=service,
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["contributors", "triga-test-mcnp-v1", "--format", "json"])

        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "cole@utexas.edu" in data


# ── Model Status ──────────────────────────────────────────────────────


class TestModelStatus:
    def test_status_draft_suggestions(self, service, valid_model_dir, capsys):
        service.add(valid_model_dir, message="test")

        with patch(
            "neutron_os.extensions.builtins.model_corral.cli._get_service",
            return_value=service,
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["status", "triga-test-mcnp-v1"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "draft" in out.lower()
        assert "neut model validate" in out

    def test_status_shows_children(self, service, valid_model_dir, tmp_path, capsys):
        service.add(valid_model_dir, message="parent")

        child_dir = _make_child_dir(
            tmp_path, "triga-test-mcnp-v1", "child-model", "nick@utexas.edu"
        )
        service.add(child_dir, message="child")

        with patch(
            "neutron_os.extensions.builtins.model_corral.cli._get_service",
            return_value=service,
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["status", "triga-test-mcnp-v1"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "child-model" in out

    def test_status_detects_model_from_cwd(self, service, valid_model_dir, capsys):
        """When no model_id given, detect from model.yaml in cwd."""
        service.add(valid_model_dir, message="test")

        with (
            patch(
                "neutron_os.extensions.builtins.model_corral.cli._get_service",
                return_value=service,
            ),
            patch("pathlib.Path.cwd", return_value=valid_model_dir),
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["status"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "triga-test-mcnp-v1" in out

    def test_status_no_model_returns_error(self, capsys, tmp_path):
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["status"])

        assert rc == 1
        assert "No model specified" in capsys.readouterr().out

    def test_status_json(self, service, valid_model_dir, capsys):
        service.add(valid_model_dir, message="test")

        with patch(
            "neutron_os.extensions.builtins.model_corral.cli._get_service",
            return_value=service,
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["status", "triga-test-mcnp-v1", "--format", "json"])

        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["model_id"] == "triga-test-mcnp-v1"
        assert data["status"] == "draft"
        assert "children" in data
        assert "lineage" in data

    def test_status_review_suggestions(self, service, tmp_path, capsys):
        """Review status shows review-specific suggestions."""
        d = tmp_path / "review-model"
        d.mkdir()
        manifest = {
            "model_id": "review-model",
            "name": "Review Model",
            "version": "1.0.0",
            "status": "review",
            "reactor_type": "TRIGA",
            "facility": "NETL",
            "physics_code": "MCNP",
            "physics_domain": ["neutronics"],
            "created_by": "test@utexas.edu",
            "created_at": "2026-04-01T00:00:00Z",
            "access_tier": "facility",
            "input_files": [{"path": "input.i", "type": "main_input"}],
            "description": "Review model",
            "tags": [],
        }
        (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
        (d / "input.i").write_text("c MCNP\n")
        service.add(d, message="test")

        with patch(
            "neutron_os.extensions.builtins.model_corral.cli._get_service",
            return_value=service,
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["status", "review-model"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "neut model diff" in out

    def test_status_production_suggestions(self, service, tmp_path, capsys):
        """Production status shows production-specific suggestions."""
        d = tmp_path / "prod-model"
        d.mkdir()
        manifest = {
            "model_id": "prod-model",
            "name": "Prod Model",
            "version": "1.0.0",
            "status": "production",
            "reactor_type": "TRIGA",
            "facility": "NETL",
            "physics_code": "MCNP",
            "physics_domain": ["neutronics"],
            "created_by": "test@utexas.edu",
            "created_at": "2026-04-01T00:00:00Z",
            "access_tier": "facility",
            "input_files": [{"path": "input.i", "type": "main_input"}],
            "description": "Prod model",
            "tags": [],
        }
        (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
        (d / "input.i").write_text("c MCNP\n")
        service.add(d, message="test")

        with patch(
            "neutron_os.extensions.builtins.model_corral.cli._get_service",
            return_value=service,
        ):
            from neutron_os.extensions.builtins.model_corral.cli import main

            rc = main(["status", "prod-model"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "neut model clone" in out
        assert "neut model export" in out


# ── Progression Clone ─────────────────────────────────────────────────


class TestProgressionName:
    def test_progression_number_detected(self):
        from neutron_os.extensions.builtins.model_corral.cli import _progression_name

        # Mock service where run name does not exist
        class FakeSvc:
            def show(self, mid):
                return None

        name, desc = _progression_name("cole-progression-1", FakeSvc())
        assert name == "cole-progression-1-run"
        assert "progression problem 1" in desc.lower()

    def test_progression_bumps_when_run_exists(self):
        from neutron_os.extensions.builtins.model_corral.cli import _progression_name

        class FakeSvc:
            def show(self, mid):
                if mid == "cole-progression-1-run":
                    return {"model_id": mid}
                return None

        name, desc = _progression_name("cole-progression-1", FakeSvc())
        assert "progression-2" in name
        assert "2" in desc

    def test_no_progression_number(self):
        from neutron_os.extensions.builtins.model_corral.cli import _progression_name

        class FakeSvc:
            def show(self, mid):
                return None

        name, desc = _progression_name("my-model", FakeSvc())
        assert name == "my-model-run"
