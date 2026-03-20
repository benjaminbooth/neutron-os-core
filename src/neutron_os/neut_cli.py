#!/usr/bin/env python3
"""
neut — Neutron OS CLI dispatcher (Python prototype)

Routes subcommands to their respective handlers via the extension system.
Core commands (config, ext, infra, doctor) are handled directly.
All other nouns are dispatched to builtin or user extensions.

The production neut CLI will be Rust (see docs/tech-specs/spec-neut-cli.md).
This Python entry point serves developer tooling during early development.

Usage:
    neut <subcommand> [args...]
    python -m neutron_os.neut_cli <subcommand> [args...]

Installation:
    alias neut="python /path/to/tools/neut_cli.py"
"""

import argparse
import sys
import os
from pathlib import Path

# Ensure repo root is on sys.path when running from source checkout.
# Skip when installed as a wheel (inside site-packages).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_in_site_packages = "site-packages" in os.path.abspath(__file__)
if not _in_site_packages and REPO_ROOT not in sys.path:
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


def _check_and_prompt_update() -> None:
    """Check for a newer version and prompt the user to update.

    Only runs in interactive TTY sessions. Uses a 1-hour cache so it
    doesn't hit the network on every invocation. Never crashes the CLI.
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return
    try:
        from neutron_os.extensions.builtins.update.version_check import VersionChecker
        checker = VersionChecker()
        info = checker.check_remote_version(timeout=3.0)
        if not info.is_newer:
            return

        current = info.current
        available = info.available or "latest"
        print(f"\n  A new version of neut is available ({current} → {available}).")
        try:
            answer = input("  Update now? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if answer != "y":
            return

        print()
        _do_self_update(checker.get_current_version())
    except Exception:
        pass  # Never block the CLI for an update check


def _do_self_update(old_version: str) -> None:
    """Perform the actual self-update and stash a changelog for next launch."""
    import subprocess

    GITHUB_REPO = "https://github.com/benjaminbooth/neutron-os-core.git"
    VENV_PIP = Path.home() / ".neut" / "venv" / "bin" / "pip"

    # Prefer the venv pip (end-user install); fall back to current interpreter's pip
    pip_cmd = str(VENV_PIP) if VENV_PIP.exists() else f"{sys.executable} -m pip"

    print("  Updating neut...")
    result = subprocess.run(
        [*pip_cmd.split(), "install", "--upgrade", f"git+{GITHUB_REPO}"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  Update failed:\n{result.stderr.strip()}")
        return

    # Stash changelog so it shows on next launch
    try:
        from neutron_os.extensions.builtins.update.cli import Updater
        from importlib.metadata import version as pkg_version
        new_version = pkg_version("neutron-os")
        updater = Updater()
        updater._stash_changelog(old_version, new_version, [])
    except Exception:
        pass

    print("  Done. Restart neut to use the new version.\n")


def _show_pending_changelog() -> None:
    """Display pending changelog from a recent update, then clear it."""
    try:
        from neutron_os.extensions.builtins.update.version_check import read_pending_changelog, clear_pending_changelog
        changelog = read_pending_changelog()
        if not changelog or changelog.get("shown"):
            return

        old_v = changelog.get("old_version", "?")
        new_v = changelog.get("new_version", "?")
        categories = changelog.get("categories", {})
        count = changelog.get("commit_count", 0)

        print(f"\n  Updated {old_v} \u2192 {new_v} ({count} commits)")
        print("  " + "\u2500" * 38)

        _LABELS = {
            "features": "New",
            "fixes": "Fixed",
            "improvements": "Improved",
            "other": "Other",
        }
        for key, label in _LABELS.items():
            items = categories.get(key, [])
            if items:
                print(f"  {label}:")
                for item in items[:5]:
                    print(f"    - {item}")
                if len(items) > 5:
                    print(f"    ... and {len(items) - 5} more")

        print()
        clear_pending_changelog()
    except Exception:
        pass  # Never crash the CLI for changelog display


# Core commands — platform infrastructure that is NOT an extension.
# Everything else is discovered via the extension system (builtins + user).
SUBCOMMANDS = {
    "config": "neutron_os.setup.cli",
    "ext": "neutron_os.extensions.cli",
    "infra": "neutron_os.setup.infra",
    "doctor": None,  # Built-in, handled specially
}


def _merge_extension_commands() -> dict[str, dict]:
    """Discover CLI commands from all extensions (builtin + user).

    Returns dict mapping noun -> {module, description, extension, root, builtin}.
    Core SUBCOMMANDS take precedence over extension commands.
    """
    try:
        from neutron_os.extensions.discovery import discover_cli_commands

        ext_cmds = discover_cli_commands()
        return {
            noun: info
            for noun, info in ext_cmds.items()
            if noun not in SUBCOMMANDS  # Core commands take precedence
        }
    except Exception:
        return {}


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
            if "from neutron_os.neut_cli import main" in entry_content:
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
        from neutron_os.infra.gateway import Gateway
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
    in_neutron = "Neutron_OS" in cwd or Path(cwd, "src/neutron_os/neut_cli.py").exists()
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
        from neutron_os.infra.gateway import Gateway
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


# Help text for core subcommands (extensions provide their own descriptions)
_SUBCOMMAND_HELP = {
    "config": "Interactive onboarding wizard",
    "ext": "Manage extensions (builtin + user)",
    "doctor": "AI-powered environment diagnostics",
}


def _copy_subparsers(
    src_parser: argparse.ArgumentParser,
    dst_parser: argparse.ArgumentParser,
) -> None:
    """Copy subparser definitions from *src_parser* into *dst_parser*.

    This lets argcomplete see the full completion tree (e.g. ``neut signal
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
            new_action = dst_parser.add_argument(*names, **kwargs)
            # Carry over argcomplete completers
            if hasattr(action, "completer") and action.completer is not None:
                new_action.completer = action.completer
        except Exception:
            pass


def get_parser() -> argparse.ArgumentParser:
    """Build top-level parser for argcomplete and help generation.

    This mirrors SUBCOMMANDS + discovered extension commands with real argparse
    subparsers so that argcomplete can provide tab completion.  The actual
    command dispatch still uses importlib — argparse is used only for
    completion and ``--help``.
    """
    import importlib

    parser = argparse.ArgumentParser(
        prog="neut",
        description="Neutron OS CLI (Python prototype)",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    seen = set()

    # Core commands
    for name, module_path in SUBCOMMANDS.items():
        if name in seen:
            continue
        seen.add(name)

        if module_path is None:
            subparsers.add_parser(name, help=_SUBCOMMAND_HELP.get(name, ""))
            continue

        try:
            mod = importlib.import_module(module_path)
            _get = getattr(mod, "get_parser", None) or getattr(mod, "build_parser", None)
            if _get:
                child_parser = _get()
                sub = subparsers.add_parser(
                    name,
                    help=child_parser.description or _SUBCOMMAND_HELP.get(name, ""),
                    description=child_parser.description,
                )
                _copy_subparsers(child_parser, sub)
                _copy_top_level_args(child_parser, sub)
            else:
                subparsers.add_parser(name, help=_SUBCOMMAND_HELP.get(name, ""))
        except ImportError:
            subparsers.add_parser(name, help=_SUBCOMMAND_HELP.get(name, ""))

    # Extension commands (builtin + user)
    ext_cmds = _merge_extension_commands()
    for name, info in ext_cmds.items():
        if name in seen:
            continue
        seen.add(name)

        module_path = info["module"]
        description = info.get("description", "")

        if info.get("builtin"):
            # Builtin: importable module, try to get parser for tab completion
            try:
                mod = importlib.import_module(module_path)
                _get = getattr(mod, "get_parser", None) or getattr(mod, "build_parser", None)
                if _get:
                    child_parser = _get()
                    sub = subparsers.add_parser(
                        name,
                        help=child_parser.description or description,
                        description=child_parser.description,
                    )
                    _copy_subparsers(child_parser, sub)
                    _copy_top_level_args(child_parser, sub)
                else:
                    subparsers.add_parser(name, help=description)
            except ImportError:
                subparsers.add_parser(name, help=description)
        else:
            # User extension: just add stub parser with description
            subparsers.add_parser(name, help=description)

    return parser


def print_usage(show_all: bool = False):
    print("neut — Neutron OS CLI")
    print()
    print("Usage: neut <command> [args...]")
    print()

    ext_cmds = _merge_extension_commands()

    # Categorise builtin vs user extensions
    builtins = {n: i for n, i in ext_cmds.items() if i.get("builtin")}
    user_exts = {n: i for n, i in ext_cmds.items() if not i.get("builtin")}

    # Always-visible commands
    print("Commands:")
    # Core
    print("  config    Interactive onboarding wizard")
    print("  doctor    Diagnose environment issues")
    print("  ext       Manage extensions (builtin + user)")
    # Show a few key builtins even in short mode
    for noun in ("status", "update", "chat"):
        if noun in builtins:
            print(f"  {noun:<10}{builtins[noun]['description']}")

    if show_all:
        print()
        print("Builtins:")
        for noun, info in sorted(builtins.items()):
            if noun in ("status", "update", "chat"):
                continue  # Already shown above
            print(f"  {noun:<12}{info['description']}")

        if user_exts:
            print()
            print("User Extensions:")
            for noun, info in sorted(user_exts.items()):
                print(f"  {noun:<12}{info['description']}")
    else:
        print()
        print("Type 'neut' with no args for interactive mode.")
        print("Run 'neut --help-all' for all commands.")


def _suggest_command(cmd: str, valid_commands: list[str]) -> str | None:
    """Suggest a similar command using fuzzy matching."""
    from difflib import get_close_matches
    matches = get_close_matches(cmd, valid_commands, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _dispatch_extension(subcommand: str, ext_info: dict) -> None:
    """Dispatch to an extension command (builtin or user).

    Builtins use importlib.import_module() (they are part of the package).
    User extensions use spec_from_file_location() (loaded from arbitrary paths).
    """
    module_path = ext_info["module"]
    is_builtin = ext_info.get("builtin", False)

    try:
        if is_builtin:
            import importlib
            mod = importlib.import_module(module_path)
            mod.main()
        else:
            # User extension — load from file path
            ext_root = Path(ext_info.get("root", ""))
            mod_rel = ext_info.get("module", "")
            mod_file = ext_root / mod_rel.replace(".", "/")
            # Try as .py file or as package
            if mod_file.with_suffix(".py").exists():
                mod_file = mod_file.with_suffix(".py")
            elif (mod_file / "__init__.py").exists():
                mod_file = mod_file / "__init__.py"
            else:
                print(f"neut: extension module not found: {mod_rel}")
                sys.exit(1)
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"neut_ext.{subcommand}", str(mod_file)
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.main()
            else:
                print(f"neut: cannot load extension module: {mod_file}")
                sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except ImportError as e:
        print(f"neut: failed to load {subcommand}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"neut: command '{subcommand}' failed: {e}")
        sys.exit(1)


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

    # --version / -V flag
    if len(sys.argv) >= 2 and sys.argv[1] in ("--version", "-V"):
        try:
            from importlib.metadata import version
            v = version("neutron-os")
        except Exception:
            v = "unknown"
        print(f"neut {v}")
        sys.exit(0)

    # Show pending changelog from a recent update, then check for newer version
    _show_pending_changelog()
    _check_and_prompt_update()

    if len(sys.argv) < 2:
        if sys.stdin.isatty() and sys.stdout.isatty():
            # Bare `neut` → interactive chat, dispatched through extensions
            sys.argv = ["neut chat", "--bare"]
            ext_cmds = _merge_extension_commands()
            if "chat" in ext_cmds:
                try:
                    _dispatch_extension("chat", ext_cmds["chat"])
                except SystemExit:
                    pass
            else:
                print("neut: chat extension not found")
            sys.exit(0)
        else:
            print_usage()
            sys.exit(1)

    subcommand = sys.argv[1]

    if subcommand in ("-h", "--help", "help"):
        print_usage()
        sys.exit(0)

    if subcommand == "--help-all":
        print_usage(show_all=True)
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

    # Check extension commands (builtin + user) if not a core command
    ext_cmd_info = None
    if not module_path:
        ext_cmds = _merge_extension_commands()
        if subcommand in ext_cmds:
            ext_cmd_info = ext_cmds[subcommand]

    if not module_path and not ext_cmd_info:
        all_cmds = list(SUBCOMMANDS.keys()) + list(_merge_extension_commands().keys())
        suggestion = _suggest_command(subcommand, all_cmds)
        print(f"neut: unknown subcommand '{subcommand}'")
        if suggestion:
            print(f"\nDid you mean: neut {suggestion}?")
        print("\nRun 'neut --help' for usage.")
        sys.exit(1)

    # Remove the subcommand from argv so the handler sees only its own args
    sys.argv = [f"neut {subcommand}"] + sys.argv[2:]

    if ext_cmd_info:
        _dispatch_extension(subcommand, ext_cmd_info)
    else:
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
