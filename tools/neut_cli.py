#!/usr/bin/env python3
"""
neut — Neutron OS CLI dispatcher (Python prototype)

Routes subcommands to their respective handlers:
  neut sense ...     → tools/agents/sense/cli.py
  neut doc ...       → tools/docflow/cli.py
  neut docflow ...   → tools/docflow/cli.py  (alias)
  neut db ...        → tools/db/cli.py
  neut infra ...     → tools/agents/setup/infra.py (Docker, K3D setup)
  neut test ...      → tools/test/cli.py
  neut update ...    → tools/update/cli.py
  neut status ...    → tools/status/cli.py

The production neut CLI will be Rust (see docs/specs/neut-cli-spec.md).
This Python entry point serves developer tooling during early development.

Usage:
    python tools/neut_cli.py <subcommand> [args...]
    python -m tools.neut_cli <subcommand> [args...]

Installation:
    alias neut="python /path/to/tools/neut_cli.py"
"""

import argparse
import sys
import os

# Ensure repo root is on sys.path so imports resolve
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_dotenv():
    """Load .env file from repo root if it exists (no external deps)."""
    env_path = os.path.join(REPO_ROOT, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Don't overwrite explicitly set env vars
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_load_dotenv()


SUBCOMMANDS = {
    "setup": "tools.agents.setup.cli",
    "sense": "tools.agents.sense.cli",
    "doc": "tools.docflow.cli",
    "docflow": "tools.docflow.cli",
    "chat": "tools.agents.chat.cli",
    "db": "tools.db.cli",  # Database infrastructure (K3D, migrations)
    "infra": "tools.agents.setup.infra",  # Infrastructure setup (Docker, K3D)
    "test": "tools.test.cli",  # Test orchestration
    "update": "tools.update.cli",  # Dependency and migration updates
    "status": "tools.status.cli",  # System health dashboard
    "serve-mcp": "tools.mcp_server.server",
    "doctor": None,  # Built-in, handled specially
}


def cmd_doctor(error_context: str | None = None):
    """Diagnose environment issues using RAG+LLM for intelligent fixes."""

    print("🩺 neut doctor — AI-Powered Diagnostics")
    print("=" * 50)

    diagnostics = _gather_diagnostics()

    # Print quick summary
    print("\n📋 Environment Summary:")
    for check in diagnostics["checks"]:
        status = "✓" if check["ok"] else "✗"
        print(f"   {status} {check['name']}: {check['status']}")

    issues = [c for c in diagnostics["checks"] if not c["ok"]]

    # If there are issues OR user provided error context, use LLM
    if issues or error_context:
        print("\n🤖 Analyzing with AI...")
        analysis = _llm_diagnose(diagnostics, error_context)
        if analysis:
            print("\n" + "=" * 50)
            print("💡 AI Analysis:")
            print(analysis)
        else:
            # Fallback to basic suggestions
            print("\n" + "=" * 50)
            if issues:
                print(f"❌ Found {len(issues)} issue(s):")
                for issue in issues:
                    print(f"   • {issue['name']}: {issue['status']}")
                    if issue.get("fix"):
                        print(f"     Fix: {issue['fix']}")
            print("\nQuick fix: cd Neutron_OS && ./scripts/bootstrap.sh")
    else:
        print("\n" + "=" * 50)
        print("✅ Environment looks healthy!")

    return 1 if issues else 0


def _gather_diagnostics() -> dict:
    """Gather all environment diagnostics into a structured dict."""
    import shutil
    import subprocess
    from pathlib import Path

    checks = []

    # 1. Python version
    py_ok = sys.version_info >= (3, 10)
    checks.append({
        "name": "Python",
        "ok": py_ok,
        "status": sys.version.split()[0],
        "fix": "Install Python 3.10+" if not py_ok else None,
    })

    # 2. Virtual environment
    venv_path = os.environ.get("VIRTUAL_ENV", "")
    checks.append({
        "name": "Virtual Environment",
        "ok": bool(venv_path),
        "status": venv_path or "Not active",
        "fix": "source .venv/bin/activate" if not venv_path else None,
    })

    # 3. Package installation
    pkg_ok = False
    pkg_status = "Unknown"
    pkg_location = ""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "neutron-os"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            pkg_ok = True
            for line in result.stdout.split("\n"):
                if line.startswith("Editable project location:"):
                    pkg_location = line.split(":", 1)[1].strip()
                    pkg_status = f"Editable at {pkg_location}"
                    break
            else:
                pkg_status = "Installed"
        else:
            pkg_status = "Not installed"
    except Exception as e:
        pkg_status = f"Check failed: {e}"

    checks.append({
        "name": "Package",
        "ok": pkg_ok,
        "status": pkg_status,
        "location": pkg_location,
        "fix": "pip install -e ." if not pkg_ok else None,
    })

    # 4. Entry point (accept either pip entry point OR shell wrapper)
    neut_script = shutil.which("neut")
    entry_ok = False
    entry_status = "Not found"
    entry_content = ""
    entry_type = None
    if neut_script:
        try:
            with open(neut_script) as f:
                entry_content = f.read()
            # Check for pip-generated Python entry point
            if "from tools.neut_cli import main" in entry_content:
                entry_ok = True
                entry_type = "pip"
                entry_status = f"Valid (pip) at {neut_script}"
            # Check for our self-healing shell wrapper
            elif "python -m tools.neut_cli" in entry_content or "-m tools.neut_cli" in entry_content:
                entry_ok = True
                entry_type = "shell"
                entry_status = f"Valid (shell wrapper) at {neut_script}"
            else:
                entry_status = f"Stale at {neut_script}"
        except Exception as e:
            entry_status = f"Cannot read: {e}"

    checks.append({
        "name": "Entry Point",
        "ok": entry_ok,
        "status": entry_status,
        "type": entry_type,
        "content": entry_content[:500] if entry_content else "",
        "fix": "./scripts/bootstrap.sh" if not entry_ok else None,
    })

    # 5. Gateway/LLM availability
    gateway_ok = False
    gateway_status = "Not configured"
    try:
        from tools.agents.sense.gateway import Gateway
        gw = Gateway()
        if gw.available:
            gateway_ok = True
            provider = gw.active_provider
            gateway_status = f"{provider.name} ({provider.model})" if provider else "Available"
        else:
            gateway_status = "No providers configured"
    except ImportError:
        gateway_status = "Gateway module not found"
    except Exception as e:
        gateway_status = f"Error: {e}"

    checks.append({
        "name": "LLM Gateway",
        "ok": gateway_ok,
        "status": gateway_status,
        "fix": "Set ANTHROPIC_API_KEY or OPENAI_API_KEY" if not gateway_ok else None,
    })

    # 6. Working directory
    cwd = os.getcwd()
    in_neutron = "Neutron_OS" in cwd or Path(cwd, "tools/neut_cli.py").exists()
    checks.append({
        "name": "Working Directory",
        "ok": True,  # Not critical
        "status": cwd,
        "in_neutron_os": in_neutron,
    })

    return {
        "checks": checks,
        "python_version": sys.version,
        "platform": sys.platform,
        "cwd": cwd,
    }


def _llm_diagnose(diagnostics: dict, error_context: str | None = None) -> str | None:
    """Use LLM with project context to diagnose issues intelligently."""
    try:
        from tools.agents.sense.gateway import Gateway
        from pathlib import Path

        gateway = Gateway()
        if not gateway.available:
            return None

        # Load CLAUDE.md for project context
        claude_md = Path(REPO_ROOT) / "CLAUDE.md"
        project_context = ""
        if claude_md.exists():
            try:
                content = claude_md.read_text()
                # Extract troubleshooting section
                if "## Troubleshooting" in content:
                    start = content.index("## Troubleshooting")
                    end = content.find("\n## ", start + 1)
                    project_context = content[start:end] if end > 0 else content[start:]
                else:
                    # Take first 2000 chars as context
                    project_context = content[:2000]
            except Exception:
                pass

        # Build diagnostic summary
        issues = [c for c in diagnostics["checks"] if not c["ok"]]
        diag_text = "Environment Diagnostics:\n"
        for check in diagnostics["checks"]:
            status = "OK" if check["ok"] else "ISSUE"
            diag_text += f"- {check['name']}: {status} - {check['status']}\n"
            if check.get("content"):
                diag_text += f"  Entry point content: {check['content'][:200]}...\n"

        if error_context:
            diag_text += f"\nUser-reported error:\n{error_context}\n"

        prompt = f"""You are a diagnostic assistant for Neutron OS, a Python-based nuclear engineering platform.

PROJECT CONTEXT (from CLAUDE.md):
{project_context}

{diag_text}

Provide a diagnosis in PLAIN TEXT only (no markdown, no **, no ```, no code fences):

DIAGNOSIS: [one line explaining the problem]

FIX: [numbered steps with exact commands]

WHY: [brief explanation of root cause]

Rules:
- Be concise (under 200 words)
- Use exact paths from diagnostics
- Commands should be copy-pasteable
- Plain text only — no markdown formatting"""

        response = gateway.complete(prompt)
        return response.text if hasattr(response, 'text') else str(response)

    except Exception:
        # Silently fall back to basic mode
        return None


# Help text for subcommands without get_parser()
_SUBCOMMAND_HELP = {
    "setup": "Interactive onboarding wizard",
    "sense": "Agentic signal ingestion pipeline",
    "doc": "Document lifecycle management",
    "docflow": "Document lifecycle management (alias for doc)",
    "chat": "Interactive agent with tool calling",
    "db": "Database infrastructure (K3D, migrations)",
    "infra": "Infrastructure setup (Docker, K3D)",
    "test": "Test orchestration",
    "update": "Dependency and migration updates",
    "status": "System health dashboard",
    "serve-mcp": "Start the MCP server for IDE integration",
    "doctor": "AI-powered environment diagnostics",
}


def _copy_subparsers(
    src_parser: argparse.ArgumentParser,
    dst_parser: argparse.ArgumentParser,
) -> None:
    """Copy subparser definitions from *src_parser* into *dst_parser*.

    This lets argcomplete see the full completion tree (e.g. ``neut sense
    ingest``) without duplicating parser definitions.
    """
    for action in src_parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            dst_sub = dst_parser.add_subparsers(dest=action.dest)
            for name, sub in action.choices.items():
                # Determine help text from _choices_actions if available
                help_text = sub.description or ""
                for choice_action in action._choices_actions:
                    if choice_action.dest == name:
                        help_text = choice_action.help or help_text
                        break
                new_sub = dst_sub.add_parser(name, help=help_text, description=sub.description)
                # Copy arguments (flags) from the child parser
                for sub_action in sub._actions:
                    if isinstance(sub_action, (argparse._HelpAction, argparse._SubParsersAction)):
                        continue
                    # Reconstruct the add_argument call from the action
                    kwargs = {}
                    if sub_action.option_strings:
                        names = sub_action.option_strings
                    else:
                        names = [sub_action.dest]
                    if sub_action.help:
                        kwargs["help"] = sub_action.help
                    if sub_action.choices:
                        kwargs["choices"] = sub_action.choices
                    if sub_action.metavar:
                        kwargs["metavar"] = sub_action.metavar
                    if isinstance(sub_action, argparse._StoreTrueAction):
                        kwargs["action"] = "store_true"
                    elif isinstance(sub_action, argparse._StoreFalseAction):
                        kwargs["action"] = "store_false"
                    elif isinstance(sub_action, argparse._CountAction):
                        kwargs["action"] = "count"
                    elif sub_action.nargs is not None:
                        kwargs["nargs"] = sub_action.nargs
                    try:
                        new_sub.add_argument(*names, **kwargs)
                    except Exception:
                        pass  # Skip arguments that can't be copied cleanly
            break  # Only one _SubParsersAction expected


def _copy_top_level_args(
    src_parser: argparse.ArgumentParser,
    dst_parser: argparse.ArgumentParser,
) -> None:
    """Copy top-level arguments (flags like --resume, --model) from *src* to *dst*."""
    for action in src_parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        kwargs = {}
        if action.option_strings:
            names = action.option_strings
        else:
            names = [action.dest]
        if action.help:
            kwargs["help"] = action.help
        if action.choices:
            kwargs["choices"] = action.choices
        if action.metavar:
            kwargs["metavar"] = action.metavar
        if action.option_strings:
            # Only set dest explicitly if it differs from the auto-derived name
            auto_dest = action.option_strings[0].lstrip("-").replace("-", "_")
            if action.dest and action.dest != auto_dest:
                kwargs["dest"] = action.dest
        if isinstance(action, argparse._StoreTrueAction):
            kwargs["action"] = "store_true"
        elif isinstance(action, argparse._StoreFalseAction):
            kwargs["action"] = "store_false"
        elif isinstance(action, argparse._CountAction):
            kwargs["action"] = "count"
        elif action.nargs is not None:
            kwargs["nargs"] = action.nargs
        try:
            dst_parser.add_argument(*names, **kwargs)
        except Exception:
            pass


def get_parser() -> argparse.ArgumentParser:
    """Build top-level parser for argcomplete and help generation.

    This mirrors the SUBCOMMANDS dict with real argparse subparsers so that
    argcomplete can provide tab completion.  The actual command dispatch still
    uses the existing SUBCOMMANDS + importlib approach — argparse is used only
    for completion and ``--help``.
    """
    import importlib

    parser = argparse.ArgumentParser(
        prog="neut",
        description="Neutron OS CLI (Python prototype)",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    seen = set()
    for name, module_path in SUBCOMMANDS.items():
        if name in seen:
            continue
        seen.add(name)

        if module_path is None:
            # Built-in (e.g. doctor)
            subparsers.add_parser(name, help=_SUBCOMMAND_HELP.get(name, ""))
            continue

        try:
            mod = importlib.import_module(module_path)
            if hasattr(mod, "get_parser"):
                child_parser = mod.get_parser()
                sub = subparsers.add_parser(
                    name,
                    help=child_parser.description or _SUBCOMMAND_HELP.get(name, ""),
                    description=child_parser.description,
                )
                # Attach child subparsers (e.g. sense status, sense ingest)
                _copy_subparsers(child_parser, sub)
                # Attach top-level flags (e.g. chat --resume, chat --model)
                _copy_top_level_args(child_parser, sub)
            else:
                subparsers.add_parser(name, help=_SUBCOMMAND_HELP.get(name, ""))
        except ImportError:
            subparsers.add_parser(name, help=_SUBCOMMAND_HELP.get(name, ""))

    return parser


def print_usage():
    print("neut — Neutron OS CLI (Python prototype)")
    print()
    print("Usage: neut <subcommand> [args...]")
    print()
    print("Subcommands:")
    print("  setup     Interactive onboarding wizard")
    print("  sense     Agentic signal ingestion pipeline")
    print("  doc       Document lifecycle management (alias: docflow)")
    print("  chat      Interactive agent with tool calling")
    print("  serve-mcp Start the MCP server for IDE integration")
    print("  doctor    AI-powered environment diagnostics")
    print()
    print("Examples:")
    print("  neut sense status")
    print("  neut sense ingest --source gitlab")
    print("  neut doc publish docs/prd/foo.md")
    print("  neut doc providers")
    print("  neut doctor                     # Check environment health")
    print("  neut doctor 'ModuleNotFoundError: No module named neut'")


def _suggest_command(cmd: str, valid_commands: list[str]) -> str | None:
    """Suggest a similar command using fuzzy matching."""
    from difflib import get_close_matches
    matches = get_close_matches(cmd, valid_commands, n=1, cutoff=0.6)
    return matches[0] if matches else None


def main():
    # Build the argparse tree so argcomplete can offer tab completions.
    # autocomplete() exits early when the shell is requesting completions;
    # otherwise it's a no-op and we fall through to the manual dispatch below.
    parser = get_parser()
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass  # argcomplete not installed — no completion, no crash

    if len(sys.argv) < 2:
        if sys.stdin.isatty() and sys.stdout.isatty():
            sys.argv = ["neut chat", "--bare"]
            try:
                from tools.agents.chat.cli import main as chat_main
                chat_main()
            except KeyboardInterrupt:
                print()
            sys.exit(0)
        else:
            print_usage()
            sys.exit(1)

    subcommand = sys.argv[1]

    if subcommand in ("-h", "--help", "help"):
        print_usage()
        sys.exit(0)

    if subcommand == "doctor":
        # Accept optional error context: neut doctor "error message" or neut doctor --error "msg"
        error_context = None
        args = sys.argv[2:]
        if args:
            if args[0] in ("--error", "-e") and len(args) > 1:
                error_context = args[1]
            elif not args[0].startswith("-"):
                error_context = " ".join(args)
        sys.exit(cmd_doctor(error_context))

    module_path = SUBCOMMANDS.get(subcommand)
    if not module_path:
        suggestion = _suggest_command(subcommand, list(SUBCOMMANDS.keys()))
        print(f"neut: unknown subcommand '{subcommand}'")
        if suggestion:
            print(f"\nDid you mean: neut {suggestion}?")
        print("\nRun 'neut --help' for usage.")
        sys.exit(1)

    # Remove the subcommand from argv so the handler sees only its own args
    sys.argv = [f"neut {subcommand}"] + sys.argv[2:]

    try:
        import importlib
        module = importlib.import_module(module_path)
        module.main()
    except ImportError as e:
        print(f"neut: failed to load {subcommand} handler: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(130)


if __name__ == "__main__":
    main()
