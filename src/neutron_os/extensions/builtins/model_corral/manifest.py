"""Model manifest parser and validator.

Validates model.yaml files against the Model Corral JSON Schema,
checks file references, and enforces domain-specific rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from axiom.infra.manifest import validate_yaml_schema

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "model-schema.json"
_SCHEMA: dict | None = None


def _get_schema() -> dict:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


@dataclass
class ManifestResult:
    """Result of manifest validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)


def parse_model_yaml(data: dict) -> ManifestResult:
    """Validate a parsed model.yaml dict against the schema.

    Returns a ManifestResult with valid=True if all checks pass.
    """
    schema = _get_schema()
    errors = validate_yaml_schema(data, schema)

    if errors:
        return ManifestResult(valid=False, errors=errors, data=data)

    return ManifestResult(valid=True, data=data)


def validate_model_dir(model_dir: Path) -> ManifestResult:
    """Validate a model directory: schema check + file reference check.

    Validation levels (per spec §10.1):
    1. Schema — model.yaml conforms to JSON Schema
    2. Files — all referenced input_files exist
    """
    model_yaml = model_dir / "model.yaml"
    if not model_yaml.exists():
        return ManifestResult(
            valid=False,
            errors=[f"model.yaml not found in {model_dir}"],
        )

    try:
        data = yaml.safe_load(model_yaml.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return ManifestResult(valid=False, errors=[f"YAML parse error: {e}"])

    if not isinstance(data, dict):
        return ManifestResult(valid=False, errors=["model.yaml must be a YAML mapping"])

    # Level 1: Schema validation
    result = parse_model_yaml(data)
    if not result.valid:
        return result

    # Level 2: File reference check
    file_errors = []
    for entry in data.get("input_files", []):
        ref_path = model_dir / entry.get("path", "")
        if not ref_path.exists():
            file_errors.append(f"Referenced file not found: {entry['path']}")

    if file_errors:
        return ManifestResult(valid=False, errors=file_errors, data=data)

    return ManifestResult(valid=True, data=data)
