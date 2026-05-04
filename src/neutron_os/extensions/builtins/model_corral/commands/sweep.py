"""neut model sweep — generate parametric model variants.

Creates N copies of a model with a parameter varied across specified values.
Each variant gets full lineage tracking back to the source model.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml


def sweep_model(
    model_dir: Path,
    *,
    param: str,
    values: list[str],
    output_dir: Path | None = None,
) -> list[Path]:
    """Generate parametric variants of a model.

    Args:
        model_dir: Source model directory.
        param: YAML key path to vary (dot-separated, e.g., "enrichment").
        values: List of values to substitute.
        output_dir: Where to put variants (defaults to model_dir parent).

    Returns:
        List of created variant directories.
    """
    model_yaml = model_dir / "model.yaml"
    if not model_yaml.exists():
        raise FileNotFoundError(f"model.yaml not found in {model_dir}")

    data = yaml.safe_load(model_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("model.yaml must be a mapping")

    base = output_dir or model_dir.parent
    base.mkdir(parents=True, exist_ok=True)
    source_id = data.get("model_id", model_dir.name)

    variants = []
    for val in values:
        # Create variant name
        safe_val = str(val).replace(".", "p")
        variant_name = f"{source_id}-{param}-{safe_val}"
        variant_dir = base / variant_name

        if variant_dir.exists():
            shutil.rmtree(variant_dir)

        # Copy all files
        shutil.copytree(model_dir, variant_dir)

        # Modify the parameter in model.yaml
        variant_data = yaml.safe_load((variant_dir / "model.yaml").read_text(encoding="utf-8"))
        variant_data["model_id"] = variant_name
        variant_data["name"] = f"{data.get('name', source_id)} ({param}={val})"
        variant_data["parent_model"] = source_id

        # Set the parameter value (supports nested via dot notation)
        _set_nested(variant_data, param, _coerce_value(val))

        # Bump version to indicate variant
        variant_data["version"] = "0.1.0"
        variant_data["status"] = "draft"

        (variant_dir / "model.yaml").write_text(
            yaml.dump(variant_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        variants.append(variant_dir)

    return variants


def _set_nested(data: dict, key_path: str, value) -> None:
    """Set a value in a nested dict using dot-separated path."""
    keys = key_path.split(".")
    d = data
    for k in keys[:-1]:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


def _coerce_value(val: str):
    """Try to coerce a string to int, float, or leave as string."""
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def cmd_sweep(
    path: str,
    *,
    param: str,
    values: str,
    output_dir: str | None = None,
    output_json: bool = False,
) -> int:
    """CLI entry point for neut model sweep."""
    import json

    model_dir = Path(path)
    value_list = [v.strip() for v in values.split(",")]

    try:
        variants = sweep_model(
            model_dir,
            param=param,
            values=value_list,
            output_dir=Path(output_dir) if output_dir else None,
        )
        if output_json:
            print(json.dumps([str(v) for v in variants], indent=2))
        else:
            print(f"Generated {len(variants)} variant(s):")
            for v in variants:
                print(f"  {v}/")
            print(f"\nAll variants reference parent: {model_dir.name}")
        return 0
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1
