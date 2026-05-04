"""Verified nuclear material compositions database.

Provides a shared, authoritative catalog of material compositions used
across CoreForge, manual MCNP/MPACT input editing, and Model Corral
validation. Compositions sourced from nuclear data references.

Supports pluggable material sources via the MaterialSource protocol.
Sources are merged by priority (higher wins). Built-in hardcoded materials
serve as the lowest-priority fallback; YAML files in the ``materials/``
directory override them.

Usage:
    from neutron_os.extensions.builtins.model_corral.materials_db import (
        get_material, list_materials, search_materials,
    )

    mat = get_material("UZrH-20")
    print(mat.mcnp_cards())  # Generate MCNP material card
    print(mat.density)       # g/cm³
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Isotope:
    """A single isotope with its ZAID and fraction."""

    zaid: str  # e.g., "92235.80c"
    fraction: float  # atom fraction or weight fraction
    name: str = ""  # e.g., "U-235"


@dataclass(frozen=True)
class MaterialDef:
    """A verified material composition."""

    name: str
    description: str
    density: float  # g/cm³ (negative = atom density in atoms/b-cm)
    isotopes: tuple[Isotope, ...] = ()
    fraction_type: str = "atom"  # "atom" or "weight"
    temperature_k: float = 293.6  # default room temperature
    category: str = ""  # fuel, moderator, structural, coolant, absorber
    source: str = ""  # reference for composition data
    sab: str = ""  # S(alpha,beta) thermal scattering library

    def mcnp_cards(self, mat_number: int = 1) -> str:
        """Generate MCNP material card text."""
        lines = [f"c  {self.name} — {self.description}"]
        lines.append(f"c  density: {abs(self.density):.4f} g/cm³  temp: {self.temperature_k} K")
        if self.source:
            lines.append(f"c  source: {self.source}")

        # Material card
        first = True
        for iso in self.isotopes:
            prefix = f"m{mat_number}" if first else "     "
            sign = "-" if self.fraction_type == "weight" else ""
            lines.append(f"{prefix}  {iso.zaid}  {sign}{iso.fraction:.6e}  $ {iso.name}")
            first = False

        # S(alpha,beta) card
        if self.sab:
            lines.append(f"mt{mat_number}  {self.sab}")

        return "\n".join(lines)

    def mpact_card(self) -> str:
        """Generate MPACT material definition."""
        parts = [f"mat {self.name} {len(self.isotopes)} {abs(self.density):.4f} g/cc"]
        parts.append(f"     {self.temperature_k:.1f} K")
        for iso in self.isotopes:
            parts.append(f"     {iso.zaid}  {iso.fraction:.6e}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "density": self.density,
            "temperature_k": self.temperature_k,
            "category": self.category,
            "source": self.source,
            "fraction_type": self.fraction_type,
            "num_isotopes": len(self.isotopes),
        }


# ---------------------------------------------------------------------------
# Material catalog — verified compositions
# ---------------------------------------------------------------------------

_BUILTIN_MATERIALS: dict[str, MaterialDef] = {}


def _register(mat: MaterialDef) -> MaterialDef:
    _BUILTIN_MATERIALS[mat.name] = mat
    return mat


# ---- Fuels ----

_register(
    MaterialDef(
        name="UZrH-20",
        description="Uranium-zirconium hydride fuel (20% enriched, TRIGA standard)",
        density=6.0,
        category="fuel",
        source="GA-4314, General Atomics TRIGA fuel specification",
        fraction_type="atom",
        temperature_k=293.6,
        isotopes=(
            Isotope("92235.80c", 3.44e-3, "U-235"),
            Isotope("92238.80c", 1.37e-2, "U-238"),
            Isotope("40090.80c", 3.30e-2, "Zr-90"),
            Isotope("40091.80c", 7.20e-3, "Zr-91"),
            Isotope("40092.80c", 1.10e-2, "Zr-92"),
            Isotope("40094.80c", 1.11e-2, "Zr-94"),
            Isotope("40096.80c", 1.79e-3, "Zr-96"),
            Isotope("1001.80c", 5.55e-2, "H-1"),
        ),
        sab="zr-h.40t",
    )
)

_register(
    MaterialDef(
        name="UO2-3.1",
        description="Uranium dioxide fuel (3.1% enriched, typical PWR)",
        density=10.42,
        category="fuel",
        source="NUREG/CR-6698",
        fraction_type="atom",
        temperature_k=900.0,
        isotopes=(
            Isotope("92235.80c", 7.18e-4, "U-235"),
            Isotope("92238.80c", 2.22e-2, "U-238"),
            Isotope("8016.80c", 4.58e-2, "O-16"),
        ),
    )
)

_register(
    MaterialDef(
        name="UO2-4.95",
        description="Uranium dioxide fuel (4.95% enriched, high-burnup PWR)",
        density=10.42,
        category="fuel",
        source="NUREG/CR-6698",
        fraction_type="atom",
        temperature_k=900.0,
        isotopes=(
            Isotope("92235.80c", 1.15e-3, "U-235"),
            Isotope("92238.80c", 2.17e-2, "U-238"),
            Isotope("8016.80c", 4.58e-2, "O-16"),
        ),
    )
)

# ---- Moderators / Coolants ----

_register(
    MaterialDef(
        name="H2O",
        description="Light water (liquid, room temperature)",
        density=0.998,
        category="moderator",
        source="Standard",
        fraction_type="atom",
        temperature_k=293.6,
        isotopes=(
            Isotope("1001.80c", 6.67e-2, "H-1"),
            Isotope("8016.80c", 3.33e-2, "O-16"),
        ),
        sab="lwtr.20t",
    )
)

_register(
    MaterialDef(
        name="H2O-hot",
        description="Light water (liquid, 600K PWR conditions)",
        density=0.700,
        category="coolant",
        source="IAPWS-IF97",
        fraction_type="atom",
        temperature_k=600.0,
        isotopes=(
            Isotope("1001.80c", 4.67e-2, "H-1"),
            Isotope("8016.80c", 2.33e-2, "O-16"),
        ),
        sab="lwtr.22t",
    )
)

_register(
    MaterialDef(
        name="graphite",
        description="Nuclear-grade graphite (density 1.70 g/cm³)",
        density=1.70,
        category="moderator",
        source="ORNL/TM-2005/272",
        fraction_type="atom",
        temperature_k=293.6,
        isotopes=(Isotope("6000.80c", 8.52e-2, "C-nat"),),
        sab="grph.20t",
    )
)

# ---- MSR Salt ----

_register(
    MaterialDef(
        name="MSRE-salt",
        description="MSRE fuel salt (LiF-BeF2-ZrF4-UF4, 65-29-5-1 mol%)",
        density=2.32,
        category="fuel",
        source="ORNL-4541, MSRE Design & Operations Report Part I",
        fraction_type="atom",
        temperature_k=922.0,
        isotopes=(
            Isotope("3007.80c", 4.62e-2, "Li-7"),
            Isotope("3006.80c", 5.08e-5, "Li-6"),
            Isotope("4009.80c", 2.06e-2, "Be-9"),
            Isotope("40090.80c", 2.65e-3, "Zr-90"),
            Isotope("40091.80c", 5.78e-4, "Zr-91"),
            Isotope("40092.80c", 8.83e-4, "Zr-92"),
            Isotope("40094.80c", 8.95e-4, "Zr-94"),
            Isotope("40096.80c", 1.44e-4, "Zr-96"),
            Isotope("92235.80c", 5.43e-4, "U-235"),
            Isotope("92238.80c", 1.63e-4, "U-238"),
            Isotope("9019.80c", 1.39e-1, "F-19"),
        ),
    )
)

# ---- Structural ----

_register(
    MaterialDef(
        name="SS304",
        description="Stainless steel 304 (standard composition)",
        density=7.94,
        category="structural",
        source="PNNL-15870 Rev. 2",
        fraction_type="weight",
        isotopes=(
            Isotope("26054.80c", 0.0342, "Fe-54"),
            Isotope("26056.80c", 0.5370, "Fe-56"),
            Isotope("26057.80c", 0.0124, "Fe-57"),
            Isotope("26058.80c", 0.0017, "Fe-58"),
            Isotope("24050.80c", 0.0077, "Cr-50"),
            Isotope("24052.80c", 0.1490, "Cr-52"),
            Isotope("24053.80c", 0.0169, "Cr-53"),
            Isotope("24054.80c", 0.0042, "Cr-54"),
            Isotope("28058.80c", 0.0659, "Ni-58"),
            Isotope("28060.80c", 0.0254, "Ni-60"),
            Isotope("28061.80c", 0.0011, "Ni-61"),
            Isotope("28062.80c", 0.0035, "Ni-62"),
            Isotope("28064.80c", 0.0009, "Ni-64"),
            Isotope("25055.80c", 0.0200, "Mn-55"),
            Isotope("14028.80c", 0.0092, "Si-28"),
            Isotope("14029.80c", 0.0005, "Si-29"),
            Isotope("14030.80c", 0.0003, "Si-30"),
        ),
    )
)

_register(
    MaterialDef(
        name="Zircaloy-4",
        description="Zircaloy-4 cladding (Zr-Sn-Fe-Cr)",
        density=6.56,
        category="structural",
        source="PNNL-15870 Rev. 2",
        fraction_type="weight",
        isotopes=(
            Isotope("40090.80c", 0.5079, "Zr-90"),
            Isotope("40091.80c", 0.1108, "Zr-91"),
            Isotope("40092.80c", 0.1694, "Zr-92"),
            Isotope("40094.80c", 0.1717, "Zr-94"),
            Isotope("40096.80c", 0.0277, "Zr-96"),
            Isotope("50120.80c", 0.0125, "Sn-120"),
        ),
    )
)

# ---- Absorbers ----

_register(
    MaterialDef(
        name="B4C",
        description="Boron carbide (natural boron, control rod absorber)",
        density=2.52,
        category="absorber",
        source="PNNL-15870 Rev. 2",
        fraction_type="atom",
        isotopes=(
            Isotope("5010.80c", 1.59e-2, "B-10"),
            Isotope("5011.80c", 6.39e-2, "B-11"),
            Isotope("6000.80c", 1.99e-2, "C-nat"),
        ),
    )
)

_register(
    MaterialDef(
        name="air",
        description="Dry air (standard composition)",
        density=0.001225,
        category="other",
        source="US Standard Atmosphere 1976",
        fraction_type="atom",
        isotopes=(
            Isotope("7014.80c", 3.90e-5, "N-14"),
            Isotope("8016.80c", 1.05e-5, "O-16"),
        ),
    )
)


# ---------------------------------------------------------------------------
# Material source protocol & implementations
# ---------------------------------------------------------------------------


@runtime_checkable
class MaterialSource(Protocol):
    """Plugin interface for material sources."""

    @property
    def name(self) -> str: ...

    @property
    def priority(self) -> int: ...

    def load(self) -> list[MaterialDef]: ...


class BuiltinMaterialSource:
    """The existing hardcoded materials (lowest priority fallback)."""

    @property
    def name(self) -> str:
        return "builtin"

    @property
    def priority(self) -> int:
        return 0  # lowest

    def load(self) -> list[MaterialDef]:
        return list(_BUILTIN_MATERIALS.values())


class YamlMaterialSource:
    """Loads materials from YAML files in a directory."""

    def __init__(self, directory: Path, priority: int = 50, source_name: str = "yaml"):
        self._directory = directory
        self._priority = priority
        self._source_name = source_name

    @property
    def name(self) -> str:
        return self._source_name

    @property
    def priority(self) -> int:
        return self._priority

    def load(self) -> list[MaterialDef]:
        """Load all .yaml files in directory, parse into MaterialDef objects."""
        materials: list[MaterialDef] = []
        if not self._directory.exists():
            return materials
        for yaml_file in sorted(self._directory.glob("*.yaml")):
            materials.extend(self._parse_yaml(yaml_file))
        return materials

    def _parse_yaml(self, path: Path) -> list[MaterialDef]:
        """Parse a single YAML file containing a list of materials."""
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        result: list[MaterialDef] = []
        for entry in data:
            isotopes = tuple(
                Isotope(
                    zaid=iso["zaid"],
                    fraction=iso["fraction"],
                    name=iso.get("name", ""),
                )
                for iso in entry.get("isotopes", [])
            )
            mat = MaterialDef(
                name=entry["name"],
                description=entry.get("description", ""),
                density=entry["density"],
                isotopes=isotopes,
                fraction_type=entry.get("fraction_type", "atom"),
                temperature_k=entry.get("temperature_k", 293.6),
                category=entry.get("category", ""),
                source=entry.get("source", ""),
                sab=entry.get("sab", ""),
            )
            result.append(mat)
        return result


class MaterialRegistry:
    """Merges materials from multiple sources with priority ordering.

    Higher priority sources override lower priority for same-named materials.
    """

    def __init__(self) -> None:
        self._sources: list[MaterialSource] = []
        self._materials: dict[str, MaterialDef] = {}
        self._material_sources: dict[str, str] = {}  # name -> source name
        self._loaded = False

    def register_source(self, source: MaterialSource) -> None:
        self._sources.append(source)
        self._sources.sort(key=lambda s: s.priority)
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._materials.clear()
        self._material_sources.clear()
        # Load in priority order (lowest first, highest overwrites)
        for source in self._sources:
            for mat in source.load():
                self._materials[mat.name] = mat
                self._material_sources[mat.name] = source.name
        self._loaded = True

    def get(self, name: str) -> MaterialDef | None:
        self._ensure_loaded()
        return self._materials.get(name)

    def list_all(self, category: str = "") -> list[MaterialDef]:
        self._ensure_loaded()
        if category:
            return [m for m in self._materials.values() if m.category == category]
        return list(self._materials.values())

    def search(self, query: str) -> list[MaterialDef]:
        self._ensure_loaded()
        q = query.lower()
        return [
            m
            for m in self._materials.values()
            if q in m.name.lower() or q in m.description.lower() or q in m.category.lower()
        ]

    def names(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._materials.keys())

    def source_of(self, name: str) -> str:
        """Return which source provided a given material."""
        self._ensure_loaded()
        return self._material_sources.get(name, "")

    def reload(self) -> None:
        """Force reload from all sources."""
        self._loaded = False
        self._ensure_loaded()


def composition_hash(mat: MaterialDef) -> str:
    """Compute a deterministic SHA-256 hash of a material's composition.

    Used for change detection — if the hash changes, the composition changed.
    """
    h = hashlib.sha256()
    h.update(mat.name.encode())
    h.update(f"{mat.density}".encode())
    h.update(mat.fraction_type.encode())
    for iso in sorted(mat.isotopes, key=lambda i: i.zaid):
        h.update(f"{iso.zaid}:{iso.fraction}".encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------

_REGISTRY = MaterialRegistry()
_REGISTRY.register_source(BuiltinMaterialSource())
_REGISTRY.register_source(YamlMaterialSource(Path(__file__).parent / "materials", priority=50))


# ---------------------------------------------------------------------------
# Public API (backward-compatible)
# ---------------------------------------------------------------------------


def get_material(name: str) -> MaterialDef | None:
    """Look up a material by name. Returns None if not found."""
    return _REGISTRY.get(name)


def list_materials(category: str = "") -> list[MaterialDef]:
    """List all materials, optionally filtered by category."""
    return _REGISTRY.list_all(category)


def search_materials(query: str) -> list[MaterialDef]:
    """Search materials by name or description."""
    return _REGISTRY.search(query)


def material_names() -> list[str]:
    """Return all registered material names."""
    return _REGISTRY.names()


def get_registry() -> MaterialRegistry:
    """Get the global material registry (for adding custom sources)."""
    return _REGISTRY
