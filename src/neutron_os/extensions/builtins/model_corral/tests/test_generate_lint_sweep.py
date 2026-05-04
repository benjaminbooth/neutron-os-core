"""Tests for generate, lint, and sweep commands.

Covers deterministic material generation (MCNP/MPACT), model linting with
all severity levels, and parametric sweep variant creation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from neutron_os.extensions.builtins.model_corral.commands.generate import (
    generate_materials,
)
from neutron_os.extensions.builtins.model_corral.commands.lint import (
    LintResult,
    cmd_lint,
    lint_model,
)
from neutron_os.extensions.builtins.model_corral.commands.sweep import sweep_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_MODEL = {
    "model_id": "test-model",
    "name": "Test Model",
    "version": "0.1.0",
    "status": "draft",
    "reactor_type": "TRIGA",
    "facility": "NETL",
    "physics_code": "MCNP",
    "physics_domain": ["neutronics"],
    "created_by": "test@example.com",
    "created_at": "2026-01-01T00:00:00Z",
    "access_tier": "facility",
    "description": "A test model for unit tests",
    "tags": ["test"],
    "materials": [
        {"name": "UZrH-20", "number": 1},
        {"name": "H2O", "number": 2},
    ],
}


def _write_model(tmp_path: Path, data: dict | None = None) -> Path:
    """Write model.yaml and return the model directory."""
    model_dir = tmp_path / "test-model"
    model_dir.mkdir(parents=True, exist_ok=True)
    payload = data if data is not None else MINIMAL_MODEL.copy()
    (model_dir / "model.yaml").write_text(
        yaml.dump(payload, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return model_dir


# =========================================================================
# Generate tests
# =========================================================================


class TestGenerateMaterials:
    """Tests for generate_materials()."""

    def test_mcnp_output_valid(self, tmp_path: Path) -> None:
        """generate_materials() produces valid MCNP cards from model.yaml."""
        model_dir = _write_model(tmp_path)
        result = generate_materials(model_dir, output_format="mcnp")
        # Should contain material card lines starting with 'm'
        assert "m1" in result
        assert "m2" in result
        # Should contain isotope ZAIDs (numeric)
        assert "$" in result  # MCNP inline comment with isotope name

    def test_mpact_output_valid(self, tmp_path: Path) -> None:
        """generate_materials() produces valid MPACT cards."""
        model_dir = _write_model(tmp_path)
        result = generate_materials(model_dir, output_format="mpact")
        assert "mat UZrH-20" in result
        assert "mat H2O" in result
        assert "g/cc" in result

    def test_deterministic_output(self, tmp_path: Path) -> None:
        """Same input = same output (run twice, compare)."""
        model_dir = _write_model(tmp_path)
        run1 = generate_materials(model_dir, output_format="mcnp")
        run2 = generate_materials(model_dir, output_format="mcnp")
        assert run1 == run2

    def test_missing_model_yaml(self, tmp_path: Path) -> None:
        """Missing model.yaml raises FileNotFoundError."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            generate_materials(empty_dir)

    def test_no_materials_section(self, tmp_path: Path) -> None:
        """No materials section raises ValueError."""
        data = MINIMAL_MODEL.copy()
        del data["materials"]
        model_dir = _write_model(tmp_path, data)
        with pytest.raises(ValueError, match="materials"):
            generate_materials(model_dir)

    def test_unknown_material_produces_warning(self, tmp_path: Path) -> None:
        """Unknown material name produces WARNING comment in output."""
        data = MINIMAL_MODEL.copy()
        data["materials"] = [{"name": "nonexistent-unobtanium", "number": 99}]
        model_dir = _write_model(tmp_path, data)
        result = generate_materials(model_dir)
        assert "WARNING" in result
        assert "nonexistent-unobtanium" in result

    def test_custom_mat_number_mapping(self, tmp_path: Path) -> None:
        """Custom mat_number mapping works."""
        data = MINIMAL_MODEL.copy()
        data["materials"] = [
            {"name": "UZrH-20", "number": 10},
            {"name": "H2O", "number": 20},
        ]
        model_dir = _write_model(tmp_path, data)
        result = generate_materials(model_dir, output_format="mcnp")
        assert "m10" in result
        assert "m20" in result

    def test_output_to_file(self, tmp_path: Path) -> None:
        """Output to file works (output_file parameter)."""
        model_dir = _write_model(tmp_path)
        out_file = tmp_path / "output" / "materials.txt"
        result = generate_materials(model_dir, output_file=out_file)
        assert out_file.exists()
        assert out_file.read_text(encoding="utf-8") == result

    def test_header_includes_metadata(self, tmp_path: Path) -> None:
        """Header includes model_id, version, physics_code."""
        model_dir = _write_model(tmp_path)
        result = generate_materials(model_dir, output_format="mcnp")
        assert "test-model" in result
        assert "v0.1.0" in result
        assert "MCNP" in result


