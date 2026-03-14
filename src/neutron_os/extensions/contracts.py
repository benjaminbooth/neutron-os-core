"""Extension manifest model and data structures.

Pure data — no I/O, no imports of external modules. Defines the shape of
extension manifests (neut-extension.toml) and the types that discovery and
scaffold modules operate on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CLICommandDef:
    """A CLI noun registered by an extension."""

    noun: str
    module: str  # Dotted module path relative to extension root
    description: str = ""


@dataclass
class ProviderDef:
    """A docflow provider registered by an extension."""

    type: str  # "generation", "storage", "notification", etc.
    name: str
    module: str


@dataclass
class ExtractorDef:
    """A sense extractor registered by an extension."""

    name: str
    module: str
    file_patterns: list[str] = field(default_factory=list)


@dataclass
class MCPServerDef:
    """An MCP server bundled with an extension."""

    name: str
    type: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Skill:
    """An agent skill defined by SKILL.md (Agent Skills standard)."""

    name: str  # Directory name
    path: Path  # Path to SKILL.md
    description: str = ""  # Parsed from frontmatter or first heading


@dataclass
class Extension:
    """A discovered extension with its parsed manifest."""

    name: str
    version: str
    description: str
    author: str
    root: Path  # Absolute path to extension directory

    # Capability declarations from manifest
    chat_tools_module: str = ""  # e.g. "tools_ext"
    skills_dir: str = "skills"
    cli_commands: list[CLICommandDef] = field(default_factory=list)
    providers: list[ProviderDef] = field(default_factory=list)
    extractors: list[ExtractorDef] = field(default_factory=list)
    mcp_servers: dict[str, MCPServerDef] = field(default_factory=dict)

    # Classification
    kind: str = "tool"  # "agent", "tool", or "utility"
    module_group: str = ""  # PRD-level grouping (e.g. "platform", "operations")

    # Runtime state
    enabled: bool = True
    builtin: bool = False  # True for extensions shipped inside extensions/builtins/
    skills: list[Skill] = field(default_factory=list)

    @property
    def manifest_path(self) -> Path:
        return self.root / "neut-extension.toml"

    @property
    def capabilities(self) -> list[str]:
        """Human-readable list of what this extension provides."""
        caps = []
        if self.chat_tools_module:
            caps.append("chat tools")
        if self.skills:
            caps.append(f"{len(self.skills)} skill(s)")
        if self.cli_commands:
            caps.append(f"{len(self.cli_commands)} CLI command(s)")
        if self.providers:
            caps.append(f"{len(self.providers)} provider(s)")
        if self.extractors:
            caps.append(f"{len(self.extractors)} extractor(s)")
        if self.mcp_servers:
            caps.append(f"{len(self.mcp_servers)} MCP server(s)")
        return caps


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "neut-extension.toml"


def parse_manifest(manifest_path: Path) -> Extension:
    """Parse a neut-extension.toml file into an Extension object.

    Raises ValueError if required fields are missing.
    Raises FileNotFoundError if the manifest doesn't exist.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    text = manifest_path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    root = manifest_path.parent

    ext_section = data.get("extension", {})
    name = ext_section.get("name", "")
    if not name:
        raise ValueError(f"Missing [extension].name in {manifest_path}")

    ext = Extension(
        name=name,
        version=ext_section.get("version", "0.1.0"),
        description=ext_section.get("description", ""),
        author=ext_section.get("author", ""),
        root=root,
        builtin=ext_section.get("builtin", False),
        kind=ext_section.get("kind", "tool"),
        module_group=ext_section.get("module", ""),
    )

    # Chat tools
    chat_section = data.get("chat_tools", {})
    ext.chat_tools_module = chat_section.get("module", "")

    # Skills
    skills_section = data.get("skills", {})
    ext.skills_dir = skills_section.get("dir", "skills")

    # CLI commands
    for cmd in data.get("cli", {}).get("commands", []):
        ext.cli_commands.append(
            CLICommandDef(
                noun=cmd.get("noun", ""),
                module=cmd.get("module", ""),
                description=cmd.get("description", ""),
            )
        )

    # Providers
    for prov in data.get("providers", []):
        ext.providers.append(
            ProviderDef(
                type=prov.get("type", ""),
                name=prov.get("name", ""),
                module=prov.get("module", ""),
            )
        )

    # Extractors
    for extr in data.get("extractors", []):
        ext.extractors.append(
            ExtractorDef(
                name=extr.get("name", ""),
                module=extr.get("module", ""),
                file_patterns=extr.get("file_patterns", []),
            )
        )

    # MCP servers
    for key, val in data.get("mcp_servers", {}).items():
        if isinstance(val, dict):
            ext.mcp_servers[key] = MCPServerDef(
                name=key,
                type=val.get("type", "stdio"),
                command=val.get("command", ""),
                args=val.get("args", []),
                env=val.get("env", {}),
            )

    # Scan for skills (SKILL.md files)
    skills_path = root / ext.skills_dir
    if skills_path.is_dir():
        ext.skills = _scan_skills(skills_path)

    return ext


