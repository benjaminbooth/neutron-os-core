"""Tests for auto-add — MCNP file detection, metadata extraction, and in-place registration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from neutron_os.extensions.builtins.model_corral.commands.auto_add import (
    auto_add_mcnp,
    extract_mcnp_metadata,
    find_mcnp_files,
    is_mcnp_file,
)

SAMPLE_MCNP = """\
NETL TRIGA Steady State k-eff calculation

c Cell cards
1  1  -6.0   -1 2 -3     imp:n=1  $ fuel
2  2  -0.998  1 -4 2 -3  imp:n=1  $ water
3  0          4:-2:3      imp:n=0  $ void

c Surface cards
1  cz  1.8256
2  pz  0.0
3  pz  38.1
4  cz  20.0

c Data cards
m1   92235.80c  3.44e-3  92238.80c  1.37e-2  $ UZrH fuel
     40090.80c  3.30e-2  1001.80c   5.55e-2
mt1  zr-h.40t
m2   1001.80c   6.67e-2  8016.80c   3.33e-2  $ water
mt2  lwtr.20t
"""


# ---------------------------------------------------------------------------
# MCNP detection
# ---------------------------------------------------------------------------


def test_is_mcnp_file_by_i_extension(tmp_path: Path) -> None:
    f = tmp_path / "input.i"
    f.write_text("title card\n")
    assert is_mcnp_file(f)


def test_is_mcnp_file_by_inp_extension(tmp_path: Path) -> None:
    f = tmp_path / "model.inp"
    f.write_text("title card\n")
    assert is_mcnp_file(f)


def test_is_mcnp_file_by_mcnp_extension(tmp_path: Path) -> None:
    f = tmp_path / "deck.mcnp"
    f.write_text("title card\n")
    assert is_mcnp_file(f)


def test_is_mcnp_file_by_content(tmp_path: Path) -> None:
    f = tmp_path / "unknown.txt"
    f.write_text("Title card\n\nc cell cards\n1 1 -1.0 -1\n")
    assert is_mcnp_file(f)


def test_is_not_mcnp_python_file(tmp_path: Path) -> None:
    f = tmp_path / "script.py"
    f.write_text("import os\nprint('hello')\n# comment\n")
    assert not is_mcnp_file(f)


def test_find_mcnp_files(tmp_path: Path) -> None:
    (tmp_path / "a.i").write_text("deck a\n")
    (tmp_path / "b.inp").write_text("deck b\n")
    (tmp_path / "c.py").write_text("not mcnp\n")
    files = find_mcnp_files(tmp_path)
    names = {f.name for f in files}
    assert "a.i" in names
    assert "b.inp" in names
    assert "c.py" not in names


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------


def test_extract_title(tmp_path: Path) -> None:
    f = tmp_path / "deck.i"
    f.write_text(SAMPLE_MCNP)
    meta = extract_mcnp_metadata(f)
    assert meta["title"] == "NETL TRIGA Steady State k-eff calculation"


def test_extract_material_numbers(tmp_path: Path) -> None:
    f = tmp_path / "deck.i"
    f.write_text(SAMPLE_MCNP)
    meta = extract_mcnp_metadata(f)
    assert 1 in meta["material_numbers"]
    assert 2 in meta["material_numbers"]


def test_extract_sab(tmp_path: Path) -> None:
    f = tmp_path / "deck.i"
    f.write_text(SAMPLE_MCNP)
    meta = extract_mcnp_metadata(f)
    assert meta["has_sab"] is True


# ---------------------------------------------------------------------------
# Auto-add (in-place — no subdirectory)
# ---------------------------------------------------------------------------


def test_auto_add_creates_model_yaml_in_place(tmp_path: Path) -> None:
    """model.yaml is created ALONGSIDE the input file, not in a subdirectory."""
    f = tmp_path / "input.i"
    f.write_text(SAMPLE_MCNP)
    model_dir = auto_add_mcnp(f)
    assert model_dir == tmp_path  # same directory
    assert (tmp_path / "model.yaml").exists()
    assert (tmp_path / "input.i").exists()  # original untouched


def test_auto_add_no_file_copy(tmp_path: Path) -> None:
    """Original file is NOT copied — model.yaml references it in place."""
    f = tmp_path / "triga_ss.i"
    f.write_text(SAMPLE_MCNP)
    auto_add_mcnp(f)
    # No subdirectory created
    assert not (tmp_path / "triga-ss").exists()
    # Original file untouched
    assert f.read_text() == SAMPLE_MCNP


def test_auto_add_model_yaml_content(tmp_path: Path) -> None:
    f = tmp_path / "triga_ss.i"
    f.write_text(SAMPLE_MCNP)
    model_dir = auto_add_mcnp(f)
    manifest = yaml.safe_load((model_dir / "model.yaml").read_text())
    assert manifest["physics_code"] == "MCNP"
    assert manifest["status"] == "draft"
    assert manifest["name"] == "NETL TRIGA Steady State k-eff calculation"
    assert "auto-registered" in manifest["tags"]
    assert manifest["input_files"][0]["path"] == "triga_ss.i"


def test_auto_add_model_id_from_directory(tmp_path: Path) -> None:
    """model_id is derived from directory name, not filename."""
    subdir = tmp_path / "my-triga-analysis"
    subdir.mkdir()
    f = subdir / "input.i"
    f.write_text(SAMPLE_MCNP)
    auto_add_mcnp(f)
    manifest = yaml.safe_load((subdir / "model.yaml").read_text())
    assert manifest["model_id"] == "my-triga-analysis"


def test_auto_add_detects_material_numbers(tmp_path: Path) -> None:
    f = tmp_path / "deck.i"
    f.write_text(SAMPLE_MCNP)
    model_dir = auto_add_mcnp(f)
    manifest = yaml.safe_load((model_dir / "model.yaml").read_text())
    assert manifest["_detected_material_numbers"] == [1, 2]


def test_auto_add_finds_all_mcnp_files_in_dir(tmp_path: Path) -> None:
    """If directory has multiple MCNP files, all are listed in input_files."""
    (tmp_path / "steady.i").write_text(SAMPLE_MCNP)
    (tmp_path / "transient.inp").write_text("Transient calc\n\nc cells\n")
    auto_add_mcnp(tmp_path / "steady.i")
    manifest = yaml.safe_load((tmp_path / "model.yaml").read_text())
    paths = [f["path"] for f in manifest["input_files"]]
    assert "steady.i" in paths
    assert "transient.inp" in paths


def test_auto_add_rejects_existing_model_yaml(tmp_path: Path) -> None:
    """If model.yaml already exists, refuse to overwrite."""
    f = tmp_path / "input.i"
    f.write_text(SAMPLE_MCNP)
    (tmp_path / "model.yaml").write_text("existing: true\n")
    with pytest.raises(FileExistsError, match="model.yaml already exists"):
        auto_add_mcnp(f)


def test_auto_add_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        auto_add_mcnp(tmp_path / "nonexistent.i")


def test_auto_add_not_mcnp(tmp_path: Path) -> None:
    f = tmp_path / "readme.txt"
    f.write_text("This is not MCNP\nhas content\non multiple lines")
    with pytest.raises(ValueError, match="Not an MCNP file"):
        auto_add_mcnp(f)


def test_auto_add_gitignore_created(tmp_path: Path) -> None:
    """In a git repo, .gitignore should be created/updated."""
    # Simulate git repo
    (tmp_path / ".git").mkdir()
    f = tmp_path / "input.i"
    f.write_text(SAMPLE_MCNP)

    from unittest import mock

    with mock.patch(
        "neutron_os.extensions.builtins.model_corral.commands.auto_add._git_info",
        return_value={
            "in_repo": True,
            "branch": "main",
            "commit": "abc123",
            "dirty": False,
            "author": "nick@utexas.edu",
            "remote": "",
        },
    ):
        auto_add_mcnp(f)

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert ".neut/" in content
    assert "outp" in content  # MCNP output file


def test_auto_add_git_provenance(tmp_path: Path) -> None:
    """Git state is captured in model.yaml."""
    f = tmp_path / "input.i"
    f.write_text(SAMPLE_MCNP)

    from unittest import mock

    with mock.patch(
        "neutron_os.extensions.builtins.model_corral.commands.auto_add._git_info",
        return_value={
            "in_repo": True,
            "branch": "feat/new-rods",
            "commit": "abc123",
            "dirty": False,
            "author": "nick@utexas.edu",
            "remote": "git@github.com:lab/models.git",
        },
    ):
        auto_add_mcnp(f)

    manifest = yaml.safe_load((tmp_path / "model.yaml").read_text())
    assert manifest["_git"]["branch"] == "feat/new-rods"
    assert manifest["_git"]["commit"] == "abc123"
    assert manifest["created_by"] == "nick@utexas.edu"


# ---------------------------------------------------------------------------
# Context-aware path defaults (CLI parser)
# ---------------------------------------------------------------------------


def test_validate_default_path() -> None:
    from neutron_os.extensions.builtins.model_corral.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["validate"])
    assert args.path == "."


def test_add_default_path() -> None:
    from neutron_os.extensions.builtins.model_corral.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["add"])
    assert args.path == "."


def test_generate_default_path() -> None:
    from neutron_os.extensions.builtins.model_corral.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["generate"])
    assert args.path == "."


def test_lint_default_path() -> None:
    from neutron_os.extensions.builtins.model_corral.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["lint"])
    assert args.path == "."


def test_explicit_path_still_works() -> None:
    from neutron_os.extensions.builtins.model_corral.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["validate", "/some/path"])
    assert args.path == "/some/path"