# =========================================================================
# Lint tests
# =========================================================================


class TestLintModel:
    """Tests for lint_model()."""

    def test_clean_model_passes(self, tmp_path: Path) -> None:
        """Clean model passes (no errors)."""
        model_dir = _write_model(tmp_path)
        result = lint_model(model_dir)
        assert result.errors == 0
        assert result.clean is True

    def test_missing_model_yaml(self, tmp_path: Path) -> None:
        """Missing model.yaml produces error."""
        empty_dir = tmp_path / "no-model"
        empty_dir.mkdir()
        result = lint_model(empty_dir)
        assert result.errors >= 1
        rules = [f.rule for f in result.findings]
        assert "missing-manifest" in rules

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        """Invalid YAML produces error."""
        model_dir = tmp_path / "bad-yaml"
        model_dir.mkdir()
        (model_dir / "model.yaml").write_text("{{invalid: yaml: [", encoding="utf-8")
        result = lint_model(model_dir)
        assert result.errors >= 1
        rules = [f.rule for f in result.findings]
        assert "invalid-yaml" in rules

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        """Missing required fields produce errors."""
        data = {"description": "incomplete model"}
        model_dir = _write_model(tmp_path, data)
        result = lint_model(model_dir)
        assert result.errors >= 1
        missing_rules = [f for f in result.findings if f.rule == "missing-field"]
        missing_names = [f.message for f in missing_rules]
        for field_name in (
            "model_id",
            "name",
            "version",
            "reactor_type",
            "physics_code",
            "created_by",
        ):
            assert any(field_name in m for m in missing_names), (
                f"Expected missing-field error for {field_name}"
            )

    def test_non_semver_version(self, tmp_path: Path) -> None:
        """Non-semver version produces warning."""
        data = MINIMAL_MODEL.copy()
        data["version"] = "v1"
        model_dir = _write_model(tmp_path, data)
        result = lint_model(model_dir)
        rules = [f.rule for f in result.findings]
        assert "non-semver" in rules

    def test_todo_description(self, tmp_path: Path) -> None:
        """TODO description produces warning."""
        data = MINIMAL_MODEL.copy()
        data["description"] = "TODO fill this in later"
        model_dir = _write_model(tmp_path, data)
        result = lint_model(model_dir)
        rules = [f.rule for f in result.findings]
        assert "todo-description" in rules

    def test_unknown_material(self, tmp_path: Path) -> None:
        """Unknown material in materials section produces warning."""
        data = MINIMAL_MODEL.copy()
        data["materials"] = [{"name": "fake-material-xyz", "number": 1}]
        model_dir = _write_model(tmp_path, data)
        result = lint_model(model_dir)
        rules = [f.rule for f in result.findings]
        assert "unknown-material" in rules

    def test_missing_input_file(self, tmp_path: Path) -> None:
        """Missing referenced input_file produces error."""
        data = MINIMAL_MODEL.copy()
        data["input_files"] = [{"path": "deck.inp"}]
        model_dir = _write_model(tmp_path, data)
        result = lint_model(model_dir)
        assert result.errors >= 1
        rules = [f.rule for f in result.findings]
        assert "missing-file" in rules

    def test_changeme_facility(self, tmp_path: Path) -> None:
        """CHANGEME facility produces warning."""
        data = MINIMAL_MODEL.copy()
        data["facility"] = "CHANGEME"
        model_dir = _write_model(tmp_path, data)
        result = lint_model(model_dir)
        rules = [f.rule for f in result.findings]
        assert "no-facility" in rules

    def test_empty_tags(self, tmp_path: Path) -> None:
        """Empty tags produces info."""
        data = MINIMAL_MODEL.copy()
        data["tags"] = []
        model_dir = _write_model(tmp_path, data)
        result = lint_model(model_dir)
        rules = [f.rule for f in result.findings]
        assert "no-tags" in rules

    def test_lint_result_counts(self, tmp_path: Path) -> None:
        """lint_model returns LintResult with correct error/warning counts."""
        data = {"description": "TODO"}  # missing many required fields + todo desc
        model_dir = _write_model(tmp_path, data)
        result = lint_model(model_dir)
        assert isinstance(result, LintResult)
        actual_errors = sum(1 for f in result.findings if f.severity == "error")
        actual_warnings = sum(1 for f in result.findings if f.severity == "warning")
        assert result.errors == actual_errors
        assert result.warnings == actual_warnings

    def test_cmd_lint_json_output(self, tmp_path: Path, capsys) -> None:
        """cmd_lint JSON output format works."""
        model_dir = _write_model(tmp_path)
        cmd_lint(str(model_dir), output_format="json")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "errors" in data
        assert "warnings" in data
        assert "clean" in data
        assert "findings" in data
        assert isinstance(data["findings"], list)


