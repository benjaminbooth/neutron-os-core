"""Extension discovery and loading.

Scans extension directories for valid packages with neut-extension.toml,
loads chat tools, skills, CLI commands, and provider registrations.

Discovery order (highest precedence first):
  1. Project extensions:  .neut/extensions/  (repo-local, found by walking cwd)
  2. User extensions:     ~/.neut/extensions/ (personal, cross-project)
  3. Builtin extensions:  tools/extensions/builtins/ (shipped with package)

Key design choice: uses importlib.util.spec_from_file_location() to load
user extension modules directly from file paths — no pip install, no sys.path
manipulation. Builtin extensions use importlib.import_module() since they are
part of the installed package.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import types
from pathlib import Path
from typing import Any

from neutron_os.extensions.contracts import (
    MANIFEST_FILENAME,
    Extension,
    Skill,
    parse_manifest,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extension directory resolution
# ---------------------------------------------------------------------------


def _builtin_extensions_dir() -> Path:
    """Builtin extensions shipped inside the package.

    Always relative to this file — works in source checkout AND installed wheel.
    """
    return Path(__file__).resolve().parent / "builtins"


def _project_extensions_dir() -> Path | None:
    """Project-local extensions: .neut/extensions/ relative to project root.

    Resolution order:
      1. NEUT_ROOT env var (explicit override)
      2. Walk up from cwd looking for a .neut/ directory

    Returns None if no project root is found (e.g. clean dir, no .neut/).
    """
    env_root = os.environ.get("NEUT_ROOT")
    if env_root:
        candidate = Path(env_root).resolve() / ".neut" / "extensions"
        if candidate.is_dir():
            return candidate
        return None

    path = Path.cwd().resolve()
    while path != path.parent:
        candidate = path / ".neut" / "extensions"
        if candidate.is_dir():
            return candidate
        path = path.parent

    return None


def _user_extensions_dir() -> Path:
    """User-level extensions: ~/.neut/extensions/."""
    return Path.home() / ".neut" / "extensions"


def get_extension_dirs() -> list[Path]:
    """Return extension directories in discovery order.

    Project-local takes precedence over user-level over builtins.
    Earlier entries win when names collide (user can override builtins).
    """
    dirs = []
    project_dir = _project_extensions_dir()
    if project_dir is not None and project_dir.is_dir():
        dirs.append(project_dir)
    user_dir = _user_extensions_dir()
    if user_dir.is_dir():
        dirs.append(user_dir)
    builtin_dir = _builtin_extensions_dir()
    if builtin_dir.is_dir():
        dirs.append(builtin_dir)
    return dirs


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_extensions(*search_dirs: Path) -> list[Extension]:
    """Scan extension directories for valid packages.

    Args:
        *search_dirs: Override default search dirs (for testing).
                      If empty, uses get_extension_dirs().

    Returns:
        List of Extension objects, deduplicated by name (first wins).
    """
    dirs = list(search_dirs) if search_dirs else get_extension_dirs()
    seen_names: set[str] = set()
    extensions: list[Extension] = []

    for ext_dir in dirs:
        if not ext_dir.is_dir():
            continue
        for child in sorted(ext_dir.iterdir()):
            if not child.is_dir():
                continue
            manifest = child / MANIFEST_FILENAME
            if not manifest.exists():
                continue
            try:
                ext = parse_manifest(manifest)
                if ext.name in seen_names:
                    logger.debug("Skipping duplicate extension: %s", ext.name)
                    continue
                seen_names.add(ext.name)
                extensions.append(ext)
            except Exception as e:
                logger.warning("Failed to parse extension %s: %s", child.name, e)

    return extensions


# ---------------------------------------------------------------------------
# Module loading (importlib, no sys.path)
# ---------------------------------------------------------------------------


def _load_module_from_file(name: str, file_path: Path) -> types.ModuleType:
    """Load a Python module from an arbitrary file path.

    Uses importlib.util.spec_from_file_location — no sys.path manipulation.
    Forces reload on each call to pick up changes immediately (hot-reload).
    """
    spec = importlib.util.spec_from_file_location(name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Chat tool loading
# ---------------------------------------------------------------------------


def load_chat_tools(ext: Extension) -> list[Any]:
    """Import chat tool modules from an extension.

    Returns list of ToolDef objects from each module's TOOLS list.
    """
    if not ext.chat_tools_module:
        return []

    tools_dir = ext.root / ext.chat_tools_module.replace(".", "/")
    if not tools_dir.is_dir():
        return []

    tool_defs = []
    for py_file in sorted(tools_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        mod_name = f"neut_ext.{ext.name}.{ext.chat_tools_module}.{py_file.stem}"
        try:
            mod = _load_module_from_file(mod_name, py_file)
            for tool_def in getattr(mod, "TOOLS", []):
                tool_defs.append(tool_def)
        except Exception as e:
            logger.warning(
                "Failed to load chat tool %s from %s: %s",
                py_file.name,
                ext.name,
                e,
            )

    return tool_defs


def discover_and_load_chat_tools(*search_dirs: Path) -> list[Any]:
    """Discover all extensions and load their chat tools."""
    tools = []
    for ext in discover_extensions(*search_dirs):
        if ext.enabled:
            tools.extend(load_chat_tools(ext))
    return tools


# ---------------------------------------------------------------------------
# Chat tool execution
# ---------------------------------------------------------------------------


def execute_extension_tool(
    name: str, params: dict[str, Any], *search_dirs: Path
) -> dict[str, Any] | None:
    """Execute an extension chat tool by name.

    Returns the result dict, or None if no extension provides this tool.
    """
    for ext in discover_extensions(*search_dirs):
        if not ext.enabled or not ext.chat_tools_module:
            continue
        tools_dir = ext.root / ext.chat_tools_module.replace(".", "/")
        if not tools_dir.is_dir():
            continue

        for py_file in sorted(tools_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            mod_name = f"neut_ext.{ext.name}.{ext.chat_tools_module}.{py_file.stem}"
            try:
                mod = _load_module_from_file(mod_name, py_file)
                tool_names = [t.name for t in getattr(mod, "TOOLS", [])]
                if name in tool_names:
                    handler = getattr(mod, "execute", None)
                    if handler:
                        return handler(name, params)
            except Exception as e:
                logger.warning("Error executing %s: %s", name, e)

    return None


# ---------------------------------------------------------------------------
# CLI command discovery
# ---------------------------------------------------------------------------


def discover_cli_commands(*search_dirs: Path) -> dict[str, dict[str, Any]]:
    """Discover CLI commands from all extensions.

    Returns dict mapping noun -> {module, description, extension, root, builtin}.
    """
    commands: dict[str, dict[str, Any]] = {}
    for ext in discover_extensions(*search_dirs):
        if not ext.enabled:
            continue
        for cmd in ext.cli_commands:
            if cmd.noun not in commands:
                commands[cmd.noun] = {
                    "module": cmd.module,
                    "description": cmd.description,
                    "extension": ext.name,
                    "root": str(ext.root),
                    "builtin": ext.builtin,
                }
    return commands


# ---------------------------------------------------------------------------
# Skill loading
# ---------------------------------------------------------------------------


def load_skills(ext: Extension) -> list[Skill]:
    """Load skills from an extension's skills directory."""
    return ext.skills  # Already scanned during parse_manifest


