"""NeutronOS domain-specific entity and relationship types.

Registers nuclear-domain entity types with the Axiom knowledge graph.
These extend the core generic types (Document, Component, Material, etc.)
with nuclear-specific subtypes.

Usage::

    from neutron_os.graph.entity_types import register_nuclear_types
    register_nuclear_types(registry)
"""

from __future__ import annotations

from axiom.graph.schema import EntityType, EntityTypeRegistry, RelationshipType

# ---------------------------------------------------------------------------
# Nuclear-domain entity types
# ---------------------------------------------------------------------------

NUCLEAR_ENTITY_TYPES = [
    # Reactor systems
    EntityType(
        "Reactor", parent="Component",
        properties=["type", "thermal_power_mw", "coolant", "moderator", "fuel_type"],
        description="A nuclear reactor system (research, power, or experimental)",
    ),
    EntityType(
        "FuelElement", parent="Component",
        properties=["enrichment", "geometry", "material", "cladding"],
        description="A nuclear fuel element or fuel assembly",
    ),
    EntityType(
        "ControlRod", parent="Component",
        properties=["material", "worth_pcm", "rod_type"],
        description="A reactor control rod or control element",
    ),
    EntityType(
        "CoolantSystem", parent="Component",
        properties=["coolant_type", "flow_rate", "operating_temperature"],
        description="A reactor coolant system (primary, secondary, emergency)",
    ),

    # Materials & isotopes
    EntityType(
        "Isotope", parent="Material",
        properties=["z", "a", "half_life", "decay_mode"],
        description="A specific nuclear isotope",
    ),
    EntityType(
        "FuelSalt", parent="Material",
        properties=["composition", "mole_fractions", "melting_point", "density"],
        description="A molten salt fuel composition",
    ),
    EntityType(
        "StructuralMaterial", parent="Material",
        properties=["alloy_designation", "operating_temp_max", "corrosion_resistance"],
        description="A structural material used in reactor construction (e.g., Hastelloy N)",
    ),

    # Regulatory & procedures
    EntityType(
        "Regulation", parent="Procedure",
        properties=["cfr_part", "section", "effective_date"],
        description="A nuclear regulatory requirement (10 CFR, NRC Reg Guide, etc.)",
    ),
    EntityType(
        "SafetyAnalysis", parent="Document",
        properties=["analysis_type", "facility", "methodology"],
        description="A safety analysis report (SAR, FSAR, PSAR, etc.)",
    ),
    EntityType(
        "TechnicalSpecification", parent="Procedure",
        properties=["facility", "limit_type", "value"],
        description="A facility technical specification or operating limit",
    ),

    # Simulation & computation
    EntityType(
        "SimulationCode", parent="Code",
        properties=["physics_domain", "method", "geometry_type"],
        description="A nuclear simulation code (MCNP, Serpent, OpenMC, MPACT, etc.)",
    ),
    EntityType(
        "CrossSectionLibrary", parent="Code",
        properties=["evaluation", "energy_groups", "temperature_range"],
        description="A nuclear cross-section data library (ENDF/B, JEFF, JENDL)",
    ),

    # Facility-specific
    EntityType(
        "Facility", parent="Component",
        properties=["facility_type", "location", "license_number", "operator"],
        description="A nuclear facility (reactor, lab, fuel fabrication, etc.)",
    ),
    EntityType(
        "Experiment", parent="Concept",
        properties=["facility", "date_range", "objective", "methodology"],
        description="A nuclear experiment or measurement campaign",
    ),
]

# ---------------------------------------------------------------------------
# Nuclear-domain relationship types
# ---------------------------------------------------------------------------

