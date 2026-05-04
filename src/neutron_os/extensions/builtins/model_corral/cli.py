"""CLI handler for `neut model` — physics model registry.

Usage:
    neut model init <name>              Scaffold a new model directory
    neut model validate <path>          Validate a model against schema
    neut model add <path>               Submit model to registry
    neut model search <query>           Search models
    neut model list [--filters]         List models with filters
    neut model show <model_id>          Show model details
    neut model pull <model_id> [dest]   Download model
    neut model clone <model_id>         Clone for editing (fork)
    neut model lineage <model_id>       Show ROM → physics chain
    neut model diff <id_a> <id_b>       Compare two models
    neut model generate <path>          Generate input deck sections
    neut model lint <path>              Run standardization checks
    neut model sweep <path>             Generate parametric variants
    neut model export <model_id>        Export as ZIP archive
    neut model audit [--since DATE]     View change history
    neut model materials [query]        Browse material compositions
    neut model share <model_id>         Package model for sharing
    neut model receive <path>           Import a shared model pack
    neut model invite <email>           Invite a collaborator
    neut model contributors <model_id>  Show who contributed to lineage
    neut model status [model_id]        Show model status & next actions
"""

from __future__ import annotations

import argparse
import json
import sys

# Progressive disclosure — graceful degradation if axiom.infra.cli_tiers unavailable
try:
    from axiom.infra.cli_tiers import get_user_tier, record_action, should_show_command

    _HAS_CLI_TIERS = True
except ImportError:
    _HAS_CLI_TIERS = False


def _make_tiered_print_help(parser: argparse.ArgumentParser, noun: str):
    """Create a print_help method that filters subcommands by user tier."""
    _original_print_help = parser.print_help

    def _print_help(file=None):
        if not _HAS_CLI_TIERS:
            return _original_print_help(file)

        try:
            tier = get_user_tier()
        except Exception:
            return _original_print_help(file)

        # Save originals and filter
        saved = {}
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                saved["npm"] = action._name_parser_map.copy()
                saved["choices"] = dict(action.choices) if action.choices else {}
                saved["choices_actions"] = list(action._choices_actions)
                hidden = [
                    name
                    for name in list(action._name_parser_map.keys())
                    if not should_show_command(noun, name, tier)
                ]
                hidden_set = set(hidden)
                for name in hidden:
                    del action._name_parser_map[name]
                action.choices = {k: v for k, v in action.choices.items() if k not in hidden_set}
                action._choices_actions = [
                    ca for ca in action._choices_actions if ca.dest not in hidden_set
                ]
                break
        else:
            hidden = []

        _original_print_help(file)

        # Restore
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction) and saved:
                action._name_parser_map = saved["npm"]
                action.choices = saved["choices"]
                action._choices_actions = saved["choices_actions"]
                break

        # Append hint
        if hidden and tier < 4:
            import sys as _sys

            out = file or _sys.stdout
            try:
                from axiom.infra.branding import get_branding as _gb_tier

                _tier_cli = _gb_tier().cli_name
            except Exception:
                _tier_cli = "neut"
            out.write(
                f"\n  ({len(hidden)} more commands available at higher tiers."
                f" Run `{_tier_cli} settings set cli.tier {tier + 1}` to unlock.)\n"
            )

    parser.print_help = _print_help