def discover_all_skills(*search_dirs: Path) -> list[Skill]:
    """Discover all skills from all extensions."""
    skills = []
    for ext in discover_extensions(*search_dirs):
        if ext.enabled:
            skills.extend(ext.skills)
    return skills


# ---------------------------------------------------------------------------
# Contract documentation generation
# ---------------------------------------------------------------------------


def generate_contract_docs() -> str:
    """Generate EXTENSION_CONTRACTS.md content.

    This is the file you paste into Claude/Gemini/Cursor context so they
    know exactly how to build NeutronOS extensions.
    """
    return _CONTRACT_DOCS_TEMPLATE


_CONTRACT_DOCS_TEMPLATE = '''# NeutronOS Extension Contracts

> Auto-generated by `neut ext docs`. Paste this into your AI assistant's
> context so it can generate extensions automatically.

## Quick Start

```bash
neut ext init my-extension    # Scaffold in ~/.neut/extensions/my-extension/
neut ext                      # List installed extensions
neut ext check my-extension   # Validate
```

## Manifest: `neut-extension.toml`

Every extension has a `neut-extension.toml` at its root:

```toml
[extension]
name = "my-extension"
version = "0.1.0"
description = "What this extension does"
author = "Your Name"

# Chat tools — Python modules with TOOLS list + execute() function
[chat_tools]
module = "tools_ext"

# Skills — SKILL.md standard (compatible with Claude Code, Codex, Copilot)
[skills]
dir = "skills"

# CLI commands — new nouns for the neut CLI
[[cli.commands]]
noun = "myverb"
module = "cli.myverb"
description = "Do something custom"

# Docflow providers
[[providers]]
type = "generation"
name = "pptx"
module = "providers.pptx_generation"

# Sense extractors
[[extractors]]
name = "reactor_log"
module = "extractors.reactor_log"
file_patterns = ["*.rlog", "*.csv"]

# MCP servers (same schema as .mcp.json)
[mcp_servers.my_server]
type = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
env = { API_KEY = "${MY_API_KEY}" }
```

---

## 1. Chat Tool Contract

Each `.py` file in the `tools_ext/` directory exports:
- `TOOLS`: list of `ToolDef` objects
- `execute(name: str, params: dict) -> dict`: handler function

```python
from neutron_os.extensions.builtins.chat_agent.tools import ToolDef
from neutron_os.platform.orchestrator.actions import ActionCategory

TOOLS = [
    ToolDef(
        name="my_tool",
        description="What this tool does (shown to the LLM).",
        category=ActionCategory.READ,  # READ = auto-approved, WRITE = needs confirmation
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
            },
            "required": ["query"],
        },
    ),
]

def execute(name: str, params: dict) -> dict:
    """Execute tool. Always return a dict."""
    if name == "my_tool":
        query = params.get("query", "")
        return {"results": [f"Result for: {query}"], "count": 1}
    return {"error": f"Unknown tool: {name}"}
```

**Parameter schema** follows OpenAI function-calling format (JSON Schema subset):
- `type`: "string", "number", "boolean", "integer", "array", "object"
- `description`: Shown to the LLM
- `enum`: Optional restricted values
- `required`: List of required parameter names

**ActionCategory:**
- `READ` — Auto-approved, no user confirmation needed
- `WRITE` — Requires human confirmation before execution

---

## 2. Skill Contract (SKILL.md)

Skills use the Agent Skills standard (compatible with Claude Code, Codex, Copilot).
Each skill lives in its own directory under `skills/`:

```
skills/
    weekly-slides/
        SKILL.md
    data-export/
        SKILL.md
```

SKILL.md format:

```markdown
---
name: weekly-slides
description: Generate weekly progress slides from sense data
---

# Weekly Slides

## Instructions

1. Query sense status for the current week's signals
2. Group signals by initiative
3. Generate a slide deck with one slide per initiative
4. Include blockers slide at the end

## Parameters

- **format**: Output format (pptx, pdf). Default: pptx
- **week**: ISO date for the week. Default: current week
```

---

## 3. CLI Command Contract

CLI command modules export a `main()` function and optionally `get_parser()`:

```python
import argparse

def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut myverb",
        description="Do something custom",
    )
    parser.add_argument("target", help="What to operate on")
    parser.add_argument("--format", choices=["json", "table"], default="table")
    return parser

def main():
    parser = get_parser()
    args = parser.parse_args()
    print(f"Operating on {args.target} with format {args.format}")
```

---

## 4. Docflow Provider Contracts

Providers implement abstract base classes from `tools.extensions.builtins.docflow.providers.base`:

### GenerationProvider

```python
from pathlib import Path
from neutron_os.extensions.builtins.docflow.providers.base import (
    GenerationProvider,
    GenerationOptions,
    GenerationResult,
)

class PptxGenerationProvider(GenerationProvider):
    def __init__(self, config: dict):
        self.config = config

    def generate(self, source_path: Path, output_path: Path,
                 options: GenerationOptions) -> GenerationResult:
        # Convert markdown to .pptx
        # Return GenerationResult with output_path, format, size_bytes
        ...

    def rewrite_links(self, artifact_path: Path, link_map: dict[str, str]) -> None:
        pass  # Optional for pptx

    def get_output_extension(self) -> str:
        return ".pptx"

    def supports_watermark(self) -> bool:
        return False
```

### StorageProvider, NotificationProvider

See `tools/docflow/providers/base.py` for all five provider ABCs.

---

## 5. Extractor Contract

Extractors inherit from `tools.extensions.builtins.sense_agent.extractors.base.BaseExtractor`:

```python
from pathlib import Path
from neutron_os.extensions.builtins.sense_agent.extractors.base import BaseExtractor
from neutron_os.extensions.builtins.sense_agent.models import Extraction, Signal

class ReactorLogExtractor(BaseExtractor):
    @property
    def name(self) -> str:
        return "reactor_log"

    def can_handle(self, path: Path) -> bool:
        return path.exists() and path.suffix in (".rlog", ".csv")

    def extract(self, source: Path, **kwargs) -> Extraction:
        # Parse reactor log file, create Signal objects
        signals = []
        # ... extraction logic ...
        return Extraction(
            extractor=self.name,
            source_file=str(source),
            signals=signals,
        )
```

---

## 6. MCP Server Contract

Same JSON schema as `.mcp.json` (Claude Code, Cursor):

```toml
[mcp_servers.my_server]
type = "stdio"
command = "python"
args = ["-m", "my_mcp_module"]
env = { API_KEY = "${MY_API_KEY}" }
```

Supports `${VAR}` and `${VAR:-default}` expansion for credentials.

---

## 7. Persistence Guidelines

**Default: file-based** (JSON/TOML in extension directory)
- Human-readable, easy backup, git-friendly
- Good for: config, session state, audit trails

**PostgreSQL** (when needed):
- Growing data, vector search, relational queries, shared state
- Declare in manifest: `[database]` section with migrations dir

---

## Directory Structure

```
~/.neut/extensions/my-extension/
    neut-extension.toml     # Manifest (required)
    tools_ext/              # Chat tools (Python modules)
        my_tool.py
    skills/                 # Agent skills (SKILL.md standard)
        weekly-slides/
            SKILL.md
    cli/                    # CLI commands
        myverb.py
    providers/              # Docflow providers
        pptx_generation.py
    extractors/             # Sense extractors
        reactor_log.py
```

Extensions are hot-reloaded — no pip install, no restart needed.
'''
