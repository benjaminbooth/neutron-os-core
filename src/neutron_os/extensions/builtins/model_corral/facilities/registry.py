"""Facility pack registry — discover, install, and manage facility packs.

Facility packs are directories (or .facilitypack archives) with a manifest.yaml
describing the reactor facility, its materials, templates, and parameters.

Pack sources (searched in order):
1. Installed packs: ~/.neut/facility-packs/
2. Project packs: .neut/facility-packs/
3. Builtin packs: shipped with NeutronOS
"""

from __future__ import annotations

import hashlib
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class FacilityManifest:
    """Parsed manifest.yaml from a facility pack."""

    name: str
    display_name: str
    reactor_type: str
    version: str
    maintainer: str
    description: str = ""
    license: str = "CC-BY-4.0"
    materials_dir: str = "materials"
    templates_dir: str = "templates"
    parameters_dir: str = "parameters"
    coreforge_dir: str = "coreforge"
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "reactor_type": self.reactor_type,
            "version": self.version,
            "maintainer": self.maintainer,
            "description": self.description,
            "license": self.license,
            "tags": list(self.tags),
        }


@dataclass
class InstalledPack:
    """A facility pack installed on this node."""

    manifest: FacilityManifest
    path: Path
    source: str = "builtin"  # builtin, user, project, federation

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def materials_path(self) -> Path:
        return self.path / self.manifest.materials_dir

    @property
    def templates_path(self) -> Path:
        return self.path / self.manifest.templates_dir

    @property
    def parameters_path(self) -> Path:
        return self.path / self.manifest.parameters_dir

    @property
    def coreforge_path(self) -> Path:
        return self.path / self.manifest.coreforge_dir

    def to_dict(self) -> dict:
        info = self.manifest.to_dict()
        info["path"] = str(self.path)
        info["source"] = self.source
        info["has_materials"] = self.materials_path.exists()
        info["has_templates"] = self.templates_path.exists()
        info["has_parameters"] = self.parameters_path.exists()
        info["has_coreforge"] = self.coreforge_path.exists()
        return info


def _user_packs_dir() -> Path:
    """~/.neut/facility-packs/"""
    return Path.home() / ".neut" / "facility-packs"


def _project_packs_dir() -> Path | None:
    """.neut/facility-packs/ in the current project, if it exists."""
    cwd = Path.cwd()
    d = cwd / ".neut" / "facility-packs"
    return d if d.exists() else None


def _builtin_packs_dir() -> Path:
    """Builtin packs shipped with NeutronOS."""
    return Path(__file__).parent / "builtin_packs"


def parse_manifest(manifest_path: Path) -> FacilityManifest:
    """Parse a facility pack manifest.yaml."""
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid manifest: {manifest_path}")

    required = ["name", "reactor_type", "version", "maintainer"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(f"Missing required fields in manifest: {', '.join(missing)}")

    return FacilityManifest(
        name=data["name"],
        display_name=data.get("display_name", data["name"]),
        reactor_type=data["reactor_type"],
        version=data["version"],
        maintainer=data["maintainer"],
        description=data.get("description", ""),
        license=data.get("license", "CC-BY-4.0"),
        materials_dir=data.get("materials_dir", "materials"),
        templates_dir=data.get("templates_dir", "templates"),
        parameters_dir=data.get("parameters_dir", "parameters"),
        coreforge_dir=data.get("coreforge_dir", "coreforge"),
        tags=tuple(data.get("tags", [])),
    )


def discover_packs() -> list[InstalledPack]:
    """Discover all available facility packs from all sources.

    Priority order (highest first): project > user > builtin.
    Same-named packs from higher-priority sources shadow lower ones.
    """
    packs: dict[str, InstalledPack] = {}

    # Builtin packs (lowest priority)
    builtin_dir = _builtin_packs_dir()
    if builtin_dir.exists():
        for pack_dir in sorted(builtin_dir.iterdir()):
            manifest_file = pack_dir / "manifest.yaml"
            if manifest_file.exists():
                try:
                    manifest = parse_manifest(manifest_file)
                    packs[manifest.name] = InstalledPack(
                        manifest=manifest, path=pack_dir, source="builtin"
                    )
                except (ValueError, yaml.YAMLError):
                    pass

    # User packs
    user_dir = _user_packs_dir()
    if user_dir.exists():
        for pack_dir in sorted(user_dir.iterdir()):
            manifest_file = pack_dir / "manifest.yaml"
            if manifest_file.exists():
                try:
                    manifest = parse_manifest(manifest_file)
                    packs[manifest.name] = InstalledPack(
                        manifest=manifest, path=pack_dir, source="user"
                    )
                except (ValueError, yaml.YAMLError):
                    pass

    # Project packs (highest priority)
    project_dir = _project_packs_dir()
    if project_dir is not None:
        for pack_dir in sorted(project_dir.iterdir()):
            manifest_file = pack_dir / "manifest.yaml"
            if manifest_file.exists():
                try:
                    manifest = parse_manifest(manifest_file)
                    packs[manifest.name] = InstalledPack(
                        manifest=manifest, path=pack_dir, source="project"
                    )
                except (ValueError, yaml.YAMLError):
                    pass

    return sorted(packs.values(), key=lambda p: p.name)


def get_pack(name: str) -> InstalledPack | None:
    """Get a specific facility pack by name."""
    for pack in discover_packs():
        if pack.name == name:
            return pack
    return None


def install_pack(source_path: Path, target: str = "user") -> InstalledPack:
    """Install a facility pack from a directory or .facilitypack archive.

    Args:
        source_path: Path to pack directory or .facilitypack file.
        target: Where to install — "user" (~/.neut/) or "project" (.neut/).

    Returns:
        The installed pack.
    """
    if target == "user":
        base = _user_packs_dir()
    elif target == "project":
        base = Path.cwd() / ".neut" / "facility-packs"
    else:
        raise ValueError(f"Invalid target: {target}")

    # If it's an archive, extract first
    if source_path.is_file() and (
        source_path.suffix == ".facilitypack" or tarfile.is_tarfile(str(source_path))
    ):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with tarfile.open(source_path, "r:gz") as tar:
                tar.extractall(tmp_path, filter="data")
            # Find manifest
            dirs = [d for d in tmp_path.iterdir() if (d / "manifest.yaml").exists()]
            if not dirs:
                raise ValueError("No manifest.yaml found in archive")
            extracted = dirs[0]
            manifest = parse_manifest(extracted / "manifest.yaml")
            dest = base / manifest.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(extracted, dest)
    else:
        # It's a directory
        manifest_file = source_path / "manifest.yaml"
        if not manifest_file.exists():
            raise ValueError(f"No manifest.yaml in {source_path}")
        manifest = parse_manifest(manifest_file)
        dest = base / manifest.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source_path, dest)

    return InstalledPack(manifest=manifest, path=dest, source=target)