_EPILOG = """\
Got an MCNP deck? Start here:

  neut model add ./your-deck.i        Register it (auto-detects code type)
  neut model list                     See what's registered
  neut model materials --card UO2     Generate verified MCNP material cards

Browse materials:

  neut model materials                All 11 verified compositions
  neut model materials --card UZrH-20 Generate MCNP card for UZrH-20
  neut model materials --category fuel Show fuels only

Facility packs (pre-built material sets for your reactor):

  neut facility list                  Available packs
  neut facility install NETL-TRIGA    Install NETL-TRIGA pack
  neut facility materials NETL-TRIGA  Materials in the pack

More workflows (unlocked as you use the tool):

  neut model clone <id> --name variant  Fork a model for editing
  neut model diff <id_a> <id_b>         Compare two versions
  neut model generate ./model --format mcnp -o materials.i
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut model",
        description="Physics model registry — versioning, validation, and provenance",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="action")

    # init
    init_p = sub.add_parser("init", help="Scaffold a new model directory")
    init_p.add_argument("name", help="Model name (kebab-case)")
    init_p.add_argument(
        "-r", "--reactor-type", help="Reactor type (TRIGA, MSR, PWR, BWR, HTGR, SFR, custom)"
    )
    init_p.add_argument(
        "-c", "--physics-code", help="Physics code (MCNP, VERA, SAM, Griffin, OpenMC, etc.)"
    )
    init_p.add_argument("-f", "--facility", help="Facility identifier (e.g., NETL, MIT)")
    init_p.add_argument(
        "--materials",
        action="store_true",
        help="Pre-populate materials section from installed facility pack",
    )
    init_p.add_argument("--json", action="store_true", help="Output JSON")

    # validate
    val_p = sub.add_parser("validate", help="Validate a model directory")
    val_p.add_argument("path", nargs="?", default=".", help="Path to model directory (default: .)")
    val_p.add_argument("--format", choices=["human", "json"], default="human")

    # add
    add_p = sub.add_parser("add", help="Submit model to registry")
    add_p.add_argument(
        "path", nargs="?", default=".", help="Path to model directory or MCNP file (default: .)"
    )
    add_p.add_argument("-m", "--message", default="", help="Submission message")
    add_p.add_argument(
        "--from-coreforge",
        action="store_true",
        help="Capture CoreForge provenance (config, builder, geometry hash)",
    )
    add_p.add_argument("--coreforge-config", help="Path to CoreForge .py config file")
    add_p.add_argument("--json", action="store_true", help="Output JSON")

    # search
    search_p = sub.add_parser("search", help="Search models")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--format", choices=["human", "json"], default="human")

    # list
    list_p = sub.add_parser("list", help="List models")
    list_p.add_argument("-r", "--reactor", "--reactor-type", dest="reactor_type")
    list_p.add_argument("-c", "--code", "--physics-code", dest="physics_code")
    list_p.add_argument("-s", "--status")
    list_p.add_argument("-f", "--facility")
    list_p.add_argument("--format", choices=["human", "json"], default="human")

    # show
    show_p = sub.add_parser("show", help="Show model details")
    show_p.add_argument("model_id", help="Model identifier")
    show_p.add_argument("--format", choices=["human", "json"], default="human")

    # pull
    pull_p = sub.add_parser("pull", help="Download model")
    pull_p.add_argument("model_id", help="Model identifier")
    pull_p.add_argument("dest", nargs="?", default=".", help="Destination directory")
    pull_p.add_argument("-v", "--version", help="Specific version to pull")
    pull_p.add_argument("--open", action="store_true", help="Open in editor after download")
    pull_p.add_argument("--json", action="store_true", help="Output JSON")

    # lineage
    lin_p = sub.add_parser("lineage", help="Show ROM → physics model chain")
    lin_p.add_argument("model_id", help="Model identifier")
    lin_p.add_argument("--format", choices=["human", "json"], default="human")

    # clone
    clone_p = sub.add_parser("clone", help="Clone a model for editing (creates fork)")
    clone_p.add_argument("model_id", help="Model to clone")
    clone_p.add_argument("--name", help="New model name (auto-generated if omitted)")
    clone_p.add_argument(
        "--progression",
        action="store_true",
        help="Auto-name as next progression level (e.g., progression-1 → progression-1-run)",
    )
    clone_p.add_argument("--no-open", action="store_true", help="Don't open in editor")
    clone_p.add_argument("--json", action="store_true", help="Output JSON")

    # diff
    diff_p = sub.add_parser("diff", help="Compare two model versions")
    diff_p.add_argument("model_a", help="First model (model_id or model_id@version)")
    diff_p.add_argument("model_b", help="Second model")
    diff_p.add_argument("--format", choices=["human", "json"], default="human")

    # export
    export_p = sub.add_parser("export", help="Export model as ZIP")
    export_p.add_argument("model_id", help="Model identifier")
    export_p.add_argument("--output", "-o", help="Output file path")
    export_p.add_argument("--json", action="store_true", help="Output JSON")

    # audit
    audit_p = sub.add_parser("audit", help="View change history")
    audit_p.add_argument("--since", help="Show changes since date (ISO 8601)")
    audit_p.add_argument("--model", dest="model_id", help="Filter by model")
    audit_p.add_argument("--format", choices=["human", "json"], default="human")

    # generate
    gen_p = sub.add_parser("generate", help="Generate input deck sections from model.yaml")
    gen_p.add_argument("path", nargs="?", default=".", help="Path to model directory (default: .)")
    gen_p.add_argument(
        "--section",
        default="materials",
        choices=["materials"],
        help="Section to generate (default: materials)",
    )
    gen_p.add_argument(
        "--format", choices=["mcnp", "mpact", "json"], default="mcnp", help="Output format"
    )
    gen_p.add_argument("-o", "--output", help="Write to file instead of stdout")

    # lint
    lint_p = sub.add_parser("lint", help="Run standardization checks")
    lint_p.add_argument("path", nargs="?", default=".", help="Path to model directory (default: .)")
    lint_p.add_argument("--format", choices=["human", "json"], default="human")

    # sweep
    sweep_p = sub.add_parser("sweep", help="Generate parametric variants")
    sweep_p.add_argument(
        "path", nargs="?", default=".", help="Path to model directory (default: .)"
    )
    sweep_p.add_argument("--param", required=True, help="Parameter to sweep (e.g., enrichment)")
    sweep_p.add_argument(
        "--values", required=True, help="Comma-separated values (e.g., 0.05,0.10,0.20)"
    )
    sweep_p.add_argument("--output-dir", help="Output directory for variants")
    sweep_p.add_argument("--json", action="store_true", help="Output JSON")

    # materials
    mat_p = sub.add_parser("materials", help="Browse verified material compositions")
    mat_p.add_argument("query", nargs="?", help="Search materials by name/category")
    mat_p.add_argument(
        "--category", choices=["fuel", "moderator", "coolant", "structural", "absorber", "other"]
    )
    mat_p.add_argument("--card", metavar="NAME", help="Generate MCNP material card for NAME")
    mat_p.add_argument(
        "--mat-number", type=int, default=1, help="MCNP material number (default: 1)"
    )
    mat_p.add_argument("--format", choices=["human", "json", "mcnp", "mpact"], default="human")

    # share
    share_p = sub.add_parser("share", help="Package model for federation sharing")
    share_p.add_argument("model_id", help="Model to share")
    share_p.add_argument("-o", "--output", help="Output .axiompack path")
    share_p.add_argument(
        "--access-tier",
        choices=["public", "facility", "export_controlled"],
        default="facility",
    )
    share_p.add_argument("--json", action="store_true", help="Output JSON")

    # receive
    recv_p = sub.add_parser("receive", help="Import a shared model pack")
    recv_p.add_argument("path", help="Path to .axiompack file")
    recv_p.add_argument("--json", action="store_true", help="Output JSON")

    # invite
    invite_p = sub.add_parser("invite", help="Invite a collaborator to your model registry")
    invite_p.add_argument("email", help="Collaborator's email address")
    invite_p.add_argument("--models", nargs="*", help="Specific models to share (default: all)")
    invite_p.add_argument("--message", "-m", default="", help="Personal message")
    invite_p.add_argument("--json", action="store_true", help="Output JSON")

    # contributors
    contrib_p = sub.add_parser("contributors", help="Show who contributed to a model's lineage")
    contrib_p.add_argument("model_id", help="Model identifier")
    contrib_p.add_argument("--format", choices=["human", "json"], default="human")

    # status (model-specific)
    mstatus_p = sub.add_parser("status", help="Show model status with suggested next actions")
    mstatus_p.add_argument(
        "model_id", nargs="?", help="Model identifier (default: current directory)"
    )
    mstatus_p.add_argument("--format", choices=["human", "json"], default="human")

    # review (add a comment)
    review_p = sub.add_parser("review", help="Leave a review comment on a model")
    review_p.add_argument("model_id", help="Model to review")
    review_p.add_argument("--comment", "-c", required=True, help="Review comment")
    review_p.add_argument("--json", action="store_true")

    # reviews (list comments)
    reviews_p = sub.add_parser("reviews", help="Show review comments on a model")
    reviews_p.add_argument("model_id", nargs="?", default=".", help="Model identifier or directory")
    reviews_p.add_argument("--status", choices=["open", "addressed", "dismissed"], default=None)
    reviews_p.add_argument("--format", choices=["human", "json"], default="human")

    # resolve (address a comment)
    resolve_p = sub.add_parser("resolve", help="Mark a review comment as addressed")
    resolve_p.add_argument("model_id", help="Model identifier")
    resolve_p.add_argument("review_id", help="Review ID to resolve")
    resolve_p.add_argument("--dismiss", action="store_true", help="Dismiss instead of address")

    _make_tiered_print_help(parser, "model")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.action:
        parser.print_help()
        return 1

    handlers = {
        "init": _cmd_init,
        "validate": _cmd_validate,
        "add": _cmd_add,
        "clone": _cmd_clone,
        "search": _cmd_search,
        "list": _cmd_list,
        "show": _cmd_show,
        "pull": _cmd_pull,
        "lineage": _cmd_lineage,
        "diff": _cmd_diff,
        "export": _cmd_export,
        "audit": _cmd_audit,
        "generate": _cmd_generate,
        "lint": _cmd_lint,
        "sweep": _cmd_sweep,
        "materials": _cmd_materials,
        "share": _cmd_share,
        "receive": _cmd_receive,
        "invite": _cmd_invite,
        "contributors": _cmd_contributors,
        "status": _cmd_model_status,
        "review": _cmd_review,
        "reviews": _cmd_reviews,
        "resolve": _cmd_resolve,
    }

    handler = handlers.get(args.action)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_init(args) -> int:
    from pathlib import Path

    from neutron_os.extensions.builtins.model_corral.commands.init import model_init

    try:
        model_dir = model_init(
            args.name,
            reactor_type=args.reactor_type or "custom",
            physics_code=args.physics_code or "MCNP",
            facility=getattr(args, "facility", "") or "",
            output_dir=Path.cwd(),
            include_materials=getattr(args, "materials", False),
        )
        if getattr(args, "json", False):
            print(json.dumps({"path": str(model_dir), "model_id": args.name}, indent=2))
        else:
            print(f"Created: {model_dir}/")
            print("\nNext steps:")
            print(f"  1. Add your input files to {model_dir}/")
            print(f"  2. Edit {model_dir}/model.yaml (fill in description, facility, tags)")
            print(f"  3. Run: neut model validate {model_dir}")
            print(f"  4. Run: neut model add {model_dir}")

            # Open in editor if available
            _open_in_editor(model_dir)
        _record("model", "init")
        return 0
    except (ValueError, FileExistsError) as e:
        print(f"Error: {e}")
        return 1


def _cmd_validate(args) -> int:
    from neutron_os.extensions.builtins.model_corral.commands.validate import cmd_validate

    return cmd_validate(args.path, output_format=getattr(args, "format", "human"))


def _cmd_add(args) -> int:
    from pathlib import Path

    path = Path(getattr(args, "path", "."))

    # Auto-detect: if path is an MCNP file, auto-create model directory
    if path.is_file():
        from neutron_os.extensions.builtins.model_corral.commands.auto_add import (
            auto_add_mcnp,
            is_mcnp_file,
        )

        if is_mcnp_file(path):
            try:
                model_dir = auto_add_mcnp(path, message=getattr(args, "message", ""))
                # Continue with normal add flow using the new directory
                args.path = str(model_dir)
            except (ValueError, FileNotFoundError) as e:
                print(f"Error: {e}")
                return 1
        else:
            print(f"Error: {path} is a file but not a recognized MCNP input deck.")
            print("  Supported extensions: .i, .inp, .mcnp")
            return 1

    svc = _get_service()

    # Capture CoreForge provenance if requested
    coreforge_prov = None
    if getattr(args, "from_coreforge", False):
        from neutron_os.extensions.builtins.model_corral.coreforge_bridge import (
            extract_provenance,
            is_coreforge_available,
        )

        if not is_coreforge_available():
            print("Warning: CoreForge not installed — provenance will be partial")

        config_path = None
        if getattr(args, "coreforge_config", None):
            config_path = Path(args.coreforge_config)

        coreforge_prov = extract_provenance(config_path=config_path)

    result = svc.add(
        Path(args.path),
        message=getattr(args, "message", ""),
        coreforge_provenance=coreforge_prov.to_dict() if coreforge_prov else None,
    )
    if result.success:
        if getattr(args, "json", False):
            data = {
                "model_id": result.model_id,
                "version": result.version,
                "success": True,
            }
            if coreforge_prov:
                data["coreforge_version"] = coreforge_prov.coreforge_version
            print(json.dumps(data, indent=2))
        else:
            # Friendly success output with next steps
            print(f"\n  Model registered: {result.model_id} (v{result.version})")
            if coreforge_prov:
                print(f"  CoreForge: v{coreforge_prov.coreforge_version}")

            # Show what was discovered (not what the user already knows)
            try:
                model_svc = _get_service()
                model = model_svc.get(result.model_id)
                if model:
                    print("  Detected:")
                    rtype = getattr(model, "reactor_type", None)
                    if rtype:
                        print(f"    Reactor type: {rtype}")
                    fac = getattr(model, "facility", None)
                    if fac and fac != "unknown":
                        print(f"    Facility:     {fac}")
                    mats = getattr(model, "materials", None)
                    if mats:
                        mat_names = [
                            m.get("name", m) if isinstance(m, dict) else str(m) for m in mats[:5]
                        ]
                        print(f"    Materials:    {', '.join(mat_names)}")
                    det_mat_nums = getattr(model, "_detected_material_numbers", None)
                    if det_mat_nums and not mats:
                        print(
                            f"    Material cards found: {len(det_mat_nums)}"
                            f" (m{', m'.join(str(n) for n in det_mat_nums[:8])})"
                        )
            except Exception:
                pass  # detection output is best-effort

            try:
                from axiom.infra.branding import get_branding as _gb_add

                _cli = _gb_add().cli_name
            except Exception:
                _cli = "neut"

            print("\n  Next steps:")
            print(f"    {_cli} model list                         See all your models")
            print(f"    {_cli} model show {result.model_id:<20s}  Full details")
            print(f"    {_cli} model validate {result.model_id:<15s}  Run checks")
            print(f"    {_cli} model materials --card UO2         Generate material cards")
        _record("model", "add")
        return 0
    if getattr(args, "json", False):
        print(json.dumps({"success": False, "error": result.error}, indent=2))
    else:
        print(f"Error: {result.error}")
    return 1


def _cmd_clone(args) -> int:
    from pathlib import Path

    from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

    svc = _get_service()

    new_name = getattr(args, "name", "") or ""
    progression = getattr(args, "progression", False)
    progression_desc = ""

    if progression and not new_name:
        new_name, progression_desc = _progression_name(args.model_id, svc)

    try:
        clone_dir = model_clone(
            args.model_id,
            svc,
            new_name=new_name,
            output_dir=Path.cwd(),
        )

        # If progression, update the description in model.yaml
        if progression and progression_desc:
            import yaml as _yaml

            manifest_path = clone_dir / "model.yaml"
            if manifest_path.exists():
                text = manifest_path.read_text(encoding="utf-8")
                data = _yaml.safe_load(text)
                data["description"] = progression_desc
                header = ""
                for line in text.splitlines():
                    if line.startswith("# yaml-language-server"):
                        header = line + "\n"
                        break
                manifest_path.write_text(
                    header + _yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "clone_dir": str(clone_dir),
                        "parent": args.model_id,
                        "model_id": clone_dir.name,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Cloned: {clone_dir}/")
            print(f"  Forked from: {args.model_id}")
            print("\nNext steps:")
            print("  1. Edit your files and model.yaml")
            print(f"  2. Run: neut model validate {clone_dir}")
            print(f"  3. Run: neut model add {clone_dir}")

            if not getattr(args, "no_open", False):
                _open_in_editor(clone_dir)
        _record("model", "clone")
        return 0
    except (FileExistsError, RuntimeError) as e:
        print(f"Error: {e}")
        return 1


def _cmd_search(args) -> int:
    svc = _get_service()
    results = svc.search(args.query)

    if getattr(args, "format", "human") == "json":
        print(json.dumps(results, indent=2))
    elif not results:
        print("No models found.")
    else:
        print(f"Found {len(results)} model(s):\n")
        for m in results:
            status = m.get("status", "")
            print(f"  {m['model_id']:<40} {m['reactor_type']:<8} {m['physics_code']:<8} {status}")
    return 0


def _cmd_list(args) -> int:
    svc = _get_service()
    models = svc.list_models(
        reactor_type=getattr(args, "reactor_type", None),
        physics_code=getattr(args, "physics_code", None),
        status=getattr(args, "status", None),
        facility=getattr(args, "facility", None),
    )

    if getattr(args, "format", "human") == "json":
        print(json.dumps(models, indent=2))
    elif not models:
        print("No models in registry.")
    else:
        print(f"{'Model ID':<40} {'Reactor':<8} {'Code':<8} {'Status':<12} {'Facility'}")
        print("-" * 80)
        for m in models:
            print(
                f"{m['model_id']:<40} {m['reactor_type']:<8} {m['physics_code']:<8} "
                f"{m['status']:<12} {m.get('facility', '')}"
            )
    return 0


def _cmd_show(args) -> int:
    svc = _get_service()
    info = svc.show(args.model_id)
    if info is None:
        print(f"Model not found: {args.model_id}")
        return 1

    if getattr(args, "format", "human") == "json":
        print(json.dumps(info, indent=2, default=str))
    else:
        print(f"Model: {info['model_id']}")
        print(f"  Name:         {info['name']}")
        print(f"  Reactor:      {info['reactor_type']}")
        print(f"  Code:         {info['physics_code']}")
        print(f"  Status:       {info['status']}")
        print(f"  Access:       {info['access_tier']}")
        print(f"  Facility:     {info.get('facility', '')}")
        print(f"  Created by:   {info['created_by']}")
        if info.get("description"):
            print(f"  Description:  {info['description'][:100]}")
        if info.get("tags"):
            print(f"  Tags:         {', '.join(info['tags'])}")
        if info.get("versions"):
            print(f"\n  Versions ({len(info['versions'])}):")
            for v in info["versions"]:
                print(
                    f"    v{v['version']}  {v.get('created_by', '')}  {v.get('checksum', '')[:12]}..."
                )
        # Show open reviews
        reviews = svc.get_reviews(args.model_id, status="open")
        if reviews:
            print(f"\n  Reviews ({len(reviews)} open):")
            for r in reviews:
                comment_preview = r["comment"][:60]
                if len(r["comment"]) > 60:
                    comment_preview += "..."
                print(f"    \u25cb {r['reviewer']}: {comment_preview}")
    return 0


def _cmd_pull(args) -> int:
    from pathlib import Path

    svc = _get_service()
    dest = Path(args.dest) / args.model_id
    result = svc.pull(args.model_id, dest, version=getattr(args, "version", None))
    if result.success:
        if getattr(args, "json", False):
            data = {
                "path": str(dest),
                "model_id": args.model_id,
                "version": getattr(args, "version", None),
            }
            print(json.dumps(data, indent=2))
        else:
            print(f"Downloaded to: {dest}")
            if getattr(args, "open", False):
                _open_in_editor(dest)
        return 0
    if getattr(args, "json", False):
        print(json.dumps({"error": result.error}, indent=2))
    else:
        print(f"Error: {result.error}")
    return 1


def _cmd_lineage(args) -> int:
    svc = _get_service()
    chain = svc.lineage(args.model_id)

    if getattr(args, "format", "human") == "json":
        print(json.dumps(chain, indent=2))
    elif not chain:
        print(f"{args.model_id}: no parent models (root)")
    else:
        print(f"Lineage for {args.model_id}:")
        for entry in chain:
            print(f"  <- {entry['parent_model_id']} ({entry['relationship_type']})")
    return 0


def _cmd_diff(args) -> int:
    import difflib
    import tempfile
    from pathlib import Path

    svc = _get_service()
    a = svc.show(args.model_a)
    b = svc.show(args.model_b)

    output_json = getattr(args, "format", "human") == "json"

    if a is None:
        print(f"Model not found: {args.model_a}")
        return 1
    if b is None:
        print(f"Model not found: {args.model_b}")
        return 1

    # Pull both to temp dirs for full diff
    with tempfile.TemporaryDirectory() as tmp:
        dir_a = Path(tmp) / "a"
        dir_b = Path(tmp) / "b"
        res_a = svc.pull(args.model_a, dir_a)
        res_b = svc.pull(args.model_b, dir_b)

        if not res_a.success or not res_b.success:
            # Fall back to metadata diff
            if output_json:
                print(json.dumps({"model_a": a, "model_b": b, "type": "metadata"}, indent=2))
            else:
                print(f"Comparing metadata: {args.model_a} vs {args.model_b}\n")
                _diff_metadata(a, b)
            return 0

        # Diff model.yaml (the most important file)
        yaml_a = (dir_a / "model.yaml").read_text() if (dir_a / "model.yaml").exists() else ""
        yaml_b = (dir_b / "model.yaml").read_text() if (dir_b / "model.yaml").exists() else ""

        # Show files that differ or are only in one
        files_a = {str(f.relative_to(dir_a)) for f in dir_a.rglob("*") if f.is_file()}
        files_b = {str(f.relative_to(dir_b)) for f in dir_b.rglob("*") if f.is_file()}

        only_a = sorted(files_a - files_b)
        only_b = sorted(files_b - files_a)

        if output_json:
            diff_lines = list(
                difflib.unified_diff(
                    yaml_a.splitlines(),
                    yaml_b.splitlines(),
                    fromfile=args.model_a,
                    tofile=args.model_b,
                )
            )
            print(
                json.dumps(
                    {
                        "model_a": args.model_a,
                        "model_b": args.model_b,
                        "yaml_diff": diff_lines,
                        "only_in_a": only_a,
                        "only_in_b": only_b,
                    },
                    indent=2,
                )
            )
        else:
            if yaml_a != yaml_b:
                print(f"--- {args.model_a}/model.yaml")
                print(f"+++ {args.model_b}/model.yaml")
                diff = difflib.unified_diff(
                    yaml_a.splitlines(keepends=True),
                    yaml_b.splitlines(keepends=True),
                    fromfile=args.model_a,
                    tofile=args.model_b,
                )
                for line in diff:
                    if line.startswith("+") and not line.startswith("+++"):
                        print(f"\033[32m{line}\033[0m", end="")
                    elif line.startswith("-") and not line.startswith("---"):
                        print(f"\033[31m{line}\033[0m", end="")
                    else:
                        print(line, end="")
                print()

            if only_a:
                print(f"Only in {args.model_a}:")
                for f in only_a:
                    print(f"  - {f}")
            if only_b:
                print(f"Only in {args.model_b}:")
                for f in only_b:
                    print(f"  + {f}")

            if yaml_a == yaml_b and not only_a and not only_b:
                print("No differences found.")

    return 0


def _diff_metadata(a: dict, b: dict) -> None:
    """Fallback metadata-only diff."""
    fields = [
        "reactor_type",
        "physics_code",
        "status",
        "facility",
        "access_tier",
        "description",
        "created_by",
    ]
    changed = False
    for field in fields:
        va = a.get(field, "")
        vb = b.get(field, "")
        if va != vb:
            changed = True
            print(f"  {field}:")
            print(f"    \033[31m- {va}\033[0m")
            print(f"    \033[32m+ {vb}\033[0m")
    if not changed:
        print("  No metadata differences.")


def _cmd_export(args) -> int:
    import shutil
    import tempfile
    from pathlib import Path

    svc = _get_service()
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / args.model_id
        result = svc.pull(args.model_id, dest)
        if not result.success:
            print(f"Error: {result.error}")
            return 1

        output = getattr(args, "output", None) or f"{args.model_id}.zip"
        output = output.removesuffix(".zip")
        shutil.make_archive(output, "zip", dest)
        if getattr(args, "json", False):
            print(json.dumps({"path": f"{output}.zip"}, indent=2))
        else:
            print(f"Exported: {output}.zip")
    return 0


def _cmd_audit(args) -> int:
    svc = _get_service()
    output_json = getattr(args, "format", "human") == "json"
    # Simple audit — list all versions with timestamps
    models = svc.list_models()
    if not models:
        if output_json:
            print(json.dumps([], indent=2))
        else:
            print("No models in registry.")
        return 0

    if output_json:
        audit_records = []
        for m in models:
            info = svc.show(m["model_id"])
            if info and info.get("versions"):
                for v in info["versions"]:
                    audit_records.append(
                        {
                            "model_id": m["model_id"],
                            "version": v["version"],
                            "created_by": v.get("created_by", ""),
                            "checksum": v.get("checksum", ""),
                        }
                    )
        print(json.dumps(audit_records, indent=2))
    else:
        print(f"{'Model ID':<40} {'Version':<10} {'Created By':<25} {'Checksum'}")
        print("-" * 90)
        for m in models:
            info = svc.show(m["model_id"])
            if info and info.get("versions"):
                for v in info["versions"]:
                    print(
                        f"{m['model_id']:<40} v{v['version']:<9} "
                        f"{v.get('created_by', ''):<25} {(v.get('checksum') or '')[:16]}"
                    )
    return 0


def _cmd_generate(args) -> int:
    from neutron_os.extensions.builtins.model_corral.commands.generate import cmd_generate

    return cmd_generate(
        args.path,
        section=getattr(args, "section", "materials"),
        output_format=getattr(args, "format", "mcnp"),
        output=getattr(args, "output", None),
    )


def _cmd_lint(args) -> int:
    from neutron_os.extensions.builtins.model_corral.commands.lint import cmd_lint

    return cmd_lint(args.path, output_format=getattr(args, "format", "human"))


def _cmd_sweep(args) -> int:
    from neutron_os.extensions.builtins.model_corral.commands.sweep import cmd_sweep

    rc = cmd_sweep(
        args.path,
        param=args.param,
        values=args.values,
        output_dir=getattr(args, "output_dir", None),
        output_json=getattr(args, "json", False),
    )
    if rc == 0:
        _record("model", "sweep")
    return rc


def _cmd_materials(args) -> int:
    import json

    from neutron_os.extensions.builtins.model_corral.materials_db import (
        get_material,
        list_materials,
        search_materials,
    )

    # Generate specific material card
    card_name = getattr(args, "card", None)
    if card_name:
        mat = get_material(card_name)
        if mat is None:
            print(f"Material not found: {card_name}")
            return 1
        fmt = getattr(args, "format", "mcnp")
        mat_num = getattr(args, "mat_number", 1)
        if fmt == "mpact":
            print(mat.mpact_card())
        else:
            print(mat.mcnp_cards(mat_number=mat_num))
        return 0

    # List/search materials
    category = getattr(args, "category", None)
    query = getattr(args, "query", None)

    if query:
        materials = search_materials(query)
    elif category:
        materials = list_materials(category=category)
    else:
        materials = list_materials()

    fmt = getattr(args, "format", "human")

    if fmt == "json":
        print(json.dumps([m.to_dict() for m in materials], indent=2))
    elif not materials:
        print("No materials found.")
    elif query or category:
        # Filtered view — simple table
        print(f"{'Name':<15} {'Category':<12} {'Density':<10} {'Description'}")
        print("-" * 75)
        for m in materials:
            print(f"{m.name:<15} {m.category:<12} {m.density:<10.3f} {m.description[:40]}")
        print(f"\n{len(materials)} material(s). Use --card NAME to generate input cards.")
    else:
        # Full listing — grouped by category for discoverability
        by_cat: dict[str, list] = {}
        for m in materials:
            by_cat.setdefault(m.category, []).append(m)

        print(f"Verified material compositions ({len(materials)} materials):\n")
        for cat in ["fuel", "moderator", "coolant", "structural", "absorber", "other"]:
            mats_in_cat = by_cat.get(cat, [])
            if not mats_in_cat:
                continue
            print(f"  {cat.title()}:")
            for m in mats_in_cat:
                print(f"    {m.name:<15} {m.description[:50]:50s} ({m.density:.2f} g/cc)")
            print()

        # Show leftover categories not in the standard list
        for cat, mats_in_cat in by_cat.items():
            if cat not in {"fuel", "moderator", "coolant", "structural", "absorber", "other"}:
                print(f"  {cat.title()}:")
                for m in mats_in_cat:
                    print(f"    {m.name:<15} {m.description[:50]:50s} ({m.density:.2f} g/cc)")
                print()

        try:
            from axiom.infra.branding import get_branding as _gb_mat

            _cli = _gb_mat().cli_name
        except Exception:
            _cli = "neut"

        print(f"Generate MCNP cards:  {_cli} model materials --card UO2")
        print(f"Generate MPACT cards: {_cli} model materials --card UO2 --format mpact")
        print(f"Filter by category:   {_cli} model materials --category fuel")
        print("\nSources: PNNL-15870, GA-4314, NUREG/CR-6698")

    return 0


def _cmd_share(args) -> int:

    from neutron_os.extensions.builtins.model_corral.federation import ModelSharingService

    sharing = ModelSharingService()
    try:
        access_tier = getattr(args, "access_tier", "public")
        pack_path = sharing.share_model(
            args.model_id,
            access_tier=access_tier,
        )
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {"pack_path": str(pack_path), "access_tier": access_tier},
                    indent=2,
                )
            )
        else:
            print(f"Packaged: {pack_path}")
            print(f"  Access tier: {access_tier}")
            print("\nShare this file with federation peers or transfer manually.")
        _record("model", "share")
        return 0
    except (ValueError, PermissionError) as e:
        print(f"Error: {e}")
        return 1


def _cmd_receive(args) -> int:
    from pathlib import Path

    from neutron_os.extensions.builtins.model_corral.federation import ModelSharingService

    sharing = ModelSharingService()
    try:
        result = sharing.receive_model(Path(args.path))
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "model_id": result["model_id"],
                        "path": str(result["path"]),
                        "access_tier": result.get("access_tier", "public"),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Received: {result['model_id']}")
            print(f"  Access tier: {result.get('access_tier', 'public')}")
            print(f"  Path: {result['path']}")
        return 0
    except (ValueError, PermissionError, FileNotFoundError) as e:
        print(f"Error: {e}")
        return 1


def _cmd_invite(args) -> int:
    import secrets

    email = args.email
    token = f"neut-invite-{secrets.token_hex(8)}"
    models = getattr(args, "models", None)
    message = getattr(args, "message", "")

    if getattr(args, "json", False):
        print(json.dumps({"token": token, "email": email, "models": models or []}))
    else:
        print(f"Invitation for {email}")
        print(f"  Token: {token}")
        print()
        print(f"Send this to {email}:")
        print("  \u2500" * 41)
        print("  Install: pip install neutron-os")
        print("  Setup:   neut config")
        print(f"  Connect: neut connect --token {token}")
        if models:
            print(f"  Models:  {', '.join(models)}")
        if message:
            print(f"  Note:    {message}")
        print("  \u2500" * 41)

    _record("model", "invite")
    return 0


def _cmd_contributors(args) -> int:
    svc = _get_service()

    contributors: dict[str, list[str]] = {}
    models_in_chain: set[str] = set()

    def _walk(model_id: str) -> None:
        if model_id in models_in_chain:
            return
        models_in_chain.add(model_id)
        info = svc.show(model_id)
        if info:
            author = info.get("created_by", "")
            if author:
                if author not in contributors:
                    contributors[author] = []
                contributors[author].append(model_id)
            # Walk parents
            for entry in svc.lineage(model_id):
                _walk(entry["parent_model_id"])

    _walk(args.model_id)

    if getattr(args, "format", "human") == "json":
        print(json.dumps(contributors, indent=2))
    else:
        if not contributors:
            print(f"Model not found: {args.model_id}")
            return 1
        print(f"Contributors to {args.model_id} lineage:")
        for author, models in contributors.items():
            print(f"  {author}: {', '.join(models)}")
    return 0


def _cmd_model_status(args) -> int:
    import yaml as _yaml

    model_id = getattr(args, "model_id", None)
    if not model_id:
        from pathlib import Path

        model_yaml = Path.cwd() / "model.yaml"
        if model_yaml.exists():
            data = _yaml.safe_load(model_yaml.read_text())
            model_id = data.get("model_id", "")

    if not model_id:
        print("No model specified and no model.yaml in current directory.")
        return 1

    svc = _get_service()
    info = svc.show(model_id)
    if info is None:
        print(f"Model not found: {model_id}")
        return 1

    output_json = getattr(args, "format", "human") == "json"

    # Collect lineage
    lineage = svc.lineage(model_id)

    # Find children (models derived from this one)
    children = []
    for m in svc.list_models():
        for entry in svc.lineage(m["model_id"]):
            if entry["parent_model_id"] == model_id:
                children.append(m["model_id"])
                break

    if output_json:
        latest_version = info["versions"][-1]["version"] if info.get("versions") else None
        result = {
            "model_id": model_id,
            "version": latest_version,
            "status": info["status"],
            "created_by": info["created_by"],
            "reactor_type": info["reactor_type"],
            "physics_code": info["physics_code"],
            "lineage": lineage,
            "children": children,
        }
        print(json.dumps(result, indent=2))
    else:
        latest_v = info["versions"][-1]["version"] if info.get("versions") else "?"
        print(f"Model: {info['model_id']} v{latest_v}")
        print(f"  Status: {info['status']}")
        print(f"  Author: {info['created_by']}")
        print(f"  Reactor: {info['reactor_type']}  Code: {info['physics_code']}")

        if lineage:
            print("\n  Lineage:")
            for entry in lineage:
                print(f"    \u2190 {entry['parent_model_id']} ({entry['relationship_type']})")

        if children:
            print("\n  Derived models:")
            for c in children:
                print(f"    \u2192 {c}")

        # Suggest next actions based on status
        print("\n  Suggested actions:")
        if info["status"] == "draft":
            print("    neut model validate          # check for issues")
            print("    neut model lint              # standardization checks")
            if not lineage:
                print("    neut model generate          # create material cards")
        elif info["status"] == "review":
            print("    neut model validate          # re-validate before approval")
            print(f"    neut model diff {model_id}@v1 {model_id}@latest  # see what changed")
        elif info["status"] == "production":
            print(f"    neut model clone {model_id}  # fork for modifications")
            print(f"    neut model export {model_id} # archive as ZIP")

    return 0


def _progression_name(model_id: str, svc) -> tuple[str, str]:
    """Derive a progression clone name from a model_id.

    Returns (new_name, description).
    """
    import re

    match = re.search(r"progression[- ]?(\d+)", model_id)
    if match:
        num = int(match.group(1))
        # Check if a "run" variant exists
        run_name = f"{model_id}-run"
        existing = svc.show(run_name)
        if existing:
            # Next progression level
            next_num = num + 1
            prefix = model_id[: match.start()] + f"progression-{next_num}" + model_id[match.end() :]
            return prefix, f"Progression problem {next_num}"
        return run_name, f"Materials run for progression problem {num}"

    # No progression number detected -- just append -run
    return f"{model_id}-run", f"Materials run for {model_id}"


def _cmd_review(args) -> int:
    svc = _get_service()
    # Auto-detect reviewer from git config
    import subprocess

    reviewer = ""
    try:
        result = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            reviewer = result.stdout.strip()
    except Exception:
        pass
    reviewer = reviewer or "anonymous"

    review = svc.add_review(args.model_id, reviewer=reviewer, comment=args.comment)

    if getattr(args, "json", False):
        print(json.dumps(review, indent=2))
    else:
        print(f"Review added to {args.model_id}:")
        print(f"  {review['review_id']}: {args.comment}")
        print(f"  By: {reviewer}")
    _record("model", "review")
    return 0


def _cmd_reviews(args) -> int:
    model_id = args.model_id
    if model_id == ".":
        # Try to detect from cwd
        from pathlib import Path

        import yaml as _yaml

        model_yaml = Path.cwd() / "model.yaml"
        if model_yaml.exists():
            data = _yaml.safe_load(model_yaml.read_text())
            model_id = data.get("model_id", "")

    if not model_id:
        print("No model specified.")
        return 1

    svc = _get_service()
    reviews = svc.get_reviews(model_id, status=getattr(args, "status", None))

    if getattr(args, "format", "human") == "json":
        print(json.dumps(reviews, indent=2))
    elif not reviews:
        print(f"No reviews on {model_id}.")
    else:
        open_count = sum(1 for r in reviews if r.get("status") == "open")
        print(f"Reviews on {model_id} ({open_count} open):\n")
        for r in reviews:
            status_icon = {"open": "\u25cb", "addressed": "\u2713", "dismissed": "\u2717"}.get(
                r["status"], "?"
            )
            print(f"  {status_icon} [{r['review_id']}] {r['reviewer']}:")
            print(f"    {r['comment']}")
            if r.get("version"):
                print(f"    (on v{r['version']})")
            print()
    return 0


def _cmd_resolve(args) -> int:
    svc = _get_service()
    resolution = "dismissed" if getattr(args, "dismiss", False) else "addressed"
    if svc.resolve_review(args.model_id, args.review_id, resolution):
        print(f"Review {args.review_id}: {resolution}")
        _record("model", "resolve")
        return 0
    print(f"Review not found: {args.review_id}")
    return 1


def _record(noun: str, verb: str) -> None:
    """Record a user action for progressive disclosure (best-effort)."""
    if _HAS_CLI_TIERS:
        try:
            record_action(noun, verb)
        except Exception:
            pass


def _open_in_editor(path) -> None:
    """Open a model directory in the user's preferred editor."""
    from axiom.infra.editor import open_in_editor

    editor = open_in_editor(path, file="model.yaml")
    if editor:
        print(f"\nOpened in {editor}.")


# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------


_SERVICE = None


def _get_service():
    """Get or create the ModelCorralService.

    DB URL resolution order:
      1. AXIOM_DB_URL env var (explicit)
      2. PostgreSQL at localhost:5432 (K3D / server install)
      3. SQLite at ~/.neut/model-corral.db (zero-infra fallback)
    """
    global _SERVICE
    if _SERVICE is not None:
        return _SERVICE

    import os

    from sqlalchemy import create_engine, text

    from axiom.infra.paths import get_user_state_dir
    from axiom.infra.storage import LocalStorageProvider
    from neutron_os.extensions.builtins.model_corral.db_models import Base
    from neutron_os.extensions.builtins.model_corral.service import ModelCorralService

    db_url = os.environ.get("AXIOM_DB_URL", "")
    engine = None

    if db_url:
        # Explicit DB URL — use it
        engine = create_engine(db_url)
    else:
        # Try PostgreSQL, fall back to SQLite
        try:
            pg_url = "postgresql://axiom:axiom@localhost:5432/axiom_db"
            test_engine = create_engine(pg_url)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine = test_engine
        except Exception:
            # PostgreSQL not available — use SQLite
            state_dir = get_user_state_dir()
            state_dir.mkdir(parents=True, exist_ok=True)
            sqlite_path = state_dir / "model-corral.db"
            engine = create_engine(f"sqlite:///{sqlite_path}")
            print(
                "Using local database (~/.neut/model-corral.db)."
                " Connect to a server with `neut config` for shared access."
            )

    Base.metadata.create_all(engine)

    state_dir = get_user_state_dir()
    storage = LocalStorageProvider({"base_dir": str(state_dir / "model-storage")})

    _SERVICE = ModelCorralService(engine=engine, storage=storage)
    return _SERVICE


if __name__ == "__main__":
    sys.exit(main())
