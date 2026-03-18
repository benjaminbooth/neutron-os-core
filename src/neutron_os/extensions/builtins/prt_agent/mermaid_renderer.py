"""Render Mermaid diagrams in markdown to PNG images before pandoc conversion.

Pre-processes a .md file: finds ```mermaid``` code blocks, renders them
via mermaid.ink API, replaces with image references.

Usage:
    from neutron_os.extensions.builtins.prt_agent.mermaid_renderer import render_mermaid_blocks

    processed_md = render_mermaid_blocks(md_content, output_dir)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import urllib.request
import zlib
from pathlib import Path

logger = logging.getLogger(__name__)

_MERMAID_INK_BASE = "https://mermaid.ink/img/pako:"
_CACHE_DIR_NAME = "mermaid_cache"


def _render_diagram(code: str, output_dir: Path, index: int) -> Path | None:
    """Render a single mermaid diagram to PNG via mermaid.ink."""
    # Use content hash for caching
    code_hash = hashlib.md5(code.encode()).hexdigest()[:8]
    cache_dir = output_dir / _CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"diagram_{code_hash}.png"

    if cached.exists() and cached.stat().st_size > 100:
        return cached

    # Encode: JSON → zlib compress → base64url (no padding)
    # Use wider rendering for complex diagrams (gantt, large flowcharts)
    width = 1200
    if "gantt" in code.lower() or code.count("subgraph") > 2 or code.count("-->") > 15:
        width = 1800

    payload = json.dumps({
        "code": code,
        "mermaid": {"theme": "default"},
        "width": width,
    })
    compressed = zlib.compress(payload.encode(), 9)
    encoded = base64.urlsafe_b64encode(compressed).decode().rstrip("=")

    url = f"{_MERMAID_INK_BASE}{encoded}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (NeutronOS PR-T)",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()

        if len(content) < 100:
            logger.warning("Mermaid render returned tiny image (%d bytes)", len(content))
            return None

        cached.write_bytes(content)
        logger.info("Rendered diagram %d (%d bytes) → %s", index, len(content), cached.name)
        return cached

    except Exception as e:
        logger.warning("Mermaid render failed for diagram %d: %s", index, e)
        return None


def render_mermaid_blocks(md_content: str, output_dir: Path) -> str:
    """Replace ```mermaid``` code blocks with rendered PNG image references.

    Args:
        md_content: Raw markdown content
        output_dir: Directory to save rendered images

    Returns:
        Processed markdown with mermaid blocks replaced by image references
    """
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)

    def replace_block(match, _counter=[0]):
        code = match.group(1).strip()
        _counter[0] += 1
        idx = _counter[0]

        img_path = _render_diagram(code, output_dir, idx)
        if img_path:
            # No alt text caption — just the image
            return f"![]({img_path})"
        else:
            # Fallback: keep as code block
            return f"```\n{code}\n```"

    return pattern.sub(replace_block, md_content)
