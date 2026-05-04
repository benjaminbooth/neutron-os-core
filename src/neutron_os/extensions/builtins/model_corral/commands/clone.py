"""neut model clone — pull a model and prepare it for editing as a fork."""

from __future__ import annotations

from pathlib import Path

import yaml


def model_clone(
    model_id: str,
    service,
    *,
    new_name: str = "",
    output_dir: Path | None = None,
) -> Path:
    """Clone a model from the registry for editing.

    1. Pulls the model files
    2. Renames to a new model_id (or auto-generates one)
    3. Sets parent_model to the original
    4. Bumps version to 0.1.0 (draft)
    5. Opens in IDE

    Args:
        model_id: Source model to clone.
        service: ModelCorralService instance.
        new_name: New model_id. Auto-generated if empty.
        output_dir: Where to create the clone. Defaults to cwd.

    Returns:
        Path to the cloned model directory.
    """
    base = output_dir or Path.cwd()

    # Generate a clone name if not provided
    if not new_name:
        new_name = _generate_clone_name(model_id, base)

    clone_dir = base / new_name
    if clone_dir.exists():
        raise FileExistsError(f"Directory already exists: {clone_dir}")

    # Pull the original
    result = service.pull(model_id, clone_dir)
    if not result.success:
        raise RuntimeError(f"Failed to pull {model_id}: {result.error}")

    # Update the manifest for the fork
    manifest_path = clone_dir / "model.yaml"
    if manifest_path.exists():
        # Strip yaml-language-server directive before loading
        text = manifest_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)

        data["model_id"] = new_name
        data["name"] = new_name.replace("-", " ").title()
        data["version"] = "0.1.0"
        data["status"] = "draft"
        data["parent_model"] = model_id
        data.pop("doi", None)  # DOI is for the original, not the fork

        # Preserve schema directive if present
        header = ""
        for line in text.splitlines():
            if line.startswith("# yaml-language-server"):
                header = line + "\n"
                break

        manifest_path.write_text(
            header + yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    # Update README
    readme = clone_dir / "README.md"
    if readme.exists():
        readme.write_text(
            f"# {new_name.replace('-', ' ').title()}\n\n"
            f"Forked from `{model_id}`.\n\n"
            f"TODO: describe your modifications.\n",
            encoding="utf-8",
        )

    return clone_dir


def _generate_clone_name(model_id: str, base: Path) -> str:
    """Generate a unique clone name by appending -fork or -fork-N."""
    candidate = f"{model_id}-fork"
    if not (base / candidate).exists():
        return candidate

    for i in range(2, 100):
        candidate = f"{model_id}-fork-{i}"
        if not (base / candidate).exists():
            return candidate

    raise RuntimeError(f"Could not generate unique clone name for {model_id}")
