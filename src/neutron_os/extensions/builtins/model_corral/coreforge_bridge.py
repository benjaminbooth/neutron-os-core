"""CoreForge bridge — optional dynamic import of CoreForge-computed materials.

CoreForge is Cole Gentry's Python library for programmatic reactor geometry
construction. When installed, NeutronOS imports its computed compositions
as a high-priority MaterialSource (priority 200, overrides YAML + builtins).

CoreForge is optional — the platform works without it. This module never
imports CoreForge at module load time; it only tries when explicitly requested.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .materials_db import Isotope, MaterialDef

logger = logging.getLogger(__name__)


@dataclass
class CoreForgeProvenance:
    """Provenance metadata captured when adding a CoreForge-generated model."""

    coreforge_version: str
    config_file: str
    builder_class: str
    builder_specs: dict
    geometry_hash: str

    def to_dict(self) -> dict:
        return {
            "coreforge_version": self.coreforge_version,
            "config_file": self.config_file,
            "builder_class": self.builder_class,
            "builder_specs": self.builder_specs,
            "geometry_hash": self.geometry_hash,
        }


def is_coreforge_available() -> bool:
    """Check if CoreForge is installed and importable."""
    try:
        importlib.import_module("coreforge")
        return True
    except ImportError:
        return False


def get_coreforge_version() -> str:
    """Get the installed CoreForge version."""
    try:
        cf = importlib.import_module("coreforge")
        return getattr(cf, "__version__", "unknown")
    except ImportError:
        return ""


def extract_provenance(config_path: Path | None = None, **kwargs: Any) -> CoreForgeProvenance:
    """Extract provenance metadata from a CoreForge environment.

    Args:
        config_path: Path to CoreForge .py config file.
        **kwargs: Additional metadata (builder_class, builder_specs, geometry_hash).

    Returns:
        CoreForgeProvenance with captured metadata.
    """
    import hashlib

    version = get_coreforge_version()
    config_file = str(config_path) if config_path else ""

    # Hash the config file for change detection
    geometry_hash = ""
    if config_path and config_path.exists():
        geometry_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()[:16]

    return CoreForgeProvenance(
        coreforge_version=version,
        config_file=config_file,
        builder_class=kwargs.get("builder_class", ""),
        builder_specs=kwargs.get("builder_specs", {}),
        geometry_hash=kwargs.get("geometry_hash", geometry_hash),
    )


class CoreForgeMaterialSource:
    """MaterialSource that loads compositions from CoreForge.

    Priority 200 — highest authority for material compositions.
    Falls back gracefully when CoreForge is not installed.
    """

    @property
    def name(self) -> str:
        return "coreforge"

    @property
    def priority(self) -> int:
        return 200

    def load(self) -> list[MaterialDef]:
        """Import materials from CoreForge if available."""
        if not is_coreforge_available():
            return []

        try:
            return self._import_materials()
        except Exception as e:
            logger.warning("CoreForge material import failed: %s", e)
            return []

    def _import_materials(self) -> list[MaterialDef]:
        """Attempt to import materials from CoreForge's material registry."""
        materials = []
        try:
            cf = importlib.import_module("coreforge")

            # CoreForge uses a material registry pattern — try known APIs
            # This adapts to CoreForge's actual API as it evolves
            registry = getattr(cf, "materials", None) or getattr(cf, "material_registry", None)
            if registry is None:
                return []

            # Try to iterate over registered materials
            mat_list = getattr(registry, "list_all", lambda: [])()
            for cf_mat in mat_list:
                mat = self._convert_material(cf_mat)
                if mat is not None:
                    materials.append(mat)

        except (ImportError, AttributeError) as e:
            logger.debug("CoreForge material import: %s", e)

        return materials

    @staticmethod
    def _convert_material(cf_mat: Any) -> MaterialDef | None:
        """Convert a CoreForge material object to MaterialDef.

        Adapts to CoreForge's frozen-dataclass API:
        - cf_mat.name, cf_mat.density, cf_mat.temperature
        - cf_mat.isotopes → list of (zaid, fraction) or similar
        """
        try:
            name = getattr(cf_mat, "name", None)
            density = getattr(cf_mat, "density", None)
            if name is None or density is None:
                return None

            # Convert isotopes
            isotopes = []
            cf_isos = getattr(cf_mat, "isotopes", []) or getattr(cf_mat, "nuclides", [])
            for iso in cf_isos:
                if hasattr(iso, "zaid"):
                    isotopes.append(
                        Isotope(
                            zaid=iso.zaid,
                            fraction=getattr(iso, "fraction", getattr(iso, "atom_fraction", 0.0)),
                            name=getattr(iso, "name", ""),
                        )
                    )
                elif isinstance(iso, (list, tuple)) and len(iso) >= 2:
                    isotopes.append(Isotope(zaid=str(iso[0]), fraction=float(iso[1])))

            return MaterialDef(
                name=name,
                description=getattr(cf_mat, "description", f"CoreForge: {name}"),
                density=float(density),
                isotopes=tuple(isotopes),
                fraction_type=getattr(cf_mat, "fraction_type", "atom"),
                temperature_k=getattr(cf_mat, "temperature", 293.6),
                category=getattr(cf_mat, "category", "fuel"),
                source=f"CoreForge v{get_coreforge_version()}",
            )
        except (AttributeError, TypeError, ValueError) as e:
            logger.debug("Failed to convert CoreForge material: %s", e)
            return None
