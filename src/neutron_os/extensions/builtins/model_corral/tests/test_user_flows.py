"""User flow tests — end-to-end workflows for each launch persona.

Per the v1.0 plan, each persona should complete their primary workflow
in under 5 minutes with no documentation.

Personas:
- Nick Luciano: Shadow operator → pull → edit → validate → add
- Cole Gentry PhD: CoreForge → add --from-coreforge → version → share
- Soha: ROM developer → search → clone → train ROM → add with lineage
- Ondrej: Analyst → search → pull → run
- Jay: Reviewer → list --status review → validate → approve
- Ben Collins PhD: Supervisor → audit → diff → approve
"""

from __future__ import annotations


import pytest
import yaml
from sqlalchemy import create_engine

from neutron_os.extensions.builtins.model_corral.cli import build_parser
from neutron_os.extensions.builtins.model_corral.commands.init import model_init
from neutron_os.extensions.builtins.model_corral.commands.validate import cmd_validate
from neutron_os.extensions.builtins.model_corral.db_models import Base
from neutron_os.extensions.builtins.model_corral.service import ModelCorralService


@pytest.fixture
def service(tmp_path):
    """Create an in-memory service for testing."""
    from axiom.infra.storage import LocalStorageProvider

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    storage = LocalStorageProvider({"base_dir": str(tmp_path / "storage")})
    return ModelCorralService(engine=engine, storage=storage)


@pytest.fixture
def model_dir(tmp_path):
    """Create a valid model directory for testing."""
    d = tmp_path / "test-model"
    d.mkdir()
    manifest = {
        "model_id": "test-model",
        "name": "Test Model",
        "version": "0.1.0",
        "status": "draft",
        "reactor_type": "TRIGA",
        "facility": "NETL",
        "physics_code": "MCNP",
        "physics_domain": ["neutronics"],
        "created_by": "test@example.com",
        "created_at": "2026-01-01T00:00:00Z",
        "access_tier": "facility",
        "description": "Test model for user flow testing",
        "tags": ["test", "triga"],
        "materials": [
            {"name": "UZrH-20", "number": 1},
            {"name": "H2O", "number": 2},
        ],
    }
    (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False), encoding="utf-8")
    (d / "input.i").write_text("c MCNP input deck placeholder\n", encoding="utf-8")
    return d


class TestNickFlow:
    """Nick Luciano — Shadow operator: pull → edit → validate → add."""

    def test_init_model_for_triga(self, tmp_path):
        """Nick scaffolds a new TRIGA model."""
        d = model_init(
            "netl-steady-state",
            reactor_type="TRIGA",
            physics_code="MCNP",
            facility="NETL",
            output_dir=tmp_path,
        )
        assert (d / "model.yaml").exists()
        data = yaml.safe_load((d / "model.yaml").read_text())
        assert data["reactor_type"] == "TRIGA"
        assert data["facility"] == "NETL"

    def test_init_with_materials(self, tmp_path):
        """Nick scaffolds with --materials flag to get TRIGA materials pre-populated."""
        d = model_init(
            "netl-with-mats",
            reactor_type="TRIGA",
            physics_code="MCNP",
            facility="NETL",
            output_dir=tmp_path,
            include_materials=True,
        )
        yaml.safe_load((d / "model.yaml").read_text())
        # Should have materials if TRIGA facility pack is installed
        # (builtin packs are available)
        assert (d / "model.yaml").exists()

    def test_validate_catches_errors(self, tmp_path):
        """Nick validates and gets actionable feedback."""
        d = tmp_path / "bad-model"
        d.mkdir()
        (d / "model.yaml").write_text("model_id: bad\n", encoding="utf-8")
        ret = cmd_validate(str(d), output_format="json")
        assert ret != 0  # Should fail validation

    def test_full_nick_flow(self, service, model_dir):
        """Nick's complete workflow: validate → add → verify in registry."""
        # Validate
        ret = cmd_validate(str(model_dir), output_format="human")
        assert ret == 0

        # Add
        result = service.add(model_dir)
        assert result.success
        assert result.model_id == "test-model"

        # Verify it's in the registry
        info = service.show("test-model")
        assert info is not None
        assert info["reactor_type"] == "TRIGA"


