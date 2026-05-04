"""Federation integration for Model Corral.

Enables material and model distribution across federated nodes via .axiompack
and .facilitypack archives. Federation-aware MaterialSource loads materials
from received packs.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from neutron_os.extensions.builtins.model_corral.materials_db import (
    MaterialDef,
    YamlMaterialSource,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_ACCESS_TIERS = {"public", "restricted", "export_controlled"}
_FEDERATION_DIR_NAME = "federation-packs"


def _federation_packs_dir() -> Path:
    """~/.neut/federation-packs/ — where received packs are stored."""
    return Path.home() / ".neut" / _FEDERATION_DIR_NAME


# ---------------------------------------------------------------------------
# FederationPackSource — MaterialSource implementation
# ---------------------------------------------------------------------------


@dataclass
class FederationPackSource:
    """MaterialSource that loads from federation-received packs.

    Priority 75 -- above builtins (0) and local YAML (50),
    below user overrides (100) and CoreForge (200).
    """

    packs_dir: Path | None = None

    @property
    def name(self) -> str:
        return "federation"

    @property
    def priority(self) -> int:
        return 75

    def load(self) -> list[MaterialDef]:
        """Load materials from all installed federation packs."""
        base = self.packs_dir or _federation_packs_dir()
        if not base.exists():
            return []

        materials: list[MaterialDef] = []
        for pack_dir in sorted(base.iterdir()):
            if not pack_dir.is_dir():
                continue
            # Check access tier — block export_controlled locally
            meta_file = pack_dir / "pack-meta.json"
            if meta_file.exists():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if meta.get("access_tier") == "export_controlled":
                    continue

            # Load materials from materials/ subdirectory
            mat_dir = pack_dir / "materials"
            if mat_dir.exists():
                src = YamlMaterialSource(
                    mat_dir, priority=75, source_name=f"federation:{pack_dir.name}"
                )
                materials.extend(src.load())

        return materials


# ---------------------------------------------------------------------------
# Pack creation
# ---------------------------------------------------------------------------


def create_materials_pack(
    materials: list[MaterialDef],
    pack_id: str,
    version: str = "1.0.0",
    access_tier: str = "public",
    output_dir: Path | None = None,
) -> Path:
    """Bundle materials into a .axiompack for federation distribution.

    Args:
        materials: List of MaterialDef objects to include.
        pack_id: Unique identifier for this pack.
        version: Semantic version string.
        access_tier: One of public, restricted, export_controlled.
        output_dir: Where to write the archive. Defaults to cwd.

    Returns:
        Path to the created .axiompack file.
    """
    if access_tier not in _VALID_ACCESS_TIERS:
        raise ValueError(
            f"Invalid access_tier: {access_tier}. Must be one of {_VALID_ACCESS_TIERS}"
        )

    out = output_dir or Path.cwd()
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        pack_dir = Path(tmp) / pack_id
        pack_dir.mkdir()
        mat_dir = pack_dir / "materials"
        mat_dir.mkdir()

        # Write materials as YAML
        mat_dicts = []
        for m in materials:
            d: dict[str, Any] = {
                "name": m.name,
                "description": m.description,
                "density": m.density,
                "category": m.category,
                "fraction_type": m.fraction_type,
                "temperature_k": m.temperature_k,
                "source": m.source,
            }
            if m.sab:
                d["sab"] = m.sab
            if m.isotopes:
                d["isotopes"] = [
                    {"zaid": iso.zaid, "fraction": iso.fraction, "name": iso.name}
                    for iso in m.isotopes
                ]
            mat_dicts.append(d)

        (mat_dir / "materials.yaml").write_text(
            yaml.dump(mat_dicts, default_flow_style=False), encoding="utf-8"
        )

        # Write pack metadata
        meta = {
            "pack_id": pack_id,
            "pack_type": "materials",
            "version": version,
            "access_tier": access_tier,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "material_count": len(materials),
        }
        (pack_dir / "pack-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # Compute checksums
        checksums: dict[str, str] = {}
        for f in sorted(pack_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(pack_dir)
                checksums[str(rel)] = hashlib.sha256(f.read_bytes()).hexdigest()
        (pack_dir / "SHA256SUMS").write_text(
            "\n".join(f"{h}  {p}" for p, h in sorted(checksums.items())) + "\n",
            encoding="utf-8",
        )

        # Create tarball
        archive_path = out / f"{pack_id}-v{version}.axiompack"
        with tarfile.open(str(archive_path), "w:gz") as tar:
            tar.add(pack_dir, arcname=pack_id)

    return archive_path


def create_facility_pack_archive(
    facility_dir: Path,
    output: Path | None = None,
) -> Path:
    """Create a .facilitypack from a facility pack directory for federation.

    Delegates to the existing publish_pack in the facilities registry, adding
    federation metadata to the archive.

    Args:
        facility_dir: Path to facility pack directory (must have manifest.yaml).
        output: Output path. Defaults to <name>-<version>.facilitypack in cwd.

    Returns:
        Path to the created .facilitypack archive.
    """
    from neutron_os.extensions.builtins.model_corral.facilities.registry import (
        publish_pack,
    )

    manifest_file = facility_dir / "manifest.yaml"
    if not manifest_file.exists():
        raise ValueError(f"No manifest.yaml in {facility_dir}")

    # Add federation metadata before publishing
    meta = {
        "federation": True,
        "distributed_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = facility_dir / "federation-meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    try:
        archive = publish_pack(facility_dir, output=output)
    finally:
        # Clean up federation metadata from source dir
        if meta_path.exists():
            meta_path.unlink()

    return archive


# ---------------------------------------------------------------------------
# Pack installation
# ---------------------------------------------------------------------------


def install_received_pack(archive_path: Path, packs_dir: Path | None = None) -> dict:
    """Install a received .axiompack or .facilitypack from a federation peer.

    Args:
        archive_path: Path to the received archive file.
        packs_dir: Override for installation directory (default ~/.neut/federation-packs/).

    Returns:
        Dict with installation details (pack_id, type, path, material_count).
    """
    base = packs_dir or _federation_packs_dir()
    base.mkdir(parents=True, exist_ok=True)

    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(str(archive_path), "r:gz") as tar:
            tar.extractall(tmp_path, filter="data")

        # Find the extracted pack directory
        extracted_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        if not extracted_dirs:
            raise ValueError("No directory found in archive")
        extracted = extracted_dirs[0]

        pack_name = extracted.name

        # Determine pack type
        meta_file = extracted / "pack-meta.json"
        manifest_file = extracted / "manifest.yaml"

        result: dict[str, Any] = {"pack_id": pack_name, "path": str(base / pack_name)}

        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            result["type"] = meta.get("pack_type", "materials")
            result["access_tier"] = meta.get("access_tier", "public")
            result["version"] = meta.get("version", "unknown")

            # Block export_controlled packs
            if meta.get("access_tier") == "export_controlled":
                raise PermissionError(
                    f"Cannot install export_controlled pack '{pack_name}' on this node. "
                    "Export-controlled materials require explicit authorization."
                )

        elif manifest_file.exists():
            result["type"] = "facility"
            manifest_data = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
            result["version"] = manifest_data.get("version", "unknown")
        else:
            result["type"] = "unknown"

        # Install
        dest = base / pack_name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(extracted, dest)
        result["path"] = str(dest)

        # Count materials
        mat_dir = dest / "materials"
        if mat_dir.exists():
            src = YamlMaterialSource(mat_dir, source_name="count")
            result["material_count"] = len(src.load())
        else:
            result["material_count"] = 0

    return result


# ---------------------------------------------------------------------------
# Federation material listing
# ---------------------------------------------------------------------------


def list_federation_materials(packs_dir: Path | None = None) -> list[dict]:
    """List all materials received from federation peers.

    Returns:
        List of dicts with material name, source pack, and metadata.
    """
    base = packs_dir or _federation_packs_dir()
    if not base.exists():
        return []

    results: list[dict] = []
    for pack_dir in sorted(base.iterdir()):
        if not pack_dir.is_dir():
            continue

        # Check access tier
        meta_file = pack_dir / "pack-meta.json"
        access_tier = "public"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            access_tier = meta.get("access_tier", "public")
            if access_tier == "export_controlled":
                continue

        mat_dir = pack_dir / "materials"
        if not mat_dir.exists():
            continue

        src = YamlMaterialSource(mat_dir, source_name=f"federation:{pack_dir.name}")
        for m in src.load():
            results.append(
                {
                    "name": m.name,
                    "category": m.category,
                    "density": m.density,
                    "source_pack": pack_dir.name,
                    "access_tier": access_tier,
                }
            )

    return results


# ---------------------------------------------------------------------------
# ModelSharingService
# ---------------------------------------------------------------------------


@dataclass
class ModelSharingService:
    """Share and receive models between federation nodes.

    Uses the axiom pack infrastructure to bundle models for distribution.
    Respects access_tier controls (public, restricted, export_controlled).
    """

    shared_dir: Path | None = None
    received_dir: Path | None = None
    _shared_registry: list[dict] = field(default_factory=list)

    def _get_shared_dir(self) -> Path:
        d = self.shared_dir or (Path.home() / ".neut" / "shared-models")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _get_received_dir(self) -> Path:
        d = self.received_dir or (Path.home() / ".neut" / "received-models")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _registry_path(self) -> Path:
        return self._get_shared_dir() / "registry.json"

    def _load_registry(self) -> list[dict]:
        reg_path = self._registry_path()
        if reg_path.exists():
            return json.loads(reg_path.read_text(encoding="utf-8"))
        return []

    def _save_registry(self, entries: list[dict]) -> None:
        self._registry_path().write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def share_model(
        self,
        model_id: str,
        target_node: str | None = None,
        access_tier: str = "public",
        model_dir: Path | None = None,
    ) -> Path:
        """Package a model as .axiompack and optionally push to a node.

        Args:
            model_id: Identifier for the model.
            target_node: Target federation node (for metadata; actual push is async).
            access_tier: Access control tier.
            model_dir: Path to model files. If None, uses a stub.

        Returns:
            Path to the created .axiompack archive.
        """
        if access_tier not in _VALID_ACCESS_TIERS:
            raise ValueError(f"Invalid access_tier: {access_tier}")

        shared = self._get_shared_dir()

        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp) / model_id
            pack_dir.mkdir()

            # Copy model files if provided
            if model_dir and model_dir.exists():
                model_dest = pack_dir / "model"
                shutil.copytree(model_dir, model_dest)
            else:
                (pack_dir / "model").mkdir()

            # Write pack metadata
            meta = {
                "pack_id": model_id,
                "pack_type": "model",
                "access_tier": access_tier,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "target_node": target_node,
            }
            (pack_dir / "pack-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

            # Create archive
            archive_path = shared / f"{model_id}.axiompack"
            with tarfile.open(str(archive_path), "w:gz") as tar:
                tar.add(pack_dir, arcname=model_id)

        # Update registry
        entries = self._load_registry()
        entries.append(
            {
                "model_id": model_id,
                "access_tier": access_tier,
                "target_node": target_node,
                "shared_at": datetime.now(timezone.utc).isoformat(),
                "archive": str(archive_path),
            }
        )
        self._save_registry(entries)

        return archive_path

    def receive_model(self, pack_path: Path) -> dict:
        """Unpack and register a received model.

        Args:
            pack_path: Path to the received .axiompack file.

        Returns:
            Dict with model_id, path, and metadata.
        """
        if not pack_path.exists():
            raise FileNotFoundError(f"Pack not found: {pack_path}")

        received = self._get_received_dir()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with tarfile.open(str(pack_path), "r:gz") as tar:
                tar.extractall(tmp_path, filter="data")

            extracted_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
            if not extracted_dirs:
                raise ValueError("No directory found in archive")
            extracted = extracted_dirs[0]
            model_id = extracted.name

            # Read metadata
            meta_file = extracted / "pack-meta.json"
            meta: dict[str, Any] = {}
            if meta_file.exists():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))

            # Check access tier
            if meta.get("access_tier") == "export_controlled":
                raise PermissionError(f"Cannot receive export_controlled model '{model_id}'.")

            # Install
            dest = received / model_id
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(extracted, dest)

        return {
            "model_id": model_id,
            "path": str(dest),
            "access_tier": meta.get("access_tier", "public"),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_shared_models(self) -> list[dict]:
        """List models available from federation peers."""
        return self._load_registry()
