"""Tests for the facility pack registry.

Covers manifest parsing, pack discovery, init/install/uninstall/publish
lifecycle, priority shadowing, serialization, and builtin pack integrity.
"""

from __future__ import annotations

import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from neutron_os.extensions.builtins.model_corral.facilities.registry import (
    FacilityManifest,
    InstalledPack,
    _builtin_packs_dir,
    discover_packs,
    get_pack,
    init_pack,
    install_pack,
    parse_manifest,
    publish_pack,
    uninstall_pack,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_MANIFEST = {
    "name": "test-reactor",
    "reactor_type": "PWR",
    "version": "0.1.0",
    "maintainer": "tester",
}


def _write_manifest(path: Path, data: dict) -> Path:
    """Write a manifest.yaml and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return path


def _make_pack_dir(base: Path, name: str, extra: dict | None = None) -> Path:
    """Create a minimal pack directory with manifest and subdirs."""
    pack_dir = base / name
    pack_dir.mkdir(parents=True, exist_ok=True)
    data = {**MINIMAL_MANIFEST, "name": name, **(extra or {})}
    _write_manifest(pack_dir / "manifest.yaml", data)
    for sub in ("materials", "templates", "parameters", "coreforge"):
        (pack_dir / sub).mkdir(exist_ok=True)
    return pack_dir


# ---------------------------------------------------------------------------
# 1. Manifest parsing
# ---------------------------------------------------------------------------


class TestParseManifest:
    """parse_manifest() on valid, missing-field, and invalid YAML."""

    def test_valid_manifest(self, tmp_path: Path) -> None:
        mf = tmp_path / "manifest.yaml"
        data = {**MINIMAL_MANIFEST, "description": "A test reactor", "tags": ["pwr"]}
        _write_manifest(mf, data)

        result = parse_manifest(mf)

        assert isinstance(result, FacilityManifest)
        assert result.name == "test-reactor"
        assert result.reactor_type == "PWR"
        assert result.version == "0.1.0"
        assert result.maintainer == "tester"
        assert result.description == "A test reactor"
        assert result.tags == ("pwr",)
        assert result.license == "CC-BY-4.0"  # default
        assert result.display_name == "test-reactor"  # falls back to name

    def test_display_name_override(self, tmp_path: Path) -> None:
        data = {**MINIMAL_MANIFEST, "display_name": "My Reactor"}
        _write_manifest(tmp_path / "manifest.yaml", data)
        result = parse_manifest(tmp_path / "manifest.yaml")
        assert result.display_name == "My Reactor"

    def test_missing_required_field(self, tmp_path: Path) -> None:
        incomplete = {"name": "broken", "reactor_type": "BWR"}
        _write_manifest(tmp_path / "manifest.yaml", incomplete)

        with pytest.raises(ValueError, match="Missing required fields"):
            parse_manifest(tmp_path / "manifest.yaml")

    def test_missing_multiple_fields(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path / "manifest.yaml", {"name": "x"})

        with pytest.raises(ValueError, match="reactor_type"):
            parse_manifest(tmp_path / "manifest.yaml")

    def test_invalid_yaml_not_dict(self, tmp_path: Path) -> None:
        mf = tmp_path / "manifest.yaml"
        mf.write_text("- just\n- a\n- list\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid manifest"):
            parse_manifest(mf)

    def test_empty_file(self, tmp_path: Path) -> None:
        mf = tmp_path / "manifest.yaml"
        mf.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid manifest"):
            parse_manifest(mf)


# ---------------------------------------------------------------------------
# 2. Pack discovery
# ---------------------------------------------------------------------------


class TestDiscoverPacks:
    """discover_packs() finds builtin packs."""

    def test_discovers_builtin_packs(self) -> None:
        """Builtin packs (NETL-TRIGA, MSRE, PWR-generic) are discovered."""
        packs = discover_packs()
        names = {p.name for p in packs}
        assert "NETL-TRIGA" in names
        assert "MSRE" in names
        assert "PWR-generic" in names

    def test_all_builtins_have_source_builtin(self) -> None:
        packs = discover_packs()
        builtins = [p for p in packs if p.path.is_relative_to(_builtin_packs_dir())]
        for p in builtins:
            assert p.source == "builtin"


# ---------------------------------------------------------------------------
# 3. Pack details
# ---------------------------------------------------------------------------


class TestGetPack:
    """get_pack() returns correct manifest fields."""

    def test_get_netl_triga(self) -> None:
        pack = get_pack("NETL-TRIGA")
        assert pack is not None
        assert pack.manifest.name == "NETL-TRIGA"
        assert pack.manifest.display_name == "UT Austin NETL TRIGA Mark II"
        assert pack.manifest.reactor_type == "TRIGA"
        assert pack.manifest.version == "1.0.0"
        assert "triga" in pack.manifest.tags

    def test_get_nonexistent_returns_none(self) -> None:
        assert get_pack("does-not-exist") is None


# ---------------------------------------------------------------------------
# 4. Pack init
# ---------------------------------------------------------------------------


class TestInitPack:
    """init_pack() creates proper directory structure."""

    def test_creates_structure(self, tmp_path: Path) -> None:
        pack_dir = init_pack("my-reactor", reactor_type="BWR", output_dir=tmp_path)

        assert pack_dir == tmp_path / "my-reactor"
        assert (pack_dir / "manifest.yaml").exists()
        assert (pack_dir / "materials").is_dir()
        assert (pack_dir / "templates").is_dir()
        assert (pack_dir / "parameters").is_dir()
        assert (pack_dir / "coreforge").is_dir()

    def test_manifest_content(self, tmp_path: Path) -> None:
        init_pack("my-reactor", reactor_type="BWR", maintainer="ben", output_dir=tmp_path)
        manifest = parse_manifest(tmp_path / "my-reactor" / "manifest.yaml")
        assert manifest.name == "my-reactor"
        assert manifest.reactor_type == "BWR"
        assert manifest.maintainer == "ben"
        assert manifest.version == "0.1.0"

    def test_raises_if_exists(self, tmp_path: Path) -> None:
        init_pack("dup", output_dir=tmp_path)
        with pytest.raises(FileExistsError):
            init_pack("dup", output_dir=tmp_path)


# ---------------------------------------------------------------------------
# 5. Pack install
# ---------------------------------------------------------------------------


class TestInstallPack:
    """install_pack() copies to user pack location."""

    def test_install_from_directory(self, tmp_path: Path) -> None:
        src = _make_pack_dir(tmp_path / "source", "test-pack")
        user_dir = tmp_path / "user_packs"

        with patch(
            "neutron_os.extensions.builtins.model_corral.facilities.registry._user_packs_dir",
            return_value=user_dir,
        ):
            result = install_pack(src)

        assert result.name == "test-pack"
        assert result.source == "user"
        assert (user_dir / "test-pack" / "manifest.yaml").exists()

    def test_install_no_manifest_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="No manifest.yaml"):
            install_pack(empty)

    def test_install_overwrites_existing(self, tmp_path: Path) -> None:
        src = _make_pack_dir(tmp_path / "source", "overwrite-me", {"version": "2.0.0"})
        user_dir = tmp_path / "user_packs"

        with patch(
            "neutron_os.extensions.builtins.model_corral.facilities.registry._user_packs_dir",
            return_value=user_dir,
        ):
            install_pack(_make_pack_dir(tmp_path / "v1", "overwrite-me", {"version": "1.0.0"}))
            result = install_pack(src)

        assert result.manifest.version == "2.0.0"


# ---------------------------------------------------------------------------
# 6. Pack uninstall
# ---------------------------------------------------------------------------


class TestUninstallPack:
    """uninstall_pack() removes the pack directory."""

    def test_uninstall_existing(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "user_packs"
        _make_pack_dir(user_dir, "remove-me")

        with patch(
            "neutron_os.extensions.builtins.model_corral.facilities.registry._user_packs_dir",
            return_value=user_dir,
        ):
            assert uninstall_pack("remove-me") is True

        assert not (user_dir / "remove-me").exists()

    def test_uninstall_nonexistent(self, tmp_path: Path) -> None:
        with patch(
            "neutron_os.extensions.builtins.model_corral.facilities.registry._user_packs_dir",
            return_value=tmp_path,
        ):
            assert uninstall_pack("ghost") is False

    def test_uninstall_invalid_target(self) -> None:
        assert uninstall_pack("x", target="invalid") is False


# ---------------------------------------------------------------------------
# 7. Pack publish
# ---------------------------------------------------------------------------


class TestPublishPack:
    """publish_pack() creates a .facilitypack tarball with SHA256SUMS."""

    def test_creates_tarball(self, tmp_path: Path) -> None:
        pack = _make_pack_dir(tmp_path, "pub-test")
        # Add a file so checksums are non-trivial
        (pack / "materials" / "fuel.yaml").write_text("fuel: UO2\n", encoding="utf-8")

        out = tmp_path / "output"
        out.mkdir()
        archive = publish_pack(pack, output=out / "pub-test.facilitypack")

        assert archive.exists()
        assert tarfile.is_tarfile(str(archive))

    def test_sha256sums_created(self, tmp_path: Path) -> None:
        pack = _make_pack_dir(tmp_path, "sha-test")
        (pack / "materials" / "fuel.yaml").write_text("fuel: UO2\n", encoding="utf-8")

        publish_pack(pack, output=tmp_path / "sha-test.facilitypack")

        sums_file = pack / "SHA256SUMS"
        assert sums_file.exists()
        content = sums_file.read_text(encoding="utf-8")
        assert "manifest.yaml" in content
        assert "materials/fuel.yaml" in content

    def test_publish_no_manifest_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "nomanifest"
        empty.mkdir()
        with pytest.raises(ValueError, match="No manifest.yaml"):
            publish_pack(empty)


# ---------------------------------------------------------------------------
# 8. Round trip: init → publish → install → discover → materials accessible
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Full lifecycle: init, publish, install, discover."""

    def test_full_round_trip(self, tmp_path: Path) -> None:
        work = tmp_path / "work"
        work.mkdir()
        user_dir = tmp_path / "user_packs"

        # Init
        pack_dir = init_pack(
            "round-trip-reactor",
            reactor_type="TRIGA",
            maintainer="test@example.com",
            output_dir=work,
        )

        # Add a material
        (pack_dir / "materials" / "fuel.yaml").write_text(
            "name: UZrH\nenrichment: 20\n", encoding="utf-8"
        )

        # Publish
        archive = publish_pack(pack_dir, output=tmp_path / "round-trip.facilitypack")
        assert archive.exists()

        # Install from archive
        with patch(
            "neutron_os.extensions.builtins.model_corral.facilities.registry._user_packs_dir",
            return_value=user_dir,
        ):
            installed = install_pack(archive)
            assert installed.name == "round-trip-reactor"
            assert installed.source == "user"

            # Materials accessible
            assert installed.materials_path.exists()
            fuel = installed.materials_path / "fuel.yaml"
            assert fuel.exists()
            fuel_data = yaml.safe_load(fuel.read_text(encoding="utf-8"))
            assert fuel_data["name"] == "UZrH"


# ---------------------------------------------------------------------------
# 9. Priority: project > user > builtin
# ---------------------------------------------------------------------------


class TestPriorityShadowing:
    """Project packs shadow user packs shadow builtin packs."""

    def test_project_shadows_user_shadows_builtin(self, tmp_path: Path) -> None:
        builtin_dir = tmp_path / "builtin"
        user_dir = tmp_path / "user"
        project_dir = tmp_path / "project"

        _make_pack_dir(builtin_dir, "shadowed", {"version": "1.0.0"})
        _make_pack_dir(user_dir, "shadowed", {"version": "2.0.0"})
        _make_pack_dir(project_dir, "shadowed", {"version": "3.0.0"})

        with (
            patch(
                "neutron_os.extensions.builtins.model_corral.facilities.registry._builtin_packs_dir",
                return_value=builtin_dir,
            ),
            patch(
                "neutron_os.extensions.builtins.model_corral.facilities.registry._user_packs_dir",
                return_value=user_dir,
            ),
            patch(
                "neutron_os.extensions.builtins.model_corral.facilities.registry._project_packs_dir",
                return_value=project_dir,
            ),
        ):
            packs = discover_packs()
            shadowed = [p for p in packs if p.name == "shadowed"]
            assert len(shadowed) == 1
            assert shadowed[0].manifest.version == "3.0.0"
            assert shadowed[0].source == "project"

    def test_user_shadows_builtin(self, tmp_path: Path) -> None:
        builtin_dir = tmp_path / "builtin"
        user_dir = tmp_path / "user"

        _make_pack_dir(builtin_dir, "shared", {"version": "1.0.0"})
        _make_pack_dir(user_dir, "shared", {"version": "2.0.0"})

        with (
            patch(
                "neutron_os.extensions.builtins.model_corral.facilities.registry._builtin_packs_dir",
                return_value=builtin_dir,
            ),
            patch(
                "neutron_os.extensions.builtins.model_corral.facilities.registry._user_packs_dir",
                return_value=user_dir,
            ),
            patch(
                "neutron_os.extensions.builtins.model_corral.facilities.registry._project_packs_dir",
                return_value=None,
            ),
        ):
            packs = discover_packs()
            shared = [p for p in packs if p.name == "shared"]
            assert len(shared) == 1
            assert shared[0].manifest.version == "2.0.0"
            assert shared[0].source == "user"


# ---------------------------------------------------------------------------
# 10. InstalledPack.to_dict()
# ---------------------------------------------------------------------------


class TestInstalledPackToDict:
    """Serialization includes all expected fields."""

    def test_to_dict_fields(self, tmp_path: Path) -> None:
        pack = _make_pack_dir(tmp_path, "dict-test")
        manifest = parse_manifest(pack / "manifest.yaml")
        ip = InstalledPack(manifest=manifest, path=pack, source="user")

        d = ip.to_dict()

        assert d["name"] == "dict-test"
        assert d["reactor_type"] == "PWR"
        assert d["version"] == "0.1.0"
        assert d["maintainer"] == "tester"
        assert d["source"] == "user"
        assert d["path"] == str(pack)
        assert d["license"] == "CC-BY-4.0"
        assert isinstance(d["tags"], list)
        # Boolean flags for directory presence
        assert d["has_materials"] is True
        assert d["has_templates"] is True
        assert d["has_parameters"] is True
        assert d["has_coreforge"] is True

    def test_to_dict_missing_subdirs(self, tmp_path: Path) -> None:
        """When subdirs don't exist, has_* flags are False."""
        pack = tmp_path / "sparse"
        pack.mkdir()
        _write_manifest(pack / "manifest.yaml", MINIMAL_MANIFEST)
        manifest = parse_manifest(pack / "manifest.yaml")
        ip = InstalledPack(manifest=manifest, path=pack, source="builtin")

        d = ip.to_dict()
        assert d["has_materials"] is False
        assert d["has_templates"] is False


# ---------------------------------------------------------------------------
# 11. Materials path
# ---------------------------------------------------------------------------


class TestMaterialsPath:
    """pack.materials_path points to correct directory."""

    def test_default_materials_dir(self, tmp_path: Path) -> None:
        pack = _make_pack_dir(tmp_path, "mat-test")
        manifest = parse_manifest(pack / "manifest.yaml")
        ip = InstalledPack(manifest=manifest, path=pack)
        assert ip.materials_path == pack / "materials"

    def test_custom_materials_dir(self, tmp_path: Path) -> None:
        pack = tmp_path / "custom"
        pack.mkdir()
        data = {**MINIMAL_MANIFEST, "materials_dir": "my_mats"}
        _write_manifest(pack / "manifest.yaml", data)
        (pack / "my_mats").mkdir()
        manifest = parse_manifest(pack / "manifest.yaml")
        ip = InstalledPack(manifest=manifest, path=pack)
        assert ip.materials_path == pack / "my_mats"


# ---------------------------------------------------------------------------
# 12. Builtin packs have materials
# ---------------------------------------------------------------------------


class TestBuiltinPackMaterials:
    """NETL-TRIGA has expected material files."""

    def test_netl_triga_has_materials(self) -> None:
        pack = get_pack("NETL-TRIGA")
        assert pack is not None
        assert pack.materials_path.exists()

        material_files = {f.name for f in pack.materials_path.iterdir()}
        assert "fuels.yaml" in material_files
        assert "moderators.yaml" in material_files
        assert "absorbers.yaml" in material_files
        assert "structural.yaml" in material_files

    def test_netl_triga_fuels_parseable(self) -> None:
        pack = get_pack("NETL-TRIGA")
        assert pack is not None
        fuel_data = yaml.safe_load((pack.materials_path / "fuels.yaml").read_text(encoding="utf-8"))
        assert fuel_data is not None