NUCLEAR_RELATIONSHIP_TYPES = [
    RelationshipType(
        "OPERATES_AT", "Person", "Facility",
        properties=["role", "period"],
        description="Person operates or works at a facility",
    ),
    RelationshipType(
        "FUELED_BY", "Reactor", "FuelSalt",
        properties=["period", "mole_fractions"],
        description="Reactor uses a specific fuel salt composition",
    ),
    RelationshipType(
        "MODERATED_BY", "Reactor", "Material",
        properties=["configuration"],
        description="Reactor uses a specific moderator material",
    ),
    RelationshipType(
        "REGULATED_BY", "Facility", "Regulation",
        properties=["compliance_status"],
        description="Facility is regulated by a specific regulation",
    ),
    RelationshipType(
        "SIMULATED_WITH", "Experiment", "SimulationCode",
        properties=["version", "geometry", "results_agreement"],
        description="Experiment was simulated/validated with a code",
    ),
    RelationshipType(
        "CONTAINS_ISOTOPE", "FuelSalt", "Isotope",
        properties=["fraction", "enrichment"],
        description="Fuel salt contains a specific isotope",
    ),
    RelationshipType(
        "CONSTRUCTED_FROM", "Reactor", "StructuralMaterial",
        properties=["component", "application"],
        description="Reactor component is constructed from a structural material",
    ),
    RelationshipType(
        "CROSS_SECTION_FROM", "SimulationCode", "CrossSectionLibrary",
        properties=["energy_groups"],
        description="Simulation code uses cross-section data from a library",
    ),
]


# ---------------------------------------------------------------------------
# Registration function
# ---------------------------------------------------------------------------

def register_nuclear_types(registry: EntityTypeRegistry) -> int:
    """Register all nuclear-domain entity and relationship types.

    Args:
        registry: The Axiom EntityTypeRegistry to extend

    Returns:
        Number of types registered
    """
    count = 0
    for et in NUCLEAR_ENTITY_TYPES:
        registry.register(et)
        count += 1
    for rt in NUCLEAR_RELATIONSHIP_TYPES:
        registry.register_relationship(rt)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Domain-specific extraction patterns (extend deterministic extractor)
# ---------------------------------------------------------------------------

NUCLEAR_CROSS_REF_PATTERNS = [
    # Reactor names
    (r"\bMSRE\b", "Reactor"),
    (r"\bMSBR\b", "Reactor"),
    (r"\bARE\b", "Reactor"),
    (r"\bTRIGA\b", "Reactor"),
    (r"\bEBR-II\b", "Reactor"),
    (r"\bHTGR\b", "Reactor"),
    (r"\bPBMR\b", "Reactor"),
    # Fuel salts
    (r"LiF-BeF2-ZrF4-UF4", "FuelSalt"),
    (r"LiF-BeF2-ThF4-UF4", "FuelSalt"),
    (r"NaCl-UCl3", "FuelSalt"),
    (r"FLiBe\b", "FuelSalt"),
    (r"FLiNaK\b", "FuelSalt"),
    # Materials
    (r"Hastelloy[\s-]?N\b", "StructuralMaterial"),
    (r"INOR-8\b", "StructuralMaterial"),
    (r"Inconel[\s-]?\d+", "StructuralMaterial"),
    # Simulation codes
    (r"\bMCNP\d?\b", "SimulationCode"),
    (r"\bSerpent\s*\d?\b", "SimulationCode"),
    (r"\bOpenMC\b", "SimulationCode"),
    (r"\bMPACT\b", "SimulationCode"),
    (r"\bSCALE\b", "SimulationCode"),
    (r"\bKENO\b", "SimulationCode"),
    # Cross-section libraries
    (r"ENDF/B[-\s]*(VII|VIII|VI)", "CrossSectionLibrary"),
    (r"JEFF[-\s]*\d+\.\d+", "CrossSectionLibrary"),
    (r"JENDL[-\s]*\d+", "CrossSectionLibrary"),
    # Isotopes (common)
    (r"U-235\b", "Isotope"),
    (r"U-233\b", "Isotope"),
    (r"U-238\b", "Isotope"),
    (r"Pu-239\b", "Isotope"),
    (r"Th-232\b", "Isotope"),
]
