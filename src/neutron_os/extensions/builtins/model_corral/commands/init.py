"""neut model init — scaffold a new model directory."""

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

_KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def _git_config(key: str) -> str:
    """Read a git config value, returning empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", key],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def model_init(
    name: str,
    *,
    reactor_type: str = "custom",
    physics_code: str = "MCNP",
    facility: str = "",
    output_dir: Path | None = None,
    include_materials: bool = False,
) -> Path:
    """Create a new model directory with model.yaml and README.md.

    Auto-populates created_by from git config user.email when available.

    Args:
        name: Model name (must be kebab-case).
        reactor_type: Reactor type enum value.
        physics_code: Physics code name.
        facility: Facility identifier (auto-detects if empty).
        output_dir: Parent directory (defaults to cwd).

    Returns:
        Path to created model directory.

    Raises:
        ValueError: If name is not valid kebab-case.
        FileExistsError: If directory already exists.
    """
    if not _KEBAB_RE.match(name):
        raise ValueError(
            f"Invalid model name: {name!r} — must be lowercase alphanumeric with hyphens"
        )

    base = output_dir or Path.cwd()
    model_dir = base / name

    if model_dir.exists():
        raise FileExistsError(f"Directory already exists: {model_dir}")

    model_dir.mkdir(parents=True)

    # Auto-detect author from git config
    author_email = _git_config("user.email") or "you@example.com"
    if not facility:
        # Smart defaults based on reactor type
        _facility_defaults = {
            "TRIGA": "NETL",
            "MSR": "ORNL",
            "PWR": "generic",
        }
        facility = (
            _facility_defaults.get(reactor_type.upper(), "generic") if reactor_type else "generic"
        )

    # Generate model.yaml
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    display_name = name.replace("-", " ").title()
    manifest = {
        "model_id": name,
        "name": display_name,
        "version": "0.1.0",
        "status": "draft",
        "reactor_type": reactor_type,
        "facility": facility,
        "physics_code": physics_code,
        "physics_domain": ["neutronics"],
        "created_by": author_email,
        "created_at": now,
        "access_tier": "facility",
        "description": f"{display_name} — {reactor_type} {physics_code} model",
        "tags": [],
    }

    # Pre-populate materials from installed facility pack
    if include_materials:
        materials_list = _suggest_materials(reactor_type)
        if materials_list:
            manifest["materials"] = materials_list

    # Find the schema path for the yaml-language-server directive
    schema_path = _find_schema_path(model_dir)

    # Write model.yaml with schema directive for VS Code YAML extension
    yaml_content = yaml.dump(manifest, default_flow_style=False, sort_keys=False)
    header = f"# yaml-language-server: $schema={schema_path}\n" if schema_path else ""
    (model_dir / "model.yaml").write_text(
        header + yaml_content,
        encoding="utf-8",
    )

    # Generate README.md
    readme = f"# {manifest['name']}\n\n{manifest['description']}\n"
    (model_dir / "README.md").write_text(readme, encoding="utf-8")

    # Editor integration
    _write_vscode_config(model_dir, schema_path)
    _write_editorconfig(model_dir)

    return model_dir


def _suggest_materials(reactor_type: str) -> list[dict]:
    """Suggest materials based on reactor type from installed facility packs."""
    try:
        from neutron_os.extensions.builtins.model_corral.facilities.registry import discover_packs

        for pack in discover_packs():
            if pack.manifest.reactor_type.upper() == reactor_type.upper():
                # Load material names from this pack
                from neutron_os.extensions.builtins.model_corral.materials_db import (
                    YamlMaterialSource,
                )

                source = YamlMaterialSource(pack.materials_path)
                mats = source.load()
                return [{"name": m.name, "number": i} for i, m in enumerate(mats, 1)]
    except Exception:
        pass
    return []


def _find_schema_path(model_dir: Path) -> str:
    """Locate the model-schema.json relative to the model directory."""
    # Try installed package location first
    schema = Path(__file__).parent.parent / "schemas" / "model-schema.json"
    if schema.exists():
        return schema.resolve().as_uri()
    return ""


def _write_vscode_config(model_dir: Path, schema_uri: str) -> None:
    """Write .vscode/ config for inline validation and recommended extensions."""
    import json

    vscode_dir = model_dir / ".vscode"
    vscode_dir.mkdir(exist_ok=True)

    # settings.json — schema association for all model.yaml files
    settings = {
        "yaml.schemas": {},
        "files.associations": {"model.yaml": "yaml"},
        "editor.formatOnSave": False,
    }
    if schema_uri:
        settings["yaml.schemas"][schema_uri] = "model.yaml"

    (vscode_dir / "settings.json").write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )

    # extensions.json — recommend YAML extension
    extensions = {
        "recommendations": [
            "redhat.vscode-yaml",
        ]
    }
    (vscode_dir / "extensions.json").write_text(
        json.dumps(extensions, indent=2) + "\n", encoding="utf-8"
    )


def _write_editorconfig(model_dir: Path) -> None:
    """Write .editorconfig — works with VS Code, vim, PyCharm, etc."""
    (model_dir / ".editorconfig").write_text(
        """\
root = true

[*]
indent_style = space
indent_size = 2
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.yaml]
indent_size = 2

[*.md]
trim_trailing_whitespace = false
""",
        encoding="utf-8",
    )
