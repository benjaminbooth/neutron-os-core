"""CLI handler for `neut db` — PostgreSQL + pgvector infrastructure.

This provides shared database infrastructure for all NeutronOS components.

Subcommands:
    neut db up           Start local K3D cluster with PostgreSQL
    neut db down         Stop local cluster (preserves data)
    neut db delete       Delete cluster and all data
    neut db status       Show cluster and connection status
    neut db migrate      Run Alembic schema migrations
    neut db bootstrap    Full setup from scratch
"""

from __future__ import annotations

import argparse
import os
import re
import sys


# Default connection for local K3D cluster
DEFAULT_LOCAL_URL = "postgresql://neut:neut@localhost:5432/neut_db"


def _mask_url(url: str) -> str:
    """Mask password in connection URL for display."""
    return re.sub(r":[^:@]+@", ":****@", url)


def cmd_up(args: argparse.Namespace) -> int:
    """Start local K3D cluster with PostgreSQL + pgvector."""
    from neutron_os.extensions.builtins.sense_agent.pgvector_store import k3d_up

    print("🚀 Starting local PostgreSQL + pgvector (K3D)...\n")
    success = k3d_up()

    if success:
        print("\nNext steps:")
        print("  neut db migrate upgrade   # Apply schema migrations")
        print("  neut db status            # Verify connection")
        return 0
    else:
        print("\nFailed to start. Check prerequisites above.")
        return 1


def cmd_down(args: argparse.Namespace) -> int:
    """Stop local K3D cluster (preserves data)."""
    from neutron_os.extensions.builtins.sense_agent.pgvector_store import k3d_down

    print("⏸️  Stopping local cluster...\n")
    success = k3d_down()
    return 0 if success else 1


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete local K3D cluster and all data."""
    from neutron_os.extensions.builtins.sense_agent.pgvector_store import k3d_delete

    if not args.confirm:
        print("⚠️  This will DELETE the local cluster and ALL data!")
        print("\nTo confirm, run:")
        print("  neut db delete --confirm")
        return 1

    print("🗑️  Deleting local cluster...\n")
    success = k3d_delete()
    return 0 if success else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show cluster and database status."""
    from neutron_os.extensions.builtins.sense_agent.pgvector_store import k3d_status, VectorDB

    db_url = os.environ.get("NEUT_DB_URL", DEFAULT_LOCAL_URL)
    masked_url = _mask_url(db_url)

    print("\n🗄️  NeutronOS Database Status\n")

    # K3D cluster status
    status = k3d_status()

    print("--- K3D Cluster ---")
    if status.get("k3d_installed") is False:
        print("  K3D:     Not installed")
        print("  Install: brew install k3d")
    elif status.get("exists"):
        running = "✓ Running" if status.get("running") else "○ Stopped"
        print(f"  Cluster: neut-local ({running})")
        print(f"  Servers: {status.get('servers', 0)}")
        print(f"  Agents:  {status.get('agents', 0)}")
    else:
        print("  Cluster: Not created")
        print("  Create:  neut db up")

    print("\n--- Connection ---")
    print(f"  URL: {masked_url}")

    if os.environ.get("NEUT_DB_URL"):
        print("  Source: NEUT_DB_URL environment variable")
    else:
        print("  Source: Default (local K3D)")

    # Test connection if cluster is running
    if status.get("running") or os.environ.get("NEUT_DB_URL"):
        print("\n--- Health Check ---")
        try:
            db = VectorDB()
            db.connect()
            health = db.health_check()

            if health.get("connected"):
                print(f"  Status:     ✓ {health.get('status', 'connected')}")
                pg_version = health.get('postgresql', 'N/A')
                if len(pg_version) > 60:
                    pg_version = pg_version[:60] + "..."
                print(f"  PostgreSQL: {pg_version}")
                print(f"  pgvector:   {health.get('pgvector', 'N/A')}")
            else:
                print(f"  Status:     ✗ {health.get('error', 'Cannot connect')}")

            db.close()
        except Exception as e:
            print(f"  Status:     ✗ Error: {e}")
            return 1

    print("\n--- Environments ---")
    print("  Local:      neut db up  (K3D)")
    print("  Staging:    Set NEUT_DB_URL to staging PostgreSQL")
    print("  Production: Set NEUT_DB_URL to production PostgreSQL")

    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    """Run Alembic database schema migrations."""
    from neutron_os.extensions.builtins.sense_agent.migrations import (
        run_migrations,
        check_migrations,
        verify_schema,
        ensure_pgvector_extension,
    )

    cmd = getattr(args, 'migrate_command', 'check') or 'check'
    revision = getattr(args, 'revision', 'head') or 'head'
    message = getattr(args, 'message', '')
    autogenerate = getattr(args, 'autogenerate', False)

    if cmd == "check":
        print("\n🔍 Migration Status\n")

        status = check_migrations()

        if not status.get("connected"):
            print("❌ Cannot connect to database")
            print("   Is the database running? Try: neut db up")
            return 1

        print(f"Current revision: {status.get('current') or '(none)'}")
        print(f"Head revision:    {status.get('head') or '(none)'}")
        print(f"Pending:          {status.get('pending', 0)} migration(s)")

        if status.get("up_to_date"):
            print("\n✅ Database is up to date")
        else:
            print(f"\n⚠️  {status['pending']} pending migration(s):")
            for rev in status.get("pending_revisions", []):
                print(f"   - {rev}")
            print("\nRun: neut db migrate upgrade head")

        # Also verify schema
        schema = verify_schema()
        if schema.get("valid"):
            print("\n✅ Schema verified")
        else:
            if schema.get("missing_tables"):
                print(f"\n⚠️  Missing tables: {', '.join(schema['missing_tables'])}")
            if not schema.get("has_pgvector"):
                print("⚠️  pgvector extension not installed")

        return 0

    elif cmd == "upgrade":
        print(f"\n🚀 Upgrading database to revision: {revision}\n")

        # Ensure pgvector extension first
        ensure_pgvector_extension()

        if run_migrations("upgrade", revision):
            print("\n✅ Upgrade complete")

            # Show current status
            status = check_migrations()
            print(f"Current revision: {status.get('current')}")
            return 0
        else:
            print("\n❌ Upgrade failed")
            return 1

    elif cmd == "downgrade":
        print(f"\n⬇️  Downgrading database to revision: {revision}\n")

        if run_migrations("downgrade", revision):
            print("\n✅ Downgrade complete")

            status = check_migrations()
            print(f"Current revision: {status.get('current')}")
            return 0
        else:
            print("\n❌ Downgrade failed")
            return 1

    elif cmd == "current":
        run_migrations("current")
        return 0

    elif cmd == "history":
        print("\n📜 Migration History\n")
        run_migrations("history")
        return 0

    elif cmd == "revision":
        if not message:
            print("Error: --message/-m is required for 'revision' command")
            print("Example: neut db migrate revision -m 'add user table'")
            return 1

        print(f"\n📝 Creating new migration: {message}\n")

        if run_migrations("revision", message=message, autogenerate=autogenerate):
            print("\n✅ Migration created")
            if autogenerate:
                print("   Review the generated migration before applying.")
            return 0
        else:
            print("\n❌ Failed to create migration")
            return 1

    else:
        _print_migrate_help()
        return 0


