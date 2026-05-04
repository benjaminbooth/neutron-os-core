"""Tests for Model Corral federation integration."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest
import yaml

from neutron_os.extensions.builtins.model_corral.federation import (
    FederationPackSource,
    ModelSharingService,
    create_facility_pack_archive,
    create_materials_pack,
    install_received_pack,
    list_federation_materials,
)
from neutron_os.extensions.builtins.model_corral.materials_db import (
    Isotope,
    MaterialDef,
    MaterialRegistry,
    MaterialSource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_materials() -> list[MaterialDef]:
    return [
        MaterialDef(
            name="TestFuel",
            description="Test fuel material",
            density=10.0,
            category="fuel",
            fraction_type="atom",
            source="test",
            isotopes=(
                Isotope("92235.80c", 0.05, "U-235"),
                Isotope("92238.80c", 0.95, "U-238"),
            ),
        ),
        MaterialDef(
            name="TestModerator",
            description="Test moderator",
            density=1.0,
            category="moderator",
            source="test",
        ),
    ]


@pytest.fixture()
def sample_materials() -> list[MaterialDef]:
    return _make_materials()


@pytest.fixture()
def federation_dir(tmp_path: Path) -> Path:
    """A federation packs directory with one installed pack."""
    fed_dir = tmp_path / "federation-packs"
    pack_dir = fed_dir / "test-pack"
    mat_dir = pack_dir / "materials"
    mat_dir.mkdir(parents=True)

    mats = [
        {
            "name": "FedMat",
            "description": "Federated material",
            "density": 5.0,
            "category": "fuel",
            "fraction_type": "atom",
            "isotopes": [{"zaid": "92235.80c", "fraction": 0.1, "name": "U-235"}],
        },
    ]
    (mat_dir / "materials.yaml").write_text(yaml.dump(mats), encoding="utf-8")

    meta = {"pack_id": "test-pack", "pack_type": "materials", "access_tier": "public"}
    (pack_dir / "pack-meta.json").write_text(json.dumps(meta), encoding="utf-8")

    return fed_dir


# ---------------------------------------------------------------------------
# FederationPackSource — protocol compliance
# ---------------------------------------------------------------------------


def test_federation_pack_source_implements_material_source():
    src = FederationPackSource()
    assert isinstance(src, MaterialSource)


def test_federation_pack_source_priority():
    src = FederationPackSource()
    assert src.priority == 75


def test_federation_pack_source_name():
    src = FederationPackSource()
    assert src.name == "federation"


def test_federation_pack_source_loads_materials(federation_dir: Path):
    src = FederationPackSource(packs_dir=federation_dir)
    materials = src.load()
    assert len(materials) == 1
    assert materials[0].name == "FedMat"
    assert materials[0].density == 5.0


def test_federation_pack_source_empty_dir(tmp_path: Path):
    empty = tmp_path / "empty-fed"
    empty.mkdir()
    src = FederationPackSource(packs_dir=empty)
    assert src.load() == []


def test_federation_pack_source_nonexistent_dir(tmp_path: Path):
    src = FederationPackSource(packs_dir=tmp_path / "nonexistent")
    assert src.load() == []


# ---------------------------------------------------------------------------
# Access tier enforcement
# ---------------------------------------------------------------------------


def test_federation_source_blocks_export_controlled(tmp_path: Path):
    """Export-controlled packs should not load materials."""
    fed_dir = tmp_path / "federation-packs"
    pack_dir = fed_dir / "ec-pack"
    mat_dir = pack_dir / "materials"
    mat_dir.mkdir(parents=True)

    mats = [{"name": "SecretMat", "density": 99.0, "category": "fuel"}]
    (mat_dir / "materials.yaml").write_text(yaml.dump(mats), encoding="utf-8")

    meta = {"pack_id": "ec-pack", "access_tier": "export_controlled"}
    (pack_dir / "pack-meta.json").write_text(json.dumps(meta), encoding="utf-8")

    src = FederationPackSource(packs_dir=fed_dir)
    materials = src.load()
    assert len(materials) == 0


def test_install_received_pack_blocks_export_controlled(tmp_path: Path, sample_materials):
    """Installing an export_controlled pack should raise PermissionError."""
    archive = create_materials_pack(
        sample_materials,
        pack_id="ec-test",
        access_tier="export_controlled",
        output_dir=tmp_path / "out",
    )

    with pytest.raises(PermissionError, match="export_controlled"):
        install_received_pack(archive, packs_dir=tmp_path / "install")


# ---------------------------------------------------------------------------
# create_materials_pack
# ---------------------------------------------------------------------------


def test_create_materials_pack_produces_valid_archive(tmp_path: Path, sample_materials):
    archive = create_materials_pack(
        sample_materials,
        pack_id="my-materials",
        version="2.0.0",
        access_tier="public",
        output_dir=tmp_path,
    )
    assert archive.exists()
    assert archive.suffix == ".axiompack"
    assert "my-materials" in archive.name
    assert tarfile.is_tarfile(str(archive))

    # Verify contents
    with tarfile.open(str(archive), "r:gz") as tar:
        names = tar.getnames()
        assert any("pack-meta.json" in n for n in names)
        assert any("materials.yaml" in n for n in names)
        assert any("SHA256SUMS" in n for n in names)


def test_create_materials_pack_metadata(tmp_path: Path, sample_materials):
    archive = create_materials_pack(
        sample_materials,
        pack_id="meta-test",
        version="1.2.3",
        access_tier="restricted",
        output_dir=tmp_path,
    )

    # Extract and check metadata
    with tarfile.open(str(archive), "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith("pack-meta.json"):
                f = tar.extractfile(member)
                meta = json.loads(f.read())
                assert meta["pack_id"] == "meta-test"
                assert meta["version"] == "1.2.3"
                assert meta["access_tier"] == "restricted"
                assert meta["material_count"] == 2
                break


def test_create_materials_pack_invalid_tier(tmp_path: Path, sample_materials):
    with pytest.raises(ValueError, match="Invalid access_tier"):
        create_materials_pack(
            sample_materials, pack_id="bad", access_tier="invalid", output_dir=tmp_path
        )


# ---------------------------------------------------------------------------
# install_received_pack
# ---------------------------------------------------------------------------


def test_install_received_pack_materials(tmp_path: Path, sample_materials):
    archive = create_materials_pack(
        sample_materials,
        pack_id="install-test",
        output_dir=tmp_path / "out",
    )

    install_dir = tmp_path / "install"
    result = install_received_pack(archive, packs_dir=install_dir)

    assert result["pack_id"] == "install-test"
    assert result["type"] == "materials"
    assert result["material_count"] == 2
    assert (install_dir / "install-test" / "materials" / "materials.yaml").exists()


def test_install_received_pack_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        install_received_pack(tmp_path / "nonexistent.axiompack")


# ---------------------------------------------------------------------------
# create_facility_pack_archive
# ---------------------------------------------------------------------------


def test_create_facility_pack_archive(tmp_path: Path):
    """Create a .facilitypack from a facility directory."""
    fac_dir = tmp_path / "MY-REACTOR"
    fac_dir.mkdir()
    (fac_dir / "materials").mkdir()
    (fac_dir / "templates").mkdir()
    (fac_dir / "parameters").mkdir()

    manifest = {
        "name": "MY-REACTOR",
        "display_name": "My Reactor",
        "reactor_type": "TRIGA",
        "version": "0.1.0",
        "maintainer": "test@test.com",
    }
    (fac_dir / "manifest.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False), encoding="utf-8"
    )

    output = tmp_path / "output"
    output.mkdir()
    archive = create_facility_pack_archive(fac_dir, output=output / "MY-REACTOR.facilitypack")

    assert archive.exists()
    assert tarfile.is_tarfile(str(archive))


def test_create_facility_pack_no_manifest(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="No manifest.yaml"):
        create_facility_pack_archive(empty)


# ---------------------------------------------------------------------------
# list_federation_materials
# ---------------------------------------------------------------------------


def test_list_federation_materials(federation_dir: Path):
    materials = list_federation_materials(packs_dir=federation_dir)
    assert len(materials) == 1
    assert materials[0]["name"] == "FedMat"
    assert materials[0]["source_pack"] == "test-pack"
    assert materials[0]["access_tier"] == "public"


def test_list_federation_materials_empty(tmp_path: Path):
    assert list_federation_materials(packs_dir=tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# ModelSharingService
# ---------------------------------------------------------------------------


def test_model_sharing_share_creates_pack(tmp_path: Path):
    svc = ModelSharingService(
        shared_dir=tmp_path / "shared",
        received_dir=tmp_path / "received",
    )

    model_dir = tmp_path / "my-model"
    model_dir.mkdir()
    (model_dir / "model.yaml").write_text("name: test-model\n", encoding="utf-8")

    archive = svc.share_model("test-model", model_dir=model_dir)
    assert archive.exists()
    assert archive.suffix == ".axiompack"


def test_model_sharing_receive_registers(tmp_path: Path):
    svc = ModelSharingService(
        shared_dir=tmp_path / "shared",
        received_dir=tmp_path / "received",
    )

    # Create a model pack first
    model_dir = tmp_path / "source-model"
    model_dir.mkdir()
    (model_dir / "model.yaml").write_text("name: source\n", encoding="utf-8")

    archive = svc.share_model("source-model", model_dir=model_dir)

    # Receive it
    result = svc.receive_model(archive)
    assert result["model_id"] == "source-model"
    assert Path(result["path"]).exists()
    assert result["access_tier"] == "public"


def test_model_sharing_list_shared(tmp_path: Path):
    svc = ModelSharingService(
        shared_dir=tmp_path / "shared",
        received_dir=tmp_path / "received",
    )

    assert svc.list_shared_models() == []

    svc.share_model("model-a")
    svc.share_model("model-b")

    shared = svc.list_shared_models()
    assert len(shared) == 2
    assert shared[0]["model_id"] == "model-a"
    assert shared[1]["model_id"] == "model-b"


def test_model_sharing_receive_not_found(tmp_path: Path):
    svc = ModelSharingService(
        shared_dir=tmp_path / "shared",
        received_dir=tmp_path / "received",
    )
    with pytest.raises(FileNotFoundError):
        svc.receive_model(tmp_path / "nonexistent.axiompack")


def test_model_sharing_export_controlled_blocked(tmp_path: Path):
    svc = ModelSharingService(
        shared_dir=tmp_path / "shared",
        received_dir=tmp_path / "received",
    )

    archive = svc.share_model("ec-model", access_tier="export_controlled")

    with pytest.raises(PermissionError, match="export_controlled"):
        svc.receive_model(archive)


# ---------------------------------------------------------------------------
# Federation materials appear in global registry
# ---------------------------------------------------------------------------


def test_federation_materials_in_registry(federation_dir: Path):
    """Federation materials merge into a MaterialRegistry."""
    reg = MaterialRegistry()
    fed_src = FederationPackSource(packs_dir=federation_dir)
    reg.register_source(fed_src)

    mat = reg.get("FedMat")
    assert mat is not None
    assert mat.density == 5.0
    assert "federation" in reg.source_of("FedMat")


# ---------------------------------------------------------------------------
# Round-trip: share -> receive -> materials available
# ---------------------------------------------------------------------------


def test_round_trip_share_receive_materials(tmp_path: Path):
    """Full round trip: create pack, install, load via FederationPackSource."""
    materials = _make_materials()

    # Create pack
    archive = create_materials_pack(
        materials,
        pack_id="round-trip",
        output_dir=tmp_path / "out",
    )

    # Install pack
    install_dir = tmp_path / "federation-packs"
    result = install_received_pack(archive, packs_dir=install_dir)
    assert result["material_count"] == 2

    # Load via FederationPackSource
    src = FederationPackSource(packs_dir=install_dir)
    loaded = src.load()
    names = {m.name for m in loaded}
    assert "TestFuel" in names
    assert "TestModerator" in names

    # Verify in registry
    reg = MaterialRegistry()
    reg.register_source(src)
    assert reg.get("TestFuel") is not None
    assert reg.get("TestFuel").density == 10.0