# =========================================================================
# Sweep tests
# =========================================================================


class TestSweepModel:
    """Tests for sweep_model()."""

    def test_creates_n_variants(self, tmp_path: Path) -> None:
        """sweep_model() creates N variants from values list."""
        model_dir = _write_model(tmp_path)
        variants = sweep_model(model_dir, param="enrichment", values=["5", "10", "20"])
        assert len(variants) == 3
        for v in variants:
            assert v.exists()
            assert (v / "model.yaml").exists()

    def test_variant_model_id_pattern(self, tmp_path: Path) -> None:
        """Each variant has correct model_id (source-param-value pattern)."""
        model_dir = _write_model(tmp_path)
        variants = sweep_model(model_dir, param="enrichment", values=["5", "20"])
        for v in variants:
            vdata = yaml.safe_load((v / "model.yaml").read_text(encoding="utf-8"))
            assert vdata["model_id"].startswith("test-model-enrichment-")

    def test_variant_references_parent(self, tmp_path: Path) -> None:
        """Each variant references parent_model = source model_id."""
        model_dir = _write_model(tmp_path)
        variants = sweep_model(model_dir, param="enrichment", values=["5"])
        vdata = yaml.safe_load((variants[0] / "model.yaml").read_text(encoding="utf-8"))
        assert vdata["parent_model"] == "test-model"

    def test_parameter_value_set(self, tmp_path: Path) -> None:
        """Parameter value is correctly set in variant model.yaml."""
        model_dir = _write_model(tmp_path)
        variants = sweep_model(model_dir, param="enrichment", values=["19.75"])
        vdata = yaml.safe_load((variants[0] / "model.yaml").read_text(encoding="utf-8"))
        assert vdata["enrichment"] == pytest.approx(19.75)

    def test_nested_parameter_dot_notation(self, tmp_path: Path) -> None:
        """Nested parameter (dot notation) works."""
        model_dir = _write_model(tmp_path)
        variants = sweep_model(model_dir, param="fuel.enrichment", values=["5"])
        vdata = yaml.safe_load((variants[0] / "model.yaml").read_text(encoding="utf-8"))
        assert vdata["fuel"]["enrichment"] == 5

    def test_source_files_copied(self, tmp_path: Path) -> None:
        """All source files are copied to variants."""
        model_dir = _write_model(tmp_path)
        # Add an extra file to the source
        (model_dir / "deck.inp").write_text("test input deck", encoding="utf-8")
        variants = sweep_model(model_dir, param="enrichment", values=["5"])
        assert (variants[0] / "deck.inp").exists()
        assert (variants[0] / "deck.inp").read_text(encoding="utf-8") == "test input deck"

    def test_missing_model_yaml(self, tmp_path: Path) -> None:
        """Missing model.yaml raises FileNotFoundError."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            sweep_model(empty_dir, param="x", values=["1"])

    def test_custom_output_dir(self, tmp_path: Path) -> None:
        """Custom output_dir works."""
        model_dir = _write_model(tmp_path)
        out = tmp_path / "sweeps"
        variants = sweep_model(
            model_dir,
            param="enrichment",
            values=["5"],
            output_dir=out,
        )
        assert len(variants) == 1
        assert variants[0].parent == out