def _scan_skills(skills_dir: Path) -> list[Skill]:
    """Scan a directory for SKILL.md files (Agent Skills standard)."""
    skills = []
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        skill_name = skill_md.parent.name
        description = _parse_skill_description(skill_md)
        skills.append(Skill(name=skill_name, path=skill_md, description=description))
    return skills


def _parse_skill_description(skill_md: Path) -> str:
    """Extract description from SKILL.md frontmatter or first paragraph."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return ""

    # Try YAML frontmatter (--- delimited)
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            frontmatter = text[3:end]
            for line in frontmatter.split("\n"):
                line = line.strip()
                if line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
                    return desc.strip("\"'")

    # Fall back to first non-heading, non-empty line
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        return line

    return ""


def validate_extension(ext: Extension) -> list[str]:
    """Validate an extension's manifest and file structure.

    Returns a list of issues (empty = valid).
    Builtins verify importability; user extensions verify filesystem paths.
    """
    issues: list[str] = []

    if not ext.name:
        issues.append("Extension name is required")

    if not ext.root.is_dir():
        issues.append(f"Extension root not found: {ext.root}")
        return issues  # Can't check further

    if not ext.manifest_path.exists():
        issues.append(f"Manifest not found: {ext.manifest_path}")

    if ext.builtin:
        # Builtins: verify CLI modules are importable
        import importlib.util

        for cmd in ext.cli_commands:
            try:
                spec = importlib.util.find_spec(cmd.module)
            except (ModuleNotFoundError, ValueError):
                spec = None
            if spec is None:
                issues.append(f"Builtin CLI module not importable: {cmd.module}")
    else:
        # User extensions: verify filesystem paths

        # Check chat tools module exists
        if ext.chat_tools_module:
            tools_dir = ext.root / ext.chat_tools_module.replace(".", "/")
            if not tools_dir.is_dir():
                issues.append(f"Chat tools module dir not found: {tools_dir}")

        # Check CLI command modules exist
        for cmd in ext.cli_commands:
            mod_path = ext.root / cmd.module.replace(".", "/")
            if not mod_path.with_suffix(".py").exists() and not (mod_path / "__init__.py").exists():
                issues.append(f"CLI module not found: {cmd.module}")

        # Check provider modules exist
        for prov in ext.providers:
            mod_path = ext.root / prov.module.replace(".", "/")
            if not mod_path.with_suffix(".py").exists():
                issues.append(f"Provider module not found: {prov.module}")

        # Check extractor modules exist
        for extr in ext.extractors:
            mod_path = ext.root / extr.module.replace(".", "/")
            if not mod_path.with_suffix(".py").exists():
                issues.append(f"Extractor module not found: {extr.module}")

    # Check skills have SKILL.md
    skills_path = ext.root / ext.skills_dir
    if skills_path.is_dir():
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not (skill_dir / "SKILL.md").exists():
                issues.append(f"Skill dir missing SKILL.md: {skill_dir.name}")

    return issues