def _print_migrate_help():
    """Print migration subcommand help."""
    print("Usage: neut db migrate <command> [revision]")
    print()
    print("Commands:")
    print("  check       Check migration status (default)")
    print("  upgrade     Apply pending migrations (default: head)")
    print("  downgrade   Revert migrations (specify revision)")
    print("  current     Show current database revision")
    print("  history     Show migration history")
    print("  revision    Create new migration (-m message required)")
    print()
    print("Examples:")
    print("  neut db migrate check")
    print("  neut db migrate upgrade head")
    print("  neut db migrate downgrade -1")
    print("  neut db migrate revision -m 'add user preferences' --autogenerate")


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Full database setup from scratch."""
    from neutron_os.extensions.builtins.sense_agent.bootstrap import Bootstrap, BootstrapConfig, BootstrapStep

    config = BootstrapConfig(
        non_interactive=args.non_interactive,
        verbose=args.verbose,
    )

    bootstrap = Bootstrap(config)

    if args.check:
        results = bootstrap.check_only()
    elif args.step:
        # Parse step name to enum
        try:
            step = BootstrapStep[args.step.upper()]
            results = bootstrap.run(steps=[step])
        except KeyError:
            print(f"Unknown step: {args.step}")
            print(f"Valid steps: {', '.join(s.name.lower() for s in BootstrapStep)}")
            return 1
    else:
        results = bootstrap.run()

    # Print summary
    print("\n" + "=" * 50)
    print("Bootstrap Summary:")
    for result in results:
        print(f"  {result}")

    all_success = all(r.success for r in results)
    return 0 if all_success else 1


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for db CLI."""
    parser = argparse.ArgumentParser(
        prog="neut db",
        description="PostgreSQL + pgvector infrastructure for NeutronOS",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # up
    subparsers.add_parser(
        "up",
        help="Start local K3D cluster with PostgreSQL + pgvector",
    )

    # down
    subparsers.add_parser(
        "down",
        help="Stop local K3D cluster (preserves data)",
    )

    # delete
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete local K3D cluster and all data",
    )
    delete_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion (required)",
    )

    # status
    subparsers.add_parser(
        "status",
        help="Show cluster and database status",
    )

    # migrate
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Run Alembic database schema migrations",
    )
    migrate_parser.add_argument(
        "migrate_command",
        nargs="?",
        choices=["upgrade", "downgrade", "current", "history", "revision", "check"],
        default="check",
        help="Migration command (default: check)",
    )
    migrate_parser.add_argument(
        "revision",
        nargs="?",
        default="head",
        help="Target revision (default: head)",
    )
    migrate_parser.add_argument(
        "-m", "--message",
        help="Message for new revision (required for 'revision' command)",
    )
    migrate_parser.add_argument(
        "--autogenerate",
        action="store_true",
        help="Auto-detect model changes for 'revision' command",
    )

    # bootstrap
    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Full database setup from scratch",
    )
    bootstrap_parser.add_argument(
        "--check",
        action="store_true",
        help="Check prerequisites without making changes",
    )
    bootstrap_parser.add_argument(
        "--step",
        help="Run only a specific step (prerequisites, k3d, postgres, pgvector, migrate, verify)",
    )
    bootstrap_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Don't prompt for confirmation",
    )
    bootstrap_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for neut db CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        # Show help with quick start
        parser.print_help()
        print("\nQuick Start:")
        print("  neut db up              # Start local PostgreSQL (K3D)")
        print("  neut db migrate upgrade # Apply schema migrations")
        print("  neut db status          # Verify everything works")
        print()
        print("Full setup:")
        print("  neut db bootstrap       # Complete setup from scratch")
        return 0

    commands = {
        "up": cmd_up,
        "down": cmd_down,
        "delete": cmd_delete,
        "status": cmd_status,
        "migrate": cmd_migrate,
        "bootstrap": cmd_bootstrap,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
