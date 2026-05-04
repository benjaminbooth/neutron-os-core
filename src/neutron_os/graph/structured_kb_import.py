"""Structured KB entity importer for the Axiom knowledge graph.

Imports pre-extracted entities from any JSON knowledge base that
follows the normalized entity format:

    {
      "category-name": [
        {"name": "entity name", "count": N, "line_hits": [1, 5, 12]}
      ]
    }

Each JSON file represents one source document. Categories are mapped
to Axiom entity types via a configurable mapping dict.

Designed to work with any deterministic KB compiler that produces
this format (e.g., Ondrej Chvala's MSR KB, or any domain-specific
knowledge compilation pipeline).

Usage::

    from axiom.graph.extractors.structured_kb import import_kb_entities

    # With default mapping (nuclear domain)
    stats = import_kb_entities(Path("kb/normalized/entities"))

    # With custom mapping
    stats = import_kb_entities(
        Path("kb/entities"),
        category_map={"protein": "Material", "gene": "Concept"},
    )
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from axiom.graph.schema import Edge, Entity

log = logging.getLogger(__name__)

# Map Ondrej's categories to Axiom entity labels
_CATEGORY_MAP = {
    "alloy-material": "Material",
    "salt-system": "Material",
    "organization": "Concept",  # Organizations as concepts (not Person)
    "component": "Component",
    "reactor": "Reactor",
    "reactor-concept": "Concept",
    "report-series": "Document",
}


@dataclass
class ImportStats:
    files_processed: int = 0
    entities_imported: int = 0
    edges_imported: int = 0
    categories: dict = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = {}


def load_kb_entities(
    entities_dir: Path,
    category_map: dict[str, str] | None = None,
) -> tuple[list[Entity], list[Edge]]:
    """Load entities from a normalized KB directory.

    Args:
        entities_dir: Path to directory containing *.json entity files
        category_map: Maps source categories to Axiom entity labels.
            If None, uses the default nuclear domain mapping.

    Returns:
        (entities, edges) ready for GraphStore.upsert
    """
    if category_map is None:
        category_map = dict(_CATEGORY_MAP)

    entities: list[Entity] = []
    edges: list[Edge] = []
    seen_entities: set[tuple[str, str]] = set()  # (label, name) dedup

    if not entities_dir.exists():
        log.warning("KB entities dir not found: %s", entities_dir)
        return [], []

    for json_file in sorted(entities_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        # The filename is the source document slug
        doc_slug = json_file.stem

        for category, items in data.items():
            label = _CATEGORY_MAP.get(category, "Concept")

            for item in items:
                name = item.get("name", "")
                if not name:
                    continue

                count = item.get("count", 1)
                line_hits = item.get("line_hits", [])

                # Dedup entities
                key = (label, name.lower())
                if key not in seen_entities:
                    seen_entities.add(key)
                    entities.append(Entity(
                        label=label,
                        name=name,
                        properties={
                            "category": category,
                            "mention_count": count,
                        },
                        confidence=1.0,
                        provenance="ondrej_kb",
                    ))

                # Edge: document DESCRIBES/REFERENCES this entity
                edges.append(Edge(
                    rel_type="DESCRIBES" if label != "Document" else "REFERENCES",
                    from_name=doc_slug,
                    from_label="Document",
                    to_name=name,
                    to_label=label,
                    properties={
                        "mention_count": count,
                        "line_hits": line_hits[:10],  # Truncate for storage
                    },
                    confidence=1.0,
                    provenance="ondrej_kb",
                ))

    return entities, edges


def import_kb_entities(
    entities_dir: Path,
    category_map: dict[str, str] | None = None,
) -> ImportStats:
    """Load and report stats on KB entity import.

    Does NOT write to AGE (caller decides storage).
    Returns entities, edges, and stats for logging.
    """
    entities, edges = load_kb_entities(entities_dir, category_map=category_map)

    # Count by category
    categories: dict[str, int] = {}
    for e in entities:
        cat = e.properties.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    stats = ImportStats(
        files_processed=len(list(entities_dir.glob("*.json"))),
        entities_imported=len(entities),
        edges_imported=len(edges),
        categories=categories,
    )

    log.info(
        "KB import: %d entities, %d edges from %d files",
        stats.entities_imported,
        stats.edges_imported,
        stats.files_processed,
    )

    return stats
