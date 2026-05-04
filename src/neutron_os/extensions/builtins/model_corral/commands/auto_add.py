"""Auto-add — register an MCNP input deck with minimal effort.

When the user runs ``neut model add ./input.i`` (a file, not a directory),
generates model.yaml alongside the file (in the same directory) and registers it.
No subdirectory created, no file copied. Works naturally with git.

When the user runs ``neut model add .`` from a directory containing MCNP files
but no model.yaml, auto-generates model.yaml from the detected files.
"""

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

MCNP_EXTENSIONS = {".i", ".inp", ".mcnp"}


def is_mcnp_file(path: Path) -> bool:
    """Detect if a file is an MCNP input deck."""
    if path.suffix.lower() in MCNP_EXTENSIONS:
        return True
    # Check content: MCNP files have a title card on line 1,
    # then blank line, then cell cards
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:10]
        if len(lines) >= 3 and lines[1].strip() == "":
            return True  # title card + blank line pattern
    except Exception:
        pass
    return False


def find_mcnp_files(directory: Path) -> list[Path]:
    """Find all MCNP input files in a directory."""
    files = []
    for ext in MCNP_EXTENSIONS:
        files.extend(directory.glob(f"*{ext}"))
    return sorted(files)


def extract_mcnp_metadata(path: Path) -> dict:
    """Extract metadata from an MCNP input deck.

    Returns dict with title, material_numbers, and any other detectable info.
    """
    content = path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    metadata: dict = {
        "title": lines[0].strip() if lines else path.stem,
        "material_numbers": [],
        "has_sab": False,
    }

    # Find material card numbers (m1, m2, m10, etc.)
    mat_pattern = re.compile(r"^m(\d+)\s", re.IGNORECASE)
    sab_pattern = re.compile(r"^mt\d+\s", re.IGNORECASE)

    for line in lines:
        mat_match = mat_pattern.match(line)
        if mat_match:
            metadata["material_numbers"].append(int(mat_match.group(1)))
        if sab_pattern.match(line):
            metadata["has_sab"] = True

    return metadata


def _git_info(directory: Path) -> dict:
    """Capture git state for provenance."""
    info = {"in_repo": False}
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=directory,
        )
        if result.returncode != 0:
            return info
        info["in_repo"] = True

        # Branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=directory,
        )
        info["branch"] = result.stdout.strip() if result.returncode == 0 else ""

        # Commit hash
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=directory,
        )
        info["commit"] = result.stdout.strip() if result.returncode == 0 else ""

        # Dirty state
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=directory,
        )
        info["dirty"] = bool(result.stdout.strip()) if result.returncode == 0 else False

        # Author
        result = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=directory,
        )
        info["author"] = result.stdout.strip() if result.returncode == 0 else ""

        # Remote URL (for provenance)
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=directory,
        )
        info["remote"] = result.stdout.strip() if result.returncode == 0 else ""

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return info


def _ensure_gitignore(directory: Path) -> None:
    """Add Model Corral entries to .gitignore if in a git repo."""
    gitignore = directory / ".gitignore"
    entries = [
        "# Model Corral local state",
        ".neut/",
        "*.db",
        "",
        "# MCNP output files (large, regenerable)",
        "outp",
        "meshtal",
        "mctal",
        "srctp",
        "runtpe",
        "comout",
    ]

    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        # Only add entries not already present
        new_entries = [e for e in entries if e and e not in content]
        if new_entries:
            addition = "\n" + "\n".join(new_entries) + "\n"
            gitignore.write_text(content.rstrip() + addition, encoding="utf-8")
    else:
        gitignore.write_text("\n".join(entries) + "\n", encoding="utf-8")


def auto_add_mcnp(
    file_path: Path,
    message: str = "",
    reactor_type: str = "custom",
    facility: str = "",
) -> Path:
    """Generate model.yaml alongside an MCNP file and prepare for registration.

    DOES NOT create a subdirectory or copy files. model.yaml is created in the
    same directory as the input file. This works naturally with existing git repos.

    Args:
        file_path: Path to MCNP input file.
        message: Description message.
        reactor_type: Reactor type.
        facility: Facility.

    Returns:
        Path to the directory containing model.yaml (same as file's parent).
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not is_mcnp_file(file_path):
        raise ValueError(f"Not an MCNP file: {file_path}")

    model_dir = file_path.parent.resolve()
    metadata = extract_mcnp_metadata(file_path)

    # Generate model_id from directory name (not file name)
    dir_name = model_dir.name.lower()
    model_id = re.sub(r"[^a-z0-9]+", "-", dir_name).strip("-")
    if len(model_id) < 3:
        # Fall back to filename
        model_id = re.sub(r"[^a-z0-9]+", "-", file_path.stem.lower()).strip("-")
    if len(model_id) < 3:
        model_id = f"model-{model_id}"

    # Capture git provenance
    git = _git_info(model_dir)
    author = git.get("author", "")
    if not author:
        author = "unknown@example.com"

    # Smart facility default
    if not facility:
        facility_defaults = {"TRIGA": "NETL", "MSR": "ORNL", "PWR": "generic"}
        facility = facility_defaults.get(reactor_type.upper(), "")

    # Find all MCNP files in directory
    mcnp_files = find_mcnp_files(model_dir)
    input_files = [{"path": f.name, "format": "mcnp"} for f in mcnp_files]

    # Build model.yaml
    manifest: dict = {
        "model_id": model_id,
        "name": metadata["title"][:80] if metadata["title"] else model_id.replace("-", " ").title(),
        "version": "0.1.0",
        "status": "draft",
        "reactor_type": reactor_type,
        "facility": facility or "unknown",
        "physics_code": "MCNP",
        "physics_domain": ["neutronics"],
        "created_by": author,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "access_tier": "facility",
        "description": message or f"{metadata['title']} — auto-registered from {file_path.name}",
        "tags": ["auto-registered"],
        "input_files": input_files,
    }

    # Add detected materials
    if metadata["material_numbers"]:
        manifest["_detected_material_numbers"] = sorted(metadata["material_numbers"])

    # Add git provenance
    if git["in_repo"]:
        manifest["_git"] = {
            "branch": git.get("branch", ""),
            "commit": git.get("commit", ""),
            "remote": git.get("remote", ""),
        }

    # Write model.yaml alongside the input file
    model_yaml = model_dir / "model.yaml"
    if model_yaml.exists():
        raise FileExistsError(
            f"model.yaml already exists in {model_dir}. "
            f"Use `neut model add {model_dir}` to register the existing model."
        )

    (model_dir / "model.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # Manage .gitignore
    if git["in_repo"]:
        _ensure_gitignore(model_dir)

    return model_dir
