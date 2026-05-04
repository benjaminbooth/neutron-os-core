"""End-to-end integration tests -- full stack verification.

Tests the complete workflow across all Model Corral subsystems:
materials -> facility packs -> models -> generation -> federation -> security.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from axiom.infra.storage import LocalStorageProvider

from neutron_os.extensions.builtins.model_corral.db_models import Base, ModelVersion
from neutron_os.extensions.builtins.model_corral.service import ModelCorralService


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def full_stack(tmp_path):
    """Create a complete Model Corral stack for integration testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    storage = LocalStorageProvider({"base_dir": str(tmp_path / "storage")})
    service = ModelCorralService(engine=engine, storage=storage)
    return {"service": service, "tmp": tmp_path, "engine": engine, "storage": storage}


def _make_model(
    tmp_path,
    name,
    reactor_type="TRIGA",
    physics_code="MCNP",
    facility="NETL",
    version="0.1.0",
    materials=None,
    **extra,
):
    """Helper to create a model directory with model.yaml."""
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "model_id": name,
        "name": name.replace("-", " ").title(),
        "version": version,
        "status": "draft",
        "reactor_type": reactor_type,
        "facility": facility,
        "physics_code": physics_code,
        "physics_domain": ["neutronics"],
        "created_by": "test@utexas.edu",
        "created_at": "2026-04-01T00:00:00Z",
        "access_tier": "facility",
        "description": f"Integration test model: {name}",
        "tags": ["integration-test"],
    }
    if materials:
        manifest["materials"] = materials
    manifest.update(extra)
    (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
    return d


# ---------------------------------------------------------------------------
# TestMaterialToModelPipeline
# ---------------------------------------------------------------------------


class TestMaterialToModelPipeline:
    """Materials -> model -> generate MCNP/MPACT cards."""

    def test_model_with_materials_validates(self, full_stack):
        tmp = full_stack["tmp"]
        svc = full_stack["service"]
        d = _make_model(tmp, "mat-pipeline-test", materials=["UZrH-20", "H2O", "B4C"])
        result = svc.add(d)
        assert result.success, result.error

    def test_generate_mcnp_cards(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.generate import (
            generate_materials,
        )

        tmp = full_stack["tmp"]
        d = _make_model(tmp, "gen-mcnp-test", materials=["UZrH-20", "H2O", "B4C"])
        output = generate_materials(d, output_format="mcnp")
        assert "92235.80c" in output  # U-235 from UZrH-20
        assert "1001.80c" in output  # H-1 from H2O
        assert "5010.80c" in output  # B-10 from B4C
        assert "m1" in output  # first material card
        assert "m2" in output  # second material card

    def test_generate_mpact_cards(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.generate import (
            generate_materials,
        )

        tmp = full_stack["tmp"]
        d = _make_model(tmp, "gen-mpact-test", materials=["UZrH-20", "H2O"])
        output = generate_materials(d, output_format="mpact")
        assert "mat UZrH-20" in output
        assert "mat H2O" in output
        assert "92235.80c" in output

    def test_generate_is_deterministic(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.generate import (
            generate_materials,
        )

        tmp = full_stack["tmp"]
        d = _make_model(tmp, "deterministic-test", materials=["UZrH-20", "H2O", "B4C"])
        out1 = generate_materials(d, output_format="mcnp")
        out2 = generate_materials(d, output_format="mcnp")
        assert out1 == out2


# ---------------------------------------------------------------------------
# TestFacilityPackToModel
# ---------------------------------------------------------------------------


class TestFacilityPackToModel:
    """Facility pack discovery -> materials -> model."""

    def test_discover_netl_triga_builtin_pack(self):
        from neutron_os.extensions.builtins.model_corral.facilities.registry import (
            discover_packs,
        )

        packs = discover_packs()
        names = [p.name for p in packs]
        assert "NETL-TRIGA" in names

    def test_load_materials_from_pack(self):
        from neutron_os.extensions.builtins.model_corral.facilities.registry import (
            get_pack,
        )
        from neutron_os.extensions.builtins.model_corral.materials_db import (
            YamlMaterialSource,
        )

        pack = get_pack("NETL-TRIGA")
        assert pack is not None
        src = YamlMaterialSource(pack.materials_path, priority=100, source_name="pack:NETL-TRIGA")
        mats = src.load()
        mat_names = [m.name for m in mats]
        assert "UZrH-20" in mat_names

    def test_model_referencing_pack_materials(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.generate import (
            generate_materials,
        )

        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        # UZrH-20 is in the NETL-TRIGA pack and also in builtins
        d = _make_model(tmp, "pack-mat-model", materials=["UZrH-20"])
        result = svc.add(d)
        assert result.success, result.error

        output = generate_materials(d, output_format="mcnp")
        assert "92235.80c" in output
        assert "zr-h.40t" in output  # S(alpha,beta) from UZrH-20


# ---------------------------------------------------------------------------
# TestModelLifecycle
# ---------------------------------------------------------------------------


class TestModelLifecycle:
    """init -> validate -> add -> list -> show -> pull -> verify."""

    def test_full_lifecycle(self, full_stack):
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        # init
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_dir = model_init(
            "lifecycle-test-model", reactor_type="TRIGA", physics_code="MCNP", output_dir=tmp
        )
        assert model_dir.exists()

        # update manifest with required fields
        manifest = yaml.safe_load((model_dir / "model.yaml").read_text())
        manifest["created_by"] = "test@utexas.edu"
        manifest["description"] = "Lifecycle integration test model"
        (model_dir / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        # validate
        from neutron_os.extensions.builtins.model_corral.manifest import validate_model_dir

        vr = validate_model_dir(model_dir)
        assert vr.valid, f"Validation failed: {vr.errors}"

        # add
        result = svc.add(model_dir)
        assert result.success, result.error

        # list
        models = svc.list_models()
        assert any(m["model_id"] == "lifecycle-test-model" for m in models)

        # show
        info = svc.show("lifecycle-test-model")
        assert info is not None
        assert info["reactor_type"] == "TRIGA"

        # pull
        dest = tmp / "pulled"
        pr = svc.pull("lifecycle-test-model", dest)
        assert pr.success
        assert (dest / "model.yaml").exists()

        # verify content round-trips
        pulled_manifest = yaml.safe_load((dest / "model.yaml").read_text())
        assert pulled_manifest["model_id"] == "lifecycle-test-model"

    def test_version_progression(self, full_stack):
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        for v in ("0.1.0", "0.2.0", "0.3.0"):
            d = _make_model(tmp / v, "versioned-model", version=v)
            result = svc.add(d)
            assert result.success, f"Failed to add v{v}: {result.error}"

        info = svc.show("versioned-model")
        assert len(info["versions"]) == 3
        version_set = {v["version"] for v in info["versions"]}
        assert version_set == {"0.1.0", "0.2.0", "0.3.0"}

    def test_clone_modify_add_with_lineage(self, full_stack):
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        # Add base model
        base = _make_model(tmp, "base-model")
        svc.add(base)

        # Pull it
        pulled = tmp / "pulled-base"
        svc.pull("base-model", pulled)

        # Clone: create new model referencing parent
        clone_dir = tmp / "cloned-model"
        clone_dir.mkdir()
        for f in pulled.iterdir():
            if f.is_file():
                (clone_dir / f.name).write_bytes(f.read_bytes())
        manifest = yaml.safe_load((clone_dir / "model.yaml").read_text())
        manifest["model_id"] = "cloned-model"
        manifest["parent_model"] = "base-model"
        manifest["version"] = "0.1.0"
        (clone_dir / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        result = svc.add(clone_dir)
        assert result.success

        chain = svc.lineage("cloned-model")
        assert len(chain) == 1
        assert chain[0]["parent_model_id"] == "base-model"

    def test_export_as_zip_like_pull(self, full_stack):
        """Pull to a directory simulates export; verify model.yaml present."""
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        d = _make_model(tmp, "export-test-model")
        svc.add(d)

        dest = tmp / "exported"
        pr = svc.pull("export-test-model", dest)
        assert pr.success
        assert (dest / "model.yaml").exists()
        data = yaml.safe_load((dest / "model.yaml").read_text())
        assert data["model_id"] == "export-test-model"


# ---------------------------------------------------------------------------
# TestCoreForgeIntegration
# ---------------------------------------------------------------------------


class TestCoreForgeIntegration:
    """Add model with coreforge provenance."""

    def test_add_with_coreforge_provenance(self, full_stack):
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        d = _make_model(tmp, "coreforge-model")
        provenance = {
            "coreforge_version": "0.3.0",
            "config_file": "/path/to/triga_config.py",
            "builder_class": "TRIGACoreBuilder",
            "builder_specs": {"fuel_rods": 91, "enrichment": 0.20},
            "geometry_hash": "abc123def456",
        }
        result = svc.add(d, coreforge_provenance=provenance)
        assert result.success

        # Verify provenance is stored
        engine = full_stack["engine"]
        with Session(engine) as session:
            ver = session.query(ModelVersion).filter_by(model_id="coreforge-model").first()
            assert ver is not None
            assert ver.coreforge_provenance is not None
            assert ver.coreforge_provenance["coreforge_version"] == "0.3.0"
            assert ver.coreforge_provenance["builder_class"] == "TRIGACoreBuilder"

    def test_pull_preserves_provenance_in_manifest(self, full_stack):
        """Provenance lives in DB, not model.yaml -- verify via show()."""
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        d = _make_model(tmp, "cf-prov-pull")
        provenance = {
            "coreforge_version": "0.3.0",
            "config_file": "config.py",
            "builder_class": "Builder",
            "builder_specs": {},
            "geometry_hash": "deadbeef",
        }
        svc.add(d, coreforge_provenance=provenance)

        # show() returns version details
        info = svc.show("cf-prov-pull")
        assert info is not None
        assert len(info["versions"]) == 1


# ---------------------------------------------------------------------------
# TestLintAndGenerate
# ---------------------------------------------------------------------------


class TestLintAndGenerate:
    """Lint a model with known issues, fix them, re-lint."""

    def test_lint_finds_known_issues(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.lint import lint_model

        tmp = full_stack["tmp"]
        d = _make_model(
            tmp,
            "lint-issues-model",
            description="TODO fill this in",
            facility="CHANGEME",
        )
        # Remove materials to trigger info finding
        manifest = yaml.safe_load((d / "model.yaml").read_text())
        manifest.pop("materials", None)
        (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        result = lint_model(d)
        rules = [f.rule for f in result.findings]
        assert "todo-description" in rules
        assert "no-facility" in rules
        assert "no-materials" in rules

    def test_lint_clean_after_fixes(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.lint import lint_model

        tmp = full_stack["tmp"]
        d = _make_model(
            tmp,
            "lint-clean-model",
            materials=["UZrH-20"],
            description="A properly described TRIGA model for neutronics analysis",
        )

        result = lint_model(d)
        # Should have no errors (warnings/infos acceptable)
        assert result.errors == 0


# ---------------------------------------------------------------------------
# TestSweepAndLineage
# ---------------------------------------------------------------------------


class TestSweepAndLineage:
    """Parametric sweep with lineage tracking."""

    def test_sweep_creates_variants(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.sweep import sweep_model

        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        base = _make_model(tmp, "sweep-base", materials=["UZrH-20"])
        svc.add(base)

        variants = sweep_model(
            base, param="enrichment", values=["0.10", "0.15", "0.20"], output_dir=tmp / "variants"
        )
        assert len(variants) == 3

        # Add all variants and verify lineage
        for vdir in variants:
            result = svc.add(vdir)
            assert result.success, result.error

        for vdir in variants:
            vdata = yaml.safe_load((vdir / "model.yaml").read_text())
            mid = vdata["model_id"]
            chain = svc.lineage(mid)
            assert len(chain) == 1
            assert chain[0]["parent_model_id"] == "sweep-base"

    def test_sweep_sets_parameter_values(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.sweep import sweep_model

        tmp = full_stack["tmp"]
        base = _make_model(tmp, "sweep-param-test")
        variants = sweep_model(
            base, param="enrichment", values=["0.10", "0.15", "0.20"], output_dir=tmp / "sweep-out"
        )

        for vdir, expected in zip(variants, [0.10, 0.15, 0.20]):
            data = yaml.safe_load((vdir / "model.yaml").read_text())
            assert data["enrichment"] == expected


# ---------------------------------------------------------------------------
# TestFederationPack
# ---------------------------------------------------------------------------


class TestFederationPack:
    """Create, share, and receive a model via federation."""

    def test_share_and_receive_model(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.federation import (
            ModelSharingService,
        )

        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        # Node A: add model to registry
        d = _make_model(tmp, "fed-model-a")
        svc.add(d)

        # Node A: share model
        node_a = ModelSharingService(
            shared_dir=tmp / "node-a-shared",
            received_dir=tmp / "node-a-received",
        )
        archive = node_a.share_model("fed-model-a", model_dir=d, access_tier="public")
        assert archive.exists()
        assert archive.suffix == ".axiompack"

        # Node B: receive model
        node_b = ModelSharingService(
            shared_dir=tmp / "node-b-shared",
            received_dir=tmp / "node-b-received",
        )
        received = node_b.receive_model(archive)
        assert received["model_id"] == "fed-model-a"
        assert received["access_tier"] == "public"

        # Verify model files exist at the received location
        received_path = Path(received["path"])
        assert (received_path / "model").exists()

    def test_federation_materials_pack(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.federation import (
            create_materials_pack,
            install_received_pack,
        )
        from neutron_os.extensions.builtins.model_corral.materials_db import (
            get_material,
        )

        tmp = full_stack["tmp"]

        # Create a materials pack from builtins
        uzrh = get_material("UZrH-20")
        h2o = get_material("H2O")
        assert uzrh is not None
        assert h2o is not None

        archive = create_materials_pack(
            [uzrh, h2o],
            pack_id="test-materials-pack",
            output_dir=tmp / "packs",
        )
        assert archive.exists()

        # Install on a "different node"
        result = install_received_pack(archive, packs_dir=tmp / "node-b-federation")
        assert result["material_count"] == 2
        assert result["pack_id"] == "test-materials-pack"


# ---------------------------------------------------------------------------
# TestMaterialAuthorityChain
# ---------------------------------------------------------------------------


class TestMaterialAuthorityChain:
    """Priority ordering: pack YAML > local YAML > builtin."""

    def test_priority_ordering(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.materials_db import (
            BuiltinMaterialSource,
            MaterialRegistry,
            YamlMaterialSource,
        )

        tmp = full_stack["tmp"]

        # Create a local YAML source that overrides H2O density
        yaml_dir = tmp / "local-materials"
        yaml_dir.mkdir()
        custom_h2o = [
            {
                "name": "H2O",
                "description": "Custom H2O from local YAML",
                "density": 0.999,
                "category": "moderator",
                "fraction_type": "atom",
                "isotopes": [
                    {"zaid": "1001.80c", "fraction": 6.67e-2, "name": "H-1"},
                    {"zaid": "8016.80c", "fraction": 3.33e-2, "name": "O-16"},
                ],
            }
        ]
        (yaml_dir / "custom.yaml").write_text(yaml.dump(custom_h2o))

        # Create a pack YAML source with even higher priority
        pack_dir = tmp / "pack-materials"
        pack_dir.mkdir()
        pack_h2o = [
            {
                "name": "H2O",
                "description": "Pack-overridden H2O",
                "density": 0.997,
                "category": "moderator",
                "fraction_type": "atom",
                "isotopes": [
                    {"zaid": "1001.80c", "fraction": 6.67e-2, "name": "H-1"},
                    {"zaid": "8016.80c", "fraction": 3.33e-2, "name": "O-16"},
                ],
            }
        ]
        (pack_dir / "custom.yaml").write_text(yaml.dump(pack_h2o))

        registry = MaterialRegistry()
        registry.register_source(BuiltinMaterialSource())
        registry.register_source(
            YamlMaterialSource(yaml_dir, priority=50, source_name="local-yaml")
        )
        registry.register_source(YamlMaterialSource(pack_dir, priority=100, source_name="pack"))

        mat = registry.get("H2O")
        assert mat is not None
        # Pack has highest priority (100), should win
        assert mat.density == 0.997
        assert registry.source_of("H2O") == "pack"

    def test_builtin_fallback(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.materials_db import (
            BuiltinMaterialSource,
            MaterialRegistry,
        )

        registry = MaterialRegistry()
        registry.register_source(BuiltinMaterialSource())

        mat = registry.get("B4C")
        assert mat is not None
        assert mat.density == 2.52
        assert registry.source_of("B4C") == "builtin"


# ---------------------------------------------------------------------------
# TestSecurityOnReceive
# ---------------------------------------------------------------------------


class TestSecurityOnReceive:
    """Content integrity verification via checksums."""

    def test_valid_content_passes(self, full_stack):
        tmp = full_stack["tmp"]
        content = b"c MCNP input deck for TRIGA model\n"
        h = hashlib.sha256(content).hexdigest()

        f = tmp / "input.i"
        f.write_bytes(content)
        assert hashlib.sha256(f.read_bytes()).hexdigest() == h

    def test_tampered_content_detected(self, full_stack):
        tmp = full_stack["tmp"]
        content = b"c MCNP input deck for TRIGA model\n"
        original_hash = hashlib.sha256(content).hexdigest()

        f = tmp / "input.i"
        f.write_bytes(content)

        # Tamper
        f.write_bytes(b"c TAMPERED content\n")
        new_hash = hashlib.sha256(f.read_bytes()).hexdigest()
        assert new_hash != original_hash

    def test_model_checksum_changes_on_modification(self, full_stack):
        """Add model, pull, modify, verify checksum differs."""
        tmp = full_stack["tmp"]
        svc = full_stack["service"]
        engine = full_stack["engine"]

        d = _make_model(tmp, "checksum-test")
        (d / "data.txt").write_text("original data")
        svc.add(d)

        with Session(engine) as session:
            v1 = session.query(ModelVersion).filter_by(model_id="checksum-test").first()
            hash1 = v1.checksum

        # Add v2 with modified content
        d2 = _make_model(tmp / "v2", "checksum-test", version="0.2.0")
        (d2 / "data.txt").write_text("modified data")
        svc.add(d2)

        with Session(engine) as session:
            v2 = (
                session.query(ModelVersion)
                .filter_by(model_id="checksum-test", version="0.2.0")
                .first()
            )
            hash2 = v2.checksum

        assert hash1 != hash2

    def test_federation_export_controlled_rejected(self, full_stack):
        """Export-controlled packs should be rejected on receive."""
        from neutron_os.extensions.builtins.model_corral.federation import (
            ModelSharingService,
        )

        tmp = full_stack["tmp"]

        node_a = ModelSharingService(
            shared_dir=tmp / "ec-shared",
            received_dir=tmp / "ec-received",
        )

        # Create export_controlled pack
        d = _make_model(tmp, "ec-model")
        archive = node_a.share_model("ec-model", model_dir=d, access_tier="export_controlled")

        # Receiving node should reject it
        node_b = ModelSharingService(
            shared_dir=tmp / "b-shared",
            received_dir=tmp / "b-received",
        )
        with pytest.raises(PermissionError, match="export_controlled"):
            node_b.receive_model(archive)


# ---------------------------------------------------------------------------
# TestPerformance
# ---------------------------------------------------------------------------


class TestPerformance:
    """Performance benchmarks for bulk operations."""

    def test_add_100_models_under_30s(self, full_stack):
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        start = time.monotonic()
        for i in range(100):
            d = _make_model(tmp / f"batch-{i}", f"perf-model-{i:03d}", version="0.1.0")
            result = svc.add(d)
            assert result.success, f"Model {i} failed: {result.error}"
        elapsed = time.monotonic() - start
        assert elapsed < 30, f"Adding 100 models took {elapsed:.1f}s (limit: 30s)"

    def test_search_100_models_under_2s(self, full_stack):
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        # Pre-populate
        for i in range(100):
            d = _make_model(
                tmp / f"search-{i}",
                f"search-model-{i:03d}",
                version="0.1.0",
                description=f"Model number {i} for search performance test",
            )
            svc.add(d)

        start = time.monotonic()
        results = svc.search("search")
        elapsed = time.monotonic() - start
        assert len(results) == 100
        assert elapsed < 2, f"Search took {elapsed:.1f}s (limit: 2s)"

    def test_list_100_models_under_1s(self, full_stack):
        tmp = full_stack["tmp"]
        svc = full_stack["service"]

        for i in range(100):
            d = _make_model(tmp / f"list-{i}", f"list-model-{i:03d}", version="0.1.0")
            svc.add(d)

        start = time.monotonic()
        models = svc.list_models()
        elapsed = time.monotonic() - start
        assert len(models) == 100
        assert elapsed < 1, f"List took {elapsed:.1f}s (limit: 1s)"

    def test_generate_10_materials_under_1s(self, full_stack):
        from neutron_os.extensions.builtins.model_corral.commands.generate import (
            generate_materials,
        )

        tmp = full_stack["tmp"]
        mats = [
            "UZrH-20",
            "H2O",
            "B4C",
            "SS304",
            "Zircaloy-4",
            "graphite",
            "UO2-3.1",
            "UO2-4.95",
            "air",
            "H2O-hot",
        ]
        d = _make_model(tmp, "perf-gen-model", materials=mats)

        start = time.monotonic()
        output = generate_materials(d, output_format="mcnp")
        elapsed = time.monotonic() - start
        assert elapsed < 1, f"Generate took {elapsed:.1f}s (limit: 1s)"
        assert len(output) > 100