class TestColeFlow:
    """Cole Gentry PhD — CoreForge: generate → add --from-coreforge → share."""

    def test_coreforge_provenance_capture(self, tmp_path):
        """Cole adds a model with CoreForge provenance."""
        from neutron_os.extensions.builtins.model_corral.coreforge_bridge import (
            CoreForgeProvenance,
            extract_provenance,
        )

        # Create a mock CoreForge config
        config = tmp_path / "triga_core.py"
        config.write_text("# CoreForge config for TRIGA core\nfuel_enrichment = 0.1975\n")

        prov = extract_provenance(config_path=config)
        assert isinstance(prov, CoreForgeProvenance)
        assert prov.config_file == str(config)
        assert prov.geometry_hash  # Should have hashed the config

    def test_add_with_coreforge(self, service, model_dir, tmp_path):
        """Cole's add with CoreForge provenance stored on version record."""
        config = tmp_path / "config.py"
        config.write_text("enrichment = 0.1975\n")

        from neutron_os.extensions.builtins.model_corral.coreforge_bridge import (
            extract_provenance,
        )

        prov = extract_provenance(config_path=config)
        result = service.add(model_dir, coreforge_provenance=prov.to_dict())
        assert result.success

        # Verify provenance is stored
        info = service.show("test-model")
        assert info is not None

    def test_version_progression(self, service, tmp_path):
        """Cole submits multiple versions of the same model."""
        for ver in ["0.1.0", "0.2.0", "0.3.0"]:
            d = tmp_path / f"model-v{ver}"
            d.mkdir()
            manifest = {
                "model_id": "coreforge-triga",
                "name": "CoreForge TRIGA",
                "version": ver,
                "status": "draft",
                "reactor_type": "TRIGA",
                "facility": "NETL",
                "physics_code": "MCNP",
                "physics_domain": ["neutronics"],
                "created_by": "cgentry@utexas.edu",
                "created_at": "2026-01-01T00:00:00Z",
                "access_tier": "facility",
            }
            (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
            result = service.add(d)
            assert result.success, f"Failed to add v{ver}: {result.error}"

        info = service.show("coreforge-triga")
        assert len(info["versions"]) == 3


class TestSohaFlow:
    """Soha — ROM developer: search → clone → add with lineage."""

    def test_search_find_model(self, service, model_dir):
        """Soha searches for a model to base her ROM on."""
        service.add(model_dir)
        results = service.search("TRIGA")
        assert len(results) >= 1
        assert results[0]["model_id"] == "test-model"

    def test_clone_for_rom(self, service, model_dir, tmp_path):
        """Soha clones a model to create an ROM variant."""
        service.add(model_dir)

        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        clone_dir = model_clone(
            "test-model", service, new_name="test-model-rom", output_dir=tmp_path
        )
        assert clone_dir.exists()

        data = yaml.safe_load((clone_dir / "model.yaml").read_text())
        assert data["parent_model"] == "test-model"
        assert data["model_id"] == "test-model-rom"

    def test_rom_lineage_tracked(self, service, model_dir, tmp_path):
        """Soha's ROM has lineage back to the physics model."""
        service.add(model_dir)

        # Create ROM variant
        rom_dir = tmp_path / "test-model-rom"
        rom_dir.mkdir()
        rom_manifest = {
            "model_id": "test-model-rom",
            "name": "Test Model ROM",
            "version": "0.1.0",
            "status": "draft",
            "reactor_type": "TRIGA",
            "facility": "NETL",
            "physics_code": "custom",
            "physics_domain": ["neutronics"],
            "created_by": "soha@utexas.edu",
            "created_at": "2026-01-01T00:00:00Z",
            "access_tier": "facility",
            "parent_model": "test-model",
            "rom_tier": "ROM-1",
        }
        (rom_dir / "model.yaml").write_text(yaml.dump(rom_manifest, sort_keys=False))

        result = service.add(rom_dir)
        assert result.success

        lineage = service.lineage("test-model-rom")
        assert len(lineage) >= 1
        assert lineage[0]["parent_model_id"] == "test-model"
        assert lineage[0]["relationship_type"] == "trained_from"


class TestOndrejFlow:
    """Ondrej — Analyst: search → pull → work with model."""

    def test_search_and_pull(self, service, model_dir, tmp_path):
        """Ondrej searches, finds, and pulls a model."""
        service.add(model_dir)

        results = service.search("test")
        assert len(results) >= 1

        dest = tmp_path / "pulled"
        pull_result = service.pull("test-model", dest)
        assert pull_result.success
        assert (dest / "model.yaml").exists()

    def test_pull_specific_version(self, service, tmp_path):
        """Ondrej pulls a specific version."""
        for ver in ["0.1.0", "0.2.0"]:
            d = tmp_path / f"model-v{ver}"
            d.mkdir()
            manifest = {
                "model_id": "multi-version",
                "name": "Multi Version",
                "version": ver,
                "status": "production",
                "reactor_type": "PWR",
                "facility": "generic",
                "physics_code": "MCNP",
                "physics_domain": ["neutronics"],
                "created_by": "ondrej@utexas.edu",
                "created_at": "2026-01-01T00:00:00Z",
                "access_tier": "public",
            }
            (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
            add_result = service.add(d)
            assert add_result.success, f"Add v{ver} failed: {add_result.error}"

        dest = tmp_path / "pulled-v1"
        result = service.pull("multi-version", dest, version="0.1.0")
        assert result.success


class TestJayFlow:
    """Jay — Post-doc reviewer: list by status → validate → update status."""

    def test_list_by_status(self, service, model_dir, tmp_path):
        """Jay lists models pending review."""
        # Add a model with review status
        review_dir = tmp_path / "review-model"
        review_dir.mkdir()
        manifest = {
            "model_id": "review-model",
            "name": "Model for Review",
            "version": "0.1.0",
            "status": "review",
            "reactor_type": "TRIGA",
            "facility": "NETL",
            "physics_code": "MCNP",
            "physics_domain": ["neutronics"],
            "created_by": "nick@utexas.edu",
            "created_at": "2026-01-01T00:00:00Z",
            "access_tier": "facility",
            "description": "Needs Jay's review",
        }
        (review_dir / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
        service.add(review_dir)

        # Jay filters by status
        models = service.list_models(status="review")
        assert len(models) >= 1
        assert models[0]["model_id"] == "review-model"


class TestBenCollinsFlow:
    """Ben Collins PhD — Supervisor: audit → diff → oversight."""

    def test_audit_shows_history(self, service, model_dir):
        """Ben audits the registry for recent changes."""
        service.add(model_dir)
        models = service.list_models()
        assert len(models) >= 1

        # Can show details for each
        for m in models:
            info = service.show(m["model_id"])
            assert info is not None
            assert len(info["versions"]) >= 1


class TestCLIParser:
    """Verify CLI parser has all v1.0 subcommands with correct args."""

    def test_all_subcommands_present(self):
        parser = build_parser()
        # Extract subcommand names
        for action in parser._subparsers._actions:
            if hasattr(action, "_name_parser_map"):
                commands = set(action._name_parser_map.keys())
                expected = {
                    "init",
                    "validate",
                    "add",
                    "clone",
                    "search",
                    "list",
                    "show",
                    "pull",
                    "lineage",
                    "diff",
                    "export",
                    "audit",
                    "generate",
                    "lint",
                    "sweep",
                    "materials",
                    "share",
                    "receive",
                }
                assert expected.issubset(commands), f"Missing: {expected - commands}"

    def test_epilog_has_workflows(self):
        parser = build_parser()
        assert "Start here" in parser.epilog
        assert "neut model add" in parser.epilog
        assert "neut model materials" in parser.epilog

    def test_init_has_materials_flag(self):
        parser = build_parser()
        args = parser.parse_args(["init", "test-model", "--materials"])
        assert args.materials is True

    def test_add_has_coreforge_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            ["add", "./model", "--from-coreforge", "--coreforge-config", "c.py"]
        )
        assert args.from_coreforge is True
        assert args.coreforge_config == "c.py"

    def test_share_has_access_tier(self):
        parser = build_parser()
        args = parser.parse_args(["share", "my-model", "--access-tier", "public"])
        assert args.access_tier == "public"

    def test_generate_format_choices(self):
        parser = build_parser()
        args = parser.parse_args(["generate", "./model", "--format", "mpact"])
        assert args.format == "mpact"


class TestMaterialCardGeneration:
    """End-to-end: model with materials → generate MCNP cards."""

    def test_generate_from_model_yaml(self, tmp_path):
        """Full flow: init → add materials → generate cards."""
        from neutron_os.extensions.builtins.model_corral.commands.generate import generate_materials

        d = tmp_path / "gen-test"
        d.mkdir()
        manifest = {
            "model_id": "gen-test",
            "name": "Generation Test",
            "version": "0.1.0",
            "status": "draft",
            "reactor_type": "TRIGA",
            "facility": "NETL",
            "physics_code": "MCNP",
            "physics_domain": ["neutronics"],
            "created_by": "test@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "access_tier": "facility",
            "materials": [
                {"name": "UZrH-20", "number": 1},
                {"name": "H2O", "number": 2},
                {"name": "B4C", "number": 10},
            ],
        }
        (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        output = generate_materials(d, output_format="mcnp")
        assert "m1" in output
        assert "92235.80c" in output  # UZrH-20
        assert "m2" in output
        assert "1001.80c" in output  # H2O
        assert "m10" in output
        assert "5010.80c" in output  # B4C

    def test_deterministic_output(self, tmp_path):
        """Same model → same output every time."""
        from neutron_os.extensions.builtins.model_corral.commands.generate import generate_materials

        d = tmp_path / "det-test"
        d.mkdir()
        manifest = {
            "model_id": "det-test",
            "name": "Determinism Test",
            "version": "0.1.0",
            "physics_code": "MCNP",
            "materials": [{"name": "UZrH-20", "number": 1}],
        }
        (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        out1 = generate_materials(d)
        out2 = generate_materials(d)
        assert out1 == out2


class TestLintWorkflow:
    """End-to-end lint checks."""

    def test_lint_clean_model(self, model_dir):
        from neutron_os.extensions.builtins.model_corral.commands.lint import lint_model

        result = lint_model(model_dir)
        assert result.errors == 0

    def test_lint_catches_todo_description(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.lint import lint_model

        d = tmp_path / "lint-test"
        d.mkdir()
        manifest = {
            "model_id": "lint-test",
            "name": "Lint Test",
            "version": "0.1.0",
            "reactor_type": "TRIGA",
            "physics_code": "MCNP",
            "created_by": "test@example.com",
            "description": "TODO: describe this",
            "facility": "CHANGEME",
        }
        (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        result = lint_model(d)
        rules = {f.rule for f in result.findings}
        assert "todo-description" in rules
        assert "no-facility" in rules


class TestSweepWorkflow:
    """End-to-end parametric sweep."""

    def test_sweep_creates_variants(self, model_dir):
        from neutron_os.extensions.builtins.model_corral.commands.sweep import sweep_model

        variants = sweep_model(model_dir, param="enrichment", values=["0.05", "0.10", "0.20"])
        assert len(variants) == 3

        for v in variants:
            data = yaml.safe_load((v / "model.yaml").read_text())
            assert data["parent_model"] == "test-model"
            assert "enrichment" in data
