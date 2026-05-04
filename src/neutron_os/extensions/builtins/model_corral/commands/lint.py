"""neut model lint — standardization checks for physics models.

Checks model directories against best practices and CoreForge-aligned
conventions. Returns actionable findings with severity levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class LintFinding:
    """A single lint finding."""

    severity: str  # "error", "warning", "info"
    rule: str
    message: str
    file: str = ""
    line: int = 0

    def to_dict(self) -> dict:
        d = {"severity": self.severity, "rule": self.rule, "message": self.message}
        if self.file:
            d["file"] = self.file
        if self.line:
            d["line"] = self.line
        return d


@dataclass
class LintResult:
    """Aggregate result of linting a model directory."""

    findings: list[LintFinding] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def clean(self) -> bool:
        return self.errors == 0

    def to_dict(self) -> dict:
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "clean": self.clean,
            "findings": [f.to_dict() for f in self.findings],
        }


def lint_model(model_dir: Path) -> LintResult:
    """Run all lint rules against a model directory."""
    result = LintResult()

    model_yaml = model_dir / "model.yaml"
    if not model_yaml.exists():
        result.findings.append(
            LintFinding("error", "missing-manifest", "model.yaml not found", str(model_dir))
        )
        return result

    try:
        data = yaml.safe_load(model_yaml.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        result.findings.append(
            LintFinding("error", "invalid-yaml", f"YAML parse error: {e}", "model.yaml")
        )
        return result

    if not isinstance(data, dict):
        result.findings.append(
            LintFinding("error", "invalid-manifest", "model.yaml must be a mapping", "model.yaml")
        )
        return result

    # Run all rules
    _check_required_fields(data, result)
    _check_naming_conventions(data, result)
    _check_version_format(data, result)
    _check_description_quality(data, result)
    _check_materials_section(data, model_dir, result)
    _check_input_files(data, model_dir, result)
    _check_metadata_completeness(data, result)
    _check_directory_hygiene(model_dir, result)

    return result


def _check_required_fields(data: dict, result: LintResult) -> None:
    required = ["model_id", "name", "version", "reactor_type", "physics_code", "created_by"]
    for field_name in required:
        if field_name not in data:
            result.findings.append(
                LintFinding(
                    "error", "missing-field", f"Required field missing: {field_name}", "model.yaml"
                )
            )


def _check_naming_conventions(data: dict, result: LintResult) -> None:
    import re

    model_id = data.get("model_id", "")
    if model_id and not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", model_id):
        result.findings.append(
            LintFinding(
                "error",
                "invalid-model-id",
                f"model_id must be lowercase alphanumeric with hyphens: {model_id!r}",
                "model.yaml",
            )
        )


def _check_version_format(data: dict, result: LintResult) -> None:
    import re

    version = data.get("version", "")
    if version and not re.match(r"^\d+\.\d+\.\d+$", version):
        result.findings.append(
            LintFinding(
                "warning", "non-semver", f"Version should be semver: {version!r}", "model.yaml"
            )
        )


def _check_description_quality(data: dict, result: LintResult) -> None:
    desc = data.get("description", "")
    if not desc:
        result.findings.append(
            LintFinding("warning", "missing-description", "No description provided", "model.yaml")
        )
    elif desc.startswith("TODO"):
        result.findings.append(
            LintFinding(
                "warning",
                "todo-description",
                "Description is still a TODO placeholder",
                "model.yaml",
            )
        )
    elif len(desc) < 10:
        result.findings.append(
            LintFinding("info", "short-description", "Description is very short", "model.yaml")
        )


def _check_materials_section(data: dict, model_dir: Path, result: LintResult) -> None:
    materials = data.get("materials", [])
    if not materials:
        result.findings.append(
            LintFinding(
                "info", "no-materials", "No materials section — consider adding one", "model.yaml"
            )
        )
        return

    from neutron_os.extensions.builtins.model_corral.materials_db import get_material

    for mat_ref in materials:
        mat_name = mat_ref if isinstance(mat_ref, str) else mat_ref.get("name", "")
        if mat_name and get_material(mat_name) is None:
            result.findings.append(
                LintFinding(
                    "warning",
                    "unknown-material",
                    f"Material not in registry: {mat_name}",
                    "model.yaml",
                )
            )


def _check_input_files(data: dict, model_dir: Path, result: LintResult) -> None:
    for entry in data.get("input_files", []):
        path = entry.get("path", "")
        if path:
            full = model_dir / path
            if not full.exists():
                result.findings.append(
                    LintFinding(
                        "error", "missing-file", f"Referenced file not found: {path}", "model.yaml"
                    )
                )
            elif full.stat().st_size == 0:
                result.findings.append(
                    LintFinding(
                        "warning", "empty-file", f"Referenced file is empty: {path}", str(path)
                    )
                )


def _check_metadata_completeness(data: dict, result: LintResult) -> None:
    if not data.get("tags"):
        result.findings.append(
            LintFinding("info", "no-tags", "No tags — harder to find via search", "model.yaml")
        )

    if data.get("facility") in ("", "CHANGEME"):
        result.findings.append(
            LintFinding("warning", "no-facility", "Facility not set", "model.yaml")
        )

    if not data.get("access_tier"):
        result.findings.append(
            LintFinding(
                "info",
                "no-access-tier",
                "No access_tier set (defaults to 'facility')",
                "model.yaml",
            )
        )


def _check_directory_hygiene(model_dir: Path, result: LintResult) -> None:
    # Check for common junk files
    junk_patterns = [".DS_Store", "Thumbs.db", "__pycache__", "*.pyc"]
    for pattern in junk_patterns:
        for match in model_dir.rglob(pattern):
            result.findings.append(
                LintFinding(
                    "info",
                    "junk-file",
                    f"Consider removing: {match.relative_to(model_dir)}",
                    str(match.relative_to(model_dir)),
                )
            )

    # Check for very large files
    for f in model_dir.rglob("*"):
        if f.is_file() and f.stat().st_size > 100_000_000:  # 100MB
            result.findings.append(
                LintFinding(
                    "warning",
                    "large-file",
                    f"File is very large ({f.stat().st_size / 1e6:.0f}MB): "
                    f"{f.relative_to(model_dir)}",
                    str(f.relative_to(model_dir)),
                )
            )


def cmd_lint(path: str, *, output_format: str = "human") -> int:
    """CLI entry point for neut model lint."""
    import json

    model_dir = Path(path)
    result = lint_model(model_dir)

    if output_format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.clean and result.warnings == 0:
            print(f"Lint clean: {model_dir}")
            return 0

        for f in result.findings:
            icon = {"error": "E", "warning": "W", "info": "I"}.get(f.severity, "?")
            loc = f"  {f.file}" if f.file else ""
            print(f"  [{icon}] {f.rule}: {f.message}{loc}")

        print(f"\n{result.errors} error(s), {result.warnings} warning(s)")

    return 1 if result.errors > 0 else 0