def uninstall_pack(name: str, target: str = "user") -> bool:
    """Remove an installed facility pack."""
    if target == "user":
        base = _user_packs_dir()
    elif target == "project":
        base = Path.cwd() / ".neut" / "facility-packs"
    else:
        return False

    pack_dir = base / name
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
        return True
    return False


def init_pack(
    name: str,
    *,
    reactor_type: str = "custom",
    maintainer: str = "",
    output_dir: Path | None = None,
) -> Path:
    """Scaffold a new facility pack directory.

    Creates:
        <name>/
        ├── manifest.yaml
        ├── materials/
        ├── templates/
        ├── parameters/
        └── coreforge/
    """
    base = output_dir or Path.cwd()
    pack_dir = base / name

    if pack_dir.exists():
        raise FileExistsError(f"Directory already exists: {pack_dir}")

    pack_dir.mkdir(parents=True)
    (pack_dir / "materials").mkdir()
    (pack_dir / "templates").mkdir()
    (pack_dir / "parameters").mkdir()
    (pack_dir / "coreforge").mkdir()

    manifest = {
        "name": name,
        "display_name": name.replace("-", " ").title(),
        "reactor_type": reactor_type,
        "version": "0.1.0",
        "maintainer": maintainer or "CHANGEME",
        "description": f"Facility pack for {name}",
        "license": "CC-BY-4.0",
        "tags": [reactor_type.lower()],
    }

    (pack_dir / "manifest.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # Placeholder README
    (pack_dir / "README.md").write_text(
        f"# {manifest['display_name']}\n\n"
        f"{manifest['description']}\n\n"
        "## Contents\n\n"
        "- `materials/` — Material definitions (YAML)\n"
        "- `templates/` — Model templates (model.yaml stubs + input skeletons)\n"
        "- `parameters/` — Facility-specific operating parameters\n"
        "- `coreforge/` — CoreForge configurations\n",
        encoding="utf-8",
    )

    return pack_dir


def publish_pack(pack_dir: Path, output: Path | None = None) -> Path:
    """Create a .facilitypack archive from a pack directory.

    Args:
        pack_dir: Path to the pack directory (must have manifest.yaml).
        output: Output path for the archive. Defaults to <name>-<version>.facilitypack.

    Returns:
        Path to the created archive.
    """
    manifest_file = pack_dir / "manifest.yaml"
    if not manifest_file.exists():
        raise ValueError(f"No manifest.yaml in {pack_dir}")

    manifest = parse_manifest(manifest_file)

    if output is None:
        output = Path.cwd() / f"{manifest.name}-v{manifest.version}.facilitypack"

    # Compute checksums
    checksums = {}
    for f in sorted(pack_dir.rglob("*")):
        if f.is_file() and f.name != "SHA256SUMS":
            rel = f.relative_to(pack_dir)
            checksums[str(rel)] = hashlib.sha256(f.read_bytes()).hexdigest()

    # Write SHA256SUMS
    sums_content = "\n".join(f"{h}  {p}" for p, h in sorted(checksums.items()))
    (pack_dir / "SHA256SUMS").write_text(sums_content + "\n", encoding="utf-8")

    # Create tarball
    with tarfile.open(str(output), "w:gz") as tar:
        tar.add(pack_dir, arcname=manifest.name)

    return output
