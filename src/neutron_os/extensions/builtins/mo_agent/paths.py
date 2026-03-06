"""Platform-aware base directory resolution for M-O scratch space.

Resolution order:
1. NEUT_SCRATCH_DIR env var (explicit override)
2. Platform default:
   - macOS: ~/Library/Caches/neut/mo/
   - Linux: $XDG_RUNTIME_DIR/neut/mo/ or /tmp/neut-{uid}/mo/
   - Windows: %TEMP%/neut/mo/
3. Fallback: tempfile.gettempdir()/neut-mo
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def resolve_base_dir() -> Path:
    """Resolve the scratch base directory for M-O.

    Returns a Path that may or may not exist yet — the caller is responsible
    for creating it and handling permission errors.
    """
    # 1. Explicit override
    env_dir = os.environ.get("NEUT_SCRATCH_DIR")
    if env_dir:
        return Path(env_dir)

    # 2. Platform default
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "neut" / "mo"

    if sys.platform == "win32":
        temp = os.environ.get("TEMP", tempfile.gettempdir())
        return Path(temp) / "neut" / "mo"

    # Linux / other Unix
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return Path(xdg) / "neut" / "mo"

    return Path(tempfile.gettempdir()) / f"neut-{os.getuid()}" / "mo"
