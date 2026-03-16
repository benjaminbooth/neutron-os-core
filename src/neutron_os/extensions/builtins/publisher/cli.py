"""CLI handler for `neut doc` / `neut docflow` — document lifecycle management.

Subcommands:
    neut pub publish <file>              Generate + publish to configured storage
    neut pub publish --draft <file>      Draft with review period
    neut pub publish --all --changed-only Batch publish changed docs
    neut pub review [file]               Interactive human-in-the-loop review
    neut pub review --quick              Fast one-shot approve/reject
    neut pub review --status             Show active review sessions
    neut pub generate <file>             Generate locally only (no upload)
    neut pub pull [<doc_id>]             Pull external doc → update local .md
    neut pub pull --all                  Pull all tracked docs from external storage
    neut pub status                      Show all doc states
    neut pub status <file>               Single doc status
    neut pub check-links                 Verify cross-doc links resolve
    neut pub diff                        Show docs changed since last publish
    neut pub providers                   List available providers
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional


def cmd_publish(args: argparse.Namespace) -> None:
    """Publish document(s) to configured storage."""
    from .engine import PublisherEngine

    engine = PublisherEngine()
    force = getattr(args, 'force', False)

    if args.all:
        # Batch publish
        if args.changed_only:
            changed = engine.diff()
            if not changed:
                print("✓ No documents changed since last publish.")
                return
            print(f"\n📝 Found {len(changed)} changed document(s):\n")
            for doc in changed:
                print(f"  • {doc}")
            print()
            for doc in changed:
                source = engine.config.repo_root / doc
                if source.exists():
                    engine.publish(
                        source,
                        storage_override=args.storage,
                        draft=args.draft,
                        force=force,
                    )
        else:
            print("Use --changed-only with --all to avoid publishing everything.")
            sys.exit(1)
    elif args.file:
        source = Path(args.file).resolve()
        if not source.exists():
            print(f"✗ File not found: {args.file}")
            sys.exit(1)
        result = engine.publish(
            source,
            storage_override=args.storage,
            draft=args.draft,
            force=force,
        )

        # Show publication details if available
        if result and isinstance(result, dict):
            print("\n" + "=" * 70)
            print("✓ Document Published Successfully")
            print("=" * 70)
            if result.get('version'):
                print(f"Version:  {result['version']}")
            if result.get('storage'):
                print(f"Storage:  {result['storage']}")
            if result.get('url'):
                print(f"URL:      {result['url']}")
            if result.get('git_footer'):
                print(f"Git URL:  {result['git_footer']}")
            print("=" * 70 + "\n")
    else:
        print("Specify a file or use --all --changed-only")
        sys.exit(1)


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate artifact locally without uploading."""
    from .engine import PublisherEngine

    source = Path(args.file).resolve()
    if not source.exists():
        print(f"File not found: {args.file}")
        sys.exit(1)

    engine = PublisherEngine()
    output = engine.generate(source)
    print(f"\nGenerated: {output}")


def _format_time_ago(iso_timestamp: str) -> str:
    """Convert ISO timestamp to human-readable 'time ago' format."""
    from datetime import datetime, timezone

    try:
        pub_time = datetime.fromisoformat(iso_timestamp)
        now = datetime.now(timezone.utc)
        delta = now - pub_time

        days = delta.days
        hours = delta.seconds // 3600

        if days > 365:
            years = days // 365
            return f"{years}y ago"
        elif days > 30:
            months = days // 30
            return f"{months}mo ago"
        elif days > 0:
            return f"{days}d ago"
        elif hours > 0:
            return f"{hours}h ago"
        else:
            minutes = delta.seconds // 60
            return f"{minutes}m ago" if minutes > 0 else "just now"
    except Exception:
        return iso_timestamp[:10]


def cmd_status(args: argparse.Namespace) -> None:
    """Show document status with detailed information."""
    from .engine import PublisherEngine

    engine = PublisherEngine()

    # Load manifests to check for SharePoint URLs
    manifests = engine.load_manifests([
        engine.config.repo_root / "docs" / "prd",
        engine.config.repo_root / "docs" / "specs",
    ])

    if args.file:
        source = Path(args.file).resolve()
        docs = engine.status(source)
    else:
        docs = engine.status()

    if not docs:
        print("No tracked documents.")
        return

    # Detailed view
    for i, doc in enumerate(docs):
        print(f"\n{'─' * 80}")
        print(f"📄 {doc.doc_id}")
        print(f"{'─' * 80}")

        # Status badge
        status_icon = "✓" if doc.status == "published" else "○" if doc.status == "draft" else "?"
        print(f"  Status:    {status_icon} {doc.status.upper()}")

        # Source file
        source_path = engine.config.repo_root / doc.source_path
        file_exists = source_path.exists()
        file_icon = "✓" if file_exists else "✗"
        print(f"  Source:    {file_icon} {doc.source_path}")

        # Published version
        if doc.published:
            print(f"  Published: v{doc.published.version}")
            time_ago = _format_time_ago(doc.published.published_at)
            print(f"    • Version: {doc.published.version}")
            print(f"    • Published: {doc.published.published_at[:10]} ({time_ago})")
            print(f"    • Provider: {doc.published.storage_provider}")
            print(f"    • URL: {doc.published.url}")

        # Draft version
        if doc.active_draft:
            time_ago = _format_time_ago(doc.active_draft.published_at)
            print(f"  Draft:     v{doc.active_draft.version}")
            print(f"    • Version: {doc.active_draft.version}")
            print(f"    • Published: {doc.active_draft.published_at[:10]} ({time_ago})")

        # Manifest status
        in_manifest = doc.doc_id in manifests
        manifest_icon = "✓" if in_manifest else "○"
        if in_manifest:
            manifest_entry = manifests[doc.doc_id]
            sharepoint_url = manifest_entry.get("published_url")
            sharepoint_icon = "✓" if sharepoint_url else "✗"
            print(f"  Manifest:  {manifest_icon} In manifest")
            if sharepoint_url:
                print(f"  SharePoint: {sharepoint_icon} Configured")
            else:
                print(f"  SharePoint: {sharepoint_icon} NOT configured")
        else:
            print(f"  Manifest:  {manifest_icon} Not in manifest (orphaned in registry)")

        # Git info
        if doc.published and doc.published.commit_sha:
            commit = doc.published.commit_sha[:8]
            print(f"  Git:       • Commit: {commit}")
            if doc.published.generation_provider:
                print("             • Footer: Included (git source URL, version, date)")

    print(f"\n{'─' * 80}")
    print(f"Total: {len(docs)} document(s)")
    in_manifest_count = sum(1 for d in docs if d.doc_id in manifests)
    print(f"In manifest: {in_manifest_count}/{len(docs)}")
    print(f"{'─' * 80}\n")


def cmd_check_links(args: argparse.Namespace) -> None:
    """Verify cross-document links."""
    from .engine import PublisherEngine

    engine = PublisherEngine()
    results = engine.check_links()

    valid = results.get("valid", [])
    missing = results.get("missing", [])

    print("\n" + "=" * 80)
    print("Cross-Document Link Verification")
    print("=" * 80)

    if not valid and not missing:
        print("\nℹ No documents in registry. Publish some documents first.")
        print("  Run: neut pub publish <file>")
        print("=" * 80 + "\n")
        return

    if valid:
        print(f"\n✓ Valid Links ({len(valid)}):")
        print("─" * 80)
        for path in sorted(valid):
            doc_id = Path(path).stem
            print(f"  ✓ {doc_id:<40} {path}")

    if missing:
        print(f"\n✗ Missing Source Files ({len(missing)}):")
        print("─" * 80)
        for path in sorted(missing):
            doc_id = Path(path).stem
            print(f"  ✗ {doc_id:<40} {path}")
        print("\n⚠ These documents are in the registry but source files not found.")
        print("  Either restore the files or remove from registry.")

    total = len(valid) + len(missing)
    if total > 0:
        pct = (len(valid) / total) * 100 if total > 0 else 0
        print(f"\n{'─' * 80}")
        print(f"Link Health: {len(valid)}/{total} ({pct:.0f}%)")
        if pct == 100:
            print("✓ All links are valid!")
        elif pct >= 80:
            print("⚠ Most links are valid, but some sources are missing.")
        else:
            print("✗ Many links are broken. Run 'neut pub scan' for details.")

    print("=" * 80 + "\n")


def cmd_diff(args: argparse.Namespace) -> None:
    """Show documents changed since last publish."""
    from .engine import PublisherEngine

    engine = PublisherEngine()
    changed = engine.diff()

    print("\n" + "=" * 80)
    print("Changed Documents Since Last Publish")
    print("=" * 80)

    if not changed:
        print("\n✓ No documents changed since last publish.")
        print("\n  To publish changed docs: neut pub publish --all --changed-only")
    else:
        print(f"\n⚠ {len(changed)} file(s) changed:")
        print("─" * 80)
        for doc in sorted(changed):
            doc_id = Path(doc).stem
            print(f"  • {doc_id:<40} {doc}")

        print("\n" + "─" * 80)
        print("To publish these changes:")
        print("  neut pub publish --all --changed-only")

    print("=" * 80 + "\n")


def cmd_pull(args: argparse.Namespace) -> None:
    """Pull document(s) from external storage → update local .md files.

    This is the reverse of `publish`:
    - Fetches the latest version from O365/OneDrive
    - Extracts text, comments, tracked changes
    - Updates the local .md file (or shows diff if --dry-run)
    """
    from .engine import PublisherEngine

    engine = PublisherEngine()

    if args.all:
        # Pull all tracked documents
        docs = engine.status()
        tracked = [d for d in docs if d.published and d.published.storage_id]
        if not tracked:
            print("No documents with external storage tracking.")
            return

        print(f"Pulling {len(tracked)} document(s) from external storage...\n")
        for doc in tracked:
            print(f"  {doc.doc_id}...")
            try:
                result = engine.pull(
                    doc.doc_id,
                    dry_run=args.dry_run,
                    include_comments=args.comments,
                )
                if result.get("changed"):
                    if args.dry_run:
                        print("    → Would update (diff available)")
                    else:
                        print(f"    → Updated {result.get('source_path')}")
                else:
                    print("    → No changes")
            except Exception as e:
                print(f"    ✗ Error: {e}")
    elif args.doc_id:
        # Pull specific document
        result = engine.pull(
            args.doc_id,
            dry_run=args.dry_run,
            include_comments=args.comments,
        )
        if args.dry_run:
            if result.get("diff"):
                print("Changes detected:\n")
                print(result["diff"])
            else:
                print("No changes detected.")
        else:
            if result.get("changed"):
                print(f"Updated: {result.get('source_path')}")
                if result.get("comments"):
                    print(f"  {len(result['comments'])} comment(s) extracted")
            else:
                print("No changes detected.")
    else:
        print("Specify a doc_id or use --all")
        sys.exit(1)


def cmd_providers(args: argparse.Namespace) -> None:
    """List all available providers with descriptions."""
    # Ensure providers are registered
    try:
        import neutron_os.extensions.builtins.publisher.providers  # noqa: F401
    except ImportError:
        pass

    from .factory import PublisherFactory
    from .config import load_config

    config = load_config()
    all_providers = PublisherFactory.available()

    print("\n" + "=" * 80)
    print("Publisher Providers")
    print("=" * 80)

    category_info = {
        "generation": {
            "label": "Generation (Markdown → Artifact)",
            "description": "Converts .md source files to publishable formats (DOCX, PDF, etc.)",
        },
        "storage": {
            "label": "Storage (Upload & URLs)",
            "description": "Manages artifact storage and provides canonical URLs",
        },
        "feedback": {
            "label": "Feedback (Reviewer Comments)",
            "description": "Extracts and tracks reviewer feedback from published artifacts",
        },
        "notification": {
            "label": "Notifications (Alerts)",
            "description": "Sends notifications when documents are published",
        },
        "embedding": {
            "label": "Embedding (RAG Indexing)",
            "description": "Indexes documents for semantic search and RAG applications",
        },
    }

    active_map = {
        "generation": config.generation.provider,
        "storage": config.storage.provider,
        "feedback": config.feedback.provider,
        "notification": config.notification.provider,
        "embedding": config.embedding.provider if config.embedding_enabled else None,
    }

    for category, names in all_providers.items():
        info = category_info.get(category, {})
        label = info.get("label", category)
        desc = info.get("description", "")
        active = active_map.get(category, "")

        print(f"\n{label}")
        if desc:
            print(f"  {desc}")
        print("─" * 78)

        if names:
            for name in sorted(names):
                marker = " ★" if name == active else ""
                print(f"  {name:<30}{marker}")
        else:
            print("  (no providers registered)")

    print("\n" + "─" * 80)
    print("★ = currently active (from .publisher.yaml)")
    print("=" * 80 + "\n")


def cmd_scan(args: argparse.Namespace) -> None:
    """Scan folders for markdown files and compare against manifests."""
    from .engine import PublisherEngine

    engine = PublisherEngine()

    # Default to docs/requirements and docs/specs if no folders specified
    if args.folders:
        folders = [Path(f).resolve() for f in args.folders]
    else:
        repo = engine.config.repo_root
        folders = [
            repo / "docs" / "prd",
            repo / "docs" / "specs",
        ]

    results = engine.scan_docs(folders)
    manifests = engine.load_manifests(folders)

    print("\n" + "=" * 80)
    print("Document Manifest Scan")
    print("=" * 80)

    tracked = results.get("tracked", [])
    untracked = results.get("untracked", [])
    orphaned = results.get("orphaned", [])

    # Tracked documents with SharePoint status
    if tracked:
        print(f"\n✓ Tracked in Manifest ({len(tracked)}):")
        print("─" * 80)

        # Group by manifest
        by_manifest = {}
        for doc_id in sorted(tracked):
            if doc_id in manifests:
                manifest_path = manifests[doc_id]["manifest_path"]
                manifest_name = manifest_path.parent.name
                if manifest_name not in by_manifest:
                    by_manifest[manifest_name] = []
                by_manifest[manifest_name].append((doc_id, manifests[doc_id]))

        for manifest_name in sorted(by_manifest.keys()):
            print(f"\n  📁 {manifest_name}/")
            for doc_id, entry in by_manifest[manifest_name]:
                has_url = entry.get("published_url") is not None
                url_icon = "🔗" if has_url else "○"
                url_status = "SharePoint configured" if has_url else "No SharePoint URL"
                print(f"    {url_icon} {doc_id:<40} [{url_status}]")

    # Untracked files
    if untracked:
        print(f"\n⚠ Untracked Files ({len(untracked)}):")
        print("─" * 80)
        for filename in sorted(untracked):
            print(f"  • {filename}")
        print("\n  To add: neut pub onboard <doc_id> <filename> --folder <path>")

    # Orphaned entries
    if orphaned:
        print(f"\n✗ Orphaned Manifest Entries ({len(orphaned)}):")
        print("─" * 80)
        for doc_id in sorted(orphaned):
            if doc_id in manifests:
                source_path = manifests[doc_id]["source_path"]
                print(f"  • {doc_id} (expected: {source_path})")
        print("\n  These are tracked in manifests but files don't exist on disk.")
        print("  Either: 1) Restore the file, or 2) Remove from manifest")

    # Summary
    print(f"\n{'─' * 80}")
    total_docs = len(tracked) + len(untracked)
    total_configured = sum(
        1 for doc_id in tracked
        if doc_id in manifests and manifests[doc_id].get("published_url")
    )
    print("Summary:")
    print(f"  Total documents found: {total_docs}")
    print(f"  In manifest: {len(tracked)}")
    print(f"  With SharePoint URL: {total_configured}/{len(tracked)}")

    if not untracked and not orphaned:
        print("\n  ✓ All documents tracked and accounted for!")

    print("=" * 80 + "\n")


def cmd_onboard(args: argparse.Namespace) -> None:
    """Add a document to a manifest."""
    from .engine import PublisherEngine

    if not args.doc_id or not args.file:
        print("Usage: neut pub onboard <doc_id> <file> [--folder <path>] [--url <sharepoint_url>]")
        sys.exit(1)

    engine = PublisherEngine()

    # Determine manifest folder
    if args.folder:
        manifest_dir = Path(args.folder).resolve()
    else:
        # Infer from file path or default to docs/requirements
        file_path = Path(args.file).resolve()
        if "specs" in str(file_path):
            manifest_dir = engine.config.repo_root / "docs" / "specs"
        else:
            manifest_dir = engine.config.repo_root / "docs" / "requirements"

    manifest_path = manifest_dir / ".publisher.json"
    source_path = Path(args.file)

    # Verify source file exists
    if not source_path.exists():
        source_path = manifest_dir / args.file
        if not source_path.exists():
            print(f"✗ File not found: {args.file}")
            sys.exit(1)

    success = engine.onboard_doc(
        doc_id=args.doc_id,
        source_path=source_path,
        manifest_path=manifest_path,
        published_url=args.url or None,
    )

    if success:
        print("\n" + "=" * 70)
        print("✓ Document Onboarded Successfully")
        print("=" * 70)
        print(f"Manifest:  {manifest_path.relative_to(engine.config.repo_root)}")
        print(f"Doc ID:    {args.doc_id}")
        print(f"Source:    {source_path.relative_to(engine.config.repo_root)}")
        if args.url:
            print(f"Published: {args.url}")
        else:
            print("Published: (not set)")
            print("\n💡 Tip: Set SharePoint URL with: neut pub onboard <id> <file> --url <url>")
        print("=" * 70 + "\n")
    else:
        print("✗ Failed to onboard document")
        sys.exit(1)


def cmd_review(args: argparse.Namespace) -> None:
    """Interactive human-in-the-loop review of a draft document."""
    from neutron_os.review.models import ReviewSessionStore
    from neutron_os.review.runner import ReviewRunner
    from neutron_os.review.adapters.draft_adapter import (
        DraftReviewAdapter,
        create_draft_session,
        find_draft,
    )

    store = ReviewSessionStore()

    # --status: show active review sessions without entering review
    if getattr(args, "review_status", False):
        sessions = store.list_active()
        if not sessions:
            print("No active review sessions.")
            return
        print(f"\nActive review sessions: {len(sessions)}\n")
        for s in sessions:
            reviewed, total = s.progress
            print(f"  {s.session_id}")
            print(f"    Source:   {s.source}")
            print(f"    Progress: {reviewed}/{total} reviewed")
            print()
        return

    # Find the draft to review
    file_arg = getattr(args, "file", None)
    draft_path = find_draft(file_arg=file_arg)
    if not draft_path:
        if file_arg:
            print(f"Draft not found: {file_arg}")
        else:
            print("No draft files found in tools/agents/drafts/")
            print("Generate one with: neut signal draft")
        sys.exit(1)

    print(f"File: {draft_path.name}")

    # --chat: hand off to conversational review in neut chat
    if getattr(args, "chat", False):
        from neutron_os.extensions.builtins.chat_agent.entry import enter_chat

        content = draft_path.read_text(encoding="utf-8")
        enter_chat(
            context_markdown=(
                f"# Review: {draft_path.name}\n\n"
                f"The user wants to review this draft conversationally.\n"
                f"Use the review_start, review_get_item, review_decide, "
                f"review_progress, and review_complete tools to drive the review.\n\n"
                f"---\n\n{content}"
            ),
            title=f"Review: {draft_path.stem}",
            suggestions=[
                "Let's review this draft",
                "Show me the first section",
                "Accept everything and finalize",
            ],
            source="neut_doc_review",
        )
        return

    fresh = getattr(args, "fresh", False)
    quick = getattr(args, "quick", False)
    session = create_draft_session(draft_path, store, fresh=fresh)

    adapter = DraftReviewAdapter()
    runner = ReviewRunner(adapter, store)
    runner.run(session, quick=quick)


def cmd_overview(args: argparse.Namespace) -> None:
    """Show dashboard overview of document ecosystem."""
    from .engine import PublisherEngine

    engine = PublisherEngine()

    # Load all manifests
    manifests = engine.load_manifests([
        engine.config.repo_root / "docs" / "prd",
        engine.config.repo_root / "docs" / "specs",
    ])

    # Scan documents
    prd_docs = engine.scan_docs([engine.config.repo_root / "docs" / "prd"])
    spec_docs = engine.scan_docs([engine.config.repo_root / "docs" / "specs"])

    total_tracked = len(prd_docs.get("tracked", [])) + len(spec_docs.get("tracked", []))
    total_untracked = len(prd_docs.get("untracked", [])) + len(spec_docs.get("untracked", []))

    # Count documents with published URLs
    with_urls = 0
    without_urls = 0
    for doc_id, entry in manifests.items():
        if entry.get("published_url"):
            with_urls += 1
        else:
            without_urls += 1

    # Check link health
    links = engine.check_links()
    valid_links = len(links.get("valid", []))
    broken_links = len(links.get("missing", []))

    print("\n" + "=" * 80)
    print("📊 Publisher Ecosystem Overview")
    print("=" * 80)

    print("\n📋 DOCUMENTS")
    print("─" * 80)
    print(f"  Total Tracked:           {total_tracked}")
    print(f"  Untracked Files:         {total_untracked}")
    print(f"  With SharePoint URLs:    {with_urls}")
    print(f"  Awaiting Configuration:  {without_urls}")

    print("\n🔗 LINKS")
    print("─" * 80)
    print(f"  Valid Links:             {valid_links}")
    print(f"  Broken/Missing:          {broken_links}")
    if valid_links + broken_links > 0:
        health_pct = (valid_links / (valid_links + broken_links)) * 100
        status = "✓ Healthy" if health_pct >= 95 else "⚠ Needs attention" if health_pct >= 80 else "✗ Critical"
        print(f"  Health:                  {health_pct:.0f}% {status}")

    print("\n📁 BY FOLDER")
    print("─" * 80)
    print("  PRDs:")
    print(f"    • Tracked:    {len(prd_docs.get('tracked', []))}")
    print(f"    • Untracked:  {len(prd_docs.get('untracked', []))}")

    print("  Specs:")
    print(f"    • Tracked:    {len(spec_docs.get('tracked', []))}")
    print(f"    • Untracked:  {len(spec_docs.get('untracked', []))}")

    print("\n💡 NEXT STEPS")
    print("─" * 80)
    if total_untracked > 0:
        print(f"  • {total_untracked} untracked documents — run 'neut pub scan' to see them")
    if without_urls > 0:
        print(f"  • {without_urls} documents missing SharePoint URLs — run 'neut pub onboard' to configure")
    if broken_links > 0:
        print(f"  • {broken_links} broken links — run 'neut pub check-links' to diagnose")
    if not total_untracked and not without_urls and not broken_links:
        print("  ✓ Everything configured and healthy! Ready to publish.")

    print("=" * 80 + "\n")


# ---------------------------------------------------------------------------
# Command Registry (auto-synced to chat slash commands)
# ---------------------------------------------------------------------------

COMMANDS: dict[str, str] = {
    "overview": "Dashboard of document ecosystem",
    "publish": "Generate + publish to storage",
    "generate": "Generate locally only",
    "review": "Interactive human-in-the-loop review",
    "pull": "Pull external doc → update .md",
    "status": "Show document status",
    "check-links": "Verify cross-doc links",
    "diff": "Show changed docs since last publish",
    "scan": "Scan folders for docs vs manifests",
    "onboard": "Add document to manifest",
    "providers": "List available providers",
}


def get_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser.

    Exposed for CLI registry introspection. Commands auto-sync to chat.
    """
    parser = argparse.ArgumentParser(
        prog="neut pub",
        description="Document lifecycle management",
    )

    subparsers = parser.add_subparsers(dest="command")

    # overview
    subparsers.add_parser("overview", help="Dashboard of document ecosystem")

    # publish
    pub_parser = subparsers.add_parser("publish", help="Generate + publish to storage")
    pub_parser.add_argument("file", nargs="?", help="Markdown file to publish")
    pub_parser.add_argument("--draft", action="store_true", help="Publish as draft")
    pub_parser.add_argument("--all", action="store_true", help="Batch publish")
    pub_parser.add_argument("--changed-only", action="store_true", help="Only changed docs")
    pub_parser.add_argument("--storage", help="Override storage provider (e.g., 'local')")
    pub_parser.add_argument("--force", action="store_true", help="Force publish even if no changes detected")

    # review
    rev_parser = subparsers.add_parser("review", help="Interactive human-in-the-loop review")
    rev_parser.add_argument("file", nargs="?", help="Draft file to review (default: most recent)")
    rev_parser.add_argument("--fresh", action="store_true", help="Start over, discard previous progress")
    rev_parser.add_argument("--quick", action="store_true", help="Fast one-shot review (approve/reject all)")
    rev_parser.add_argument("--status", action="store_true", dest="review_status", help="Show active review sessions")
    rev_parser.add_argument("--chat", action="store_true", help="Review conversationally via neut chat")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate locally only")
    gen_parser.add_argument("file", help="Markdown file to generate")

    # pull
    pull_parser = subparsers.add_parser("pull", help="Pull external doc → update .md")
    pull_parser.add_argument("doc_id", nargs="?", help="Document ID to pull")
    pull_parser.add_argument("--all", action="store_true", help="Pull all tracked docs")
    pull_parser.add_argument("--dry-run", action="store_true", help="Show diff without updating")
    pull_parser.add_argument("--comments", action="store_true", help="Include comments in output")

    # status
    stat_parser = subparsers.add_parser("status", help="Show document status")
    stat_parser.add_argument("file", nargs="?", help="Specific file (optional)")

    # check-links
    subparsers.add_parser("check-links", help="Verify cross-doc links")

    # diff
    subparsers.add_parser("diff", help="Show changed docs since last publish")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan folders for docs vs manifests")
    scan_parser.add_argument("folders", nargs="*", help="Folders to scan (default: docs/requirements docs/specs)")

    # onboard
    onboard_parser = subparsers.add_parser("onboard", help="Add document to manifest")
    onboard_parser.add_argument("doc_id", help="Document identifier")
    onboard_parser.add_argument("file", help="Path to .md file")
    onboard_parser.add_argument("--folder", help="Manifest folder (default: inferred from file)")
    onboard_parser.add_argument("--url", help="SharePoint URL (optional)")

    # providers
    subparsers.add_parser("providers", help="List available providers")

    # push — primary happy-path command (auto-detects .compile.yaml)
    push_parser = subparsers.add_parser(
        "push", help="Push document to storage (auto-assembles multi-section if .compile.yaml found)"
    )
    push_parser.add_argument("path", nargs="?", help="File or directory to push")
    push_parser.add_argument("--all", action="store_true", help="Push all .md files in configured folders")
    push_parser.add_argument("--draft", action="store_true", help="Publish as draft")
    push_parser.add_argument("--storage", help="Override storage provider (e.g. 'local', 'onedrive-browser')")
    push_parser.add_argument("--headed", action="store_true", help="Show browser window (for first-time login)")
    push_parser.add_argument("--force", action="store_true", help="Force re-publish even if unchanged")

    # assemble — plumbing for multi-section compilation
    asm_parser = subparsers.add_parser(
        "assemble", help="Assemble a multi-section doc from .compile.yaml (plumbing)"
    )
    asm_parser.add_argument("manifest", help="Path to .compile.yaml")
    asm_parser.add_argument("--output", "-o", help="Output file path (default: <output>.assembled.md)")

    return parser


def _find_compile_manifest(path: Path) -> Optional[Path]:
    """Search *path* and its parents for a .compile.yaml manifest.

    Checks:
    1. If *path* is a directory, look for .compile.yaml inside it
    2. If *path* is a file, look for .compile.yaml in the same directory
    3. Walk up to repo root (where .git lives) stopping at each level
    """
    candidates = []
    if path.is_dir():
        candidates.append(path / ".compile.yaml")
    candidates.append(path.parent / ".compile.yaml")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _assemble_from_manifest(manifest_path: Path, output_path: Optional[Path] = None) -> Path:
    """Concatenate source files from a .compile.yaml manifest into a single .md.

    Returns the path to the assembled file.
    """
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        # .compile.yaml is YAML, not TOML
        import yaml as _yaml  # type: ignore[import]
        with open(manifest_path) as f:
            manifest = _yaml.safe_load(f)
    except ImportError:
        # Fall back to basic key:value parsing for simple manifests
        manifest = {}
        with open(manifest_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and ":" in line:
                    k, _, v = line.partition(":")
                    manifest[k.strip()] = v.strip().strip('"')

    sources = manifest.get("sources", [])
    title = manifest.get("title", "")
    doc_dir = manifest_path.parent

    if not sources:
        raise ValueError(f"No sources listed in {manifest_path}")

    # Assemble
    parts = []
    if title:
        parts.append(f"# {title}\n\n")
    for src in sources:
        src_path = doc_dir / src
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")
        parts.append(src_path.read_text(encoding="utf-8"))
        if not parts[-1].endswith("\n"):
            parts.append("\n")
        parts.append("\n")

    assembled = "".join(parts)

    if output_path is None:
        output_name = manifest.get("output", "assembled")
        output_path = doc_dir / f"{output_name}.assembled.md"

    output_path.write_text(assembled, encoding="utf-8")
    return output_path


def cmd_assemble(args: argparse.Namespace) -> None:
    """Assemble a multi-section document from a .compile.yaml manifest.

    This is the plumbing command. For the happy path, use `neut pub push`
    which detects and runs assembly automatically.
    """
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"✗ Manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output).resolve() if args.output else None

    try:
        result = _assemble_from_manifest(manifest_path, output_path)
        print(f"✓ Assembled → {result}")
    except (FileNotFoundError, ValueError) as exc:
        print(f"✗ Assembly failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_push(args: argparse.Namespace) -> None:
    """Push a document (or batch) to configured storage.

    Two modes:
    - Single/directory: generates + publishes via engine (supports .compile.yaml assembly)
    - --all + --storage onedrive-browser: batch generate + upload via Playwright

    First run with --headed opens a browser for Microsoft login.
    """
    from .engine import PublisherEngine
    import tempfile

    engine = PublisherEngine()
    force = getattr(args, "force", False)
    draft = getattr(args, "draft", False)
    storage = getattr(args, "storage", None)
    headed = getattr(args, "headed", False)
    push_all = getattr(args, "all", False)

    # ── Batch browser upload (--all --storage onedrive-browser) ───────────
    if push_all or storage == "onedrive-browser":
        _cmd_push_batch(args, engine, draft, storage, headed, force)
        return

    # ── Single file / directory push (original behavior) ──────────────────
    if not args.path:
        print("Usage: neut pub push <path> [--all] [--storage onedrive-browser] [--headed]")
        print("\nExamples:")
        print("  neut pub push docs/requirements/prd_executive.md")
        print("  neut pub push --all --storage onedrive-browser --headed")
        return

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"✗ Path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    # Auto-detect .compile.yaml for multi-section assembly
    assembled_tmp: Optional[Path] = None
    source = target

    manifest = _find_compile_manifest(target)
    if manifest:
        print(f"  Assembling from {manifest.relative_to(manifest.parent.parent)}...")
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".assembled.md", dir=manifest.parent, delete=False,
            )
            tmp.close()
            assembled_tmp = Path(tmp.name)
            source = _assemble_from_manifest(manifest, assembled_tmp)
            print(f"  Assembly complete ({source.stat().st_size // 1024}KB)")
        except (FileNotFoundError, ValueError) as exc:
            print(f"✗ Assembly failed: {exc}", file=sys.stderr)
            sys.exit(1)

    # Publish via engine
    try:
        result = engine.publish(
            source, storage_override=storage, draft=draft, force=force,
        )
        if result and isinstance(result, dict):
            print("\n" + "=" * 70)
            print("✓ Published successfully")
            print("=" * 70)
            if result.get("version"):
                print(f"Version:  {result['version']}")
            if result.get("storage"):
                print(f"Storage:  {result['storage']}")
            if result.get("url"):
                print(f"URL:      {result['url']}")
            print("=" * 70 + "\n")
    except Exception as e:
        print(f"✗ Publish failed: {e}", file=sys.stderr)
        raise
    finally:
        if assembled_tmp and assembled_tmp.exists():
            assembled_tmp.unlink()


def _cmd_push_batch(args, engine, draft, storage, headed, force):
    """Batch generate + upload via Playwright browser."""
    from neutron_os import REPO_ROOT

    # Collect files from configured folders
    config_path = REPO_ROOT / ".publisher.yaml"
    folders = []
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            folders = cfg.get("folders", [])
        except Exception:
            pass

    if not folders:
        folders = [{"path": "docs/requirements", "pattern": "prd_*.md"}]

    files_to_push: list[tuple[Path, Path]] = []
    for folder_cfg in folders:
        folder = REPO_ROOT / folder_cfg["path"]
        pattern = folder_cfg.get("pattern", "*.md")
        if folder.exists():
            for md_file in sorted(folder.glob(pattern)):
                if md_file.name.startswith("_") or md_file.name == "README.md":
                    continue
                files_to_push.append((md_file, _generate_docx(md_file)))

    if not files_to_push:
        print("No documents found to push.")
        return

    # Generate .docx files
    print(f"\n  Generating {len(files_to_push)} document(s)...\n")
    docx_files: list[Path] = []
    for source_md, docx_path in files_to_push:
        if source_md.suffix == ".md" and not docx_path.exists():
            print(f"    Generating {docx_path.name}...", end=" ", flush=True)
            docx_path = _generate_docx(source_md)
            print("✓")
        else:
            print(f"    {docx_path.name} (already generated)")
        docx_files.append(docx_path)

    # Upload via browser
    try:
        from .providers.storage.onedrive_browser import OneDriveBrowserStorageProvider
    except ImportError:
        print("\n✗ Playwright not installed. Run:")
        print("    pip install playwright && playwright install chromium")
        sys.exit(1)

    onedrive_folder = "NeutronOS/prd"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            onedrive_folder = cfg.get("storage", {}).get("onedrive_folder", "NeutronOS") + "/prd"
        except Exception:
            pass

    provider = OneDriveBrowserStorageProvider({
        "folder": onedrive_folder,
        "headless": not headed,
    })

    if not provider.has_session() and not headed:
        print("\n  No saved session. Run with --headed for first-time login:")
        print("    neut pub push --all --storage onedrive-browser --headed\n")
        sys.exit(1)

    print(f"\n  Uploading {len(docx_files)} file(s) to OneDrive/{onedrive_folder}...\n")

    results = provider.upload_batch(docx_files, draft=draft, headed=headed)
    success = 0
    for docx, result in zip(docx_files, results):
        icon = "✓" if result.success else "✗"
        msg = result.url if result.success else result.error
        print(f"    {icon} {docx.name}  {msg}")
        if result.success:
            success += 1

    print(f"\n  {success}/{len(docx_files)} published successfully.\n")


def _generate_docx(md_path: Path) -> Path:
    """Generate a .docx from a .md file using pandoc. Returns path to .docx."""
    import subprocess

    from neutron_os import REPO_ROOT

    output_dir = REPO_ROOT / ".neut" / "generated" / "prd"
    output_dir.mkdir(parents=True, exist_ok=True)

    docx_name = md_path.stem + ".docx"
    output_path = output_dir / docx_name

    # Get title from first line
    title = md_path.stem.replace("_", " ").replace("-", " ").title()
    try:
        first_line = md_path.read_text(encoding="utf-8").split("\n")[0]
        if first_line.startswith("# "):
            title = first_line[2:].strip()
    except Exception:
        pass

    try:
        subprocess.run(
            [
                "pandoc", str(md_path),
                "-o", str(output_path),
                "--from", "markdown",
                "--to", "docx",
                "--toc", "--toc-depth=3",
                "--metadata", f"title={title}",
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"\n    Warning: pandoc failed for {md_path.name}: {e.stderr.decode()[:200]}")
    except FileNotFoundError:
        print("\n    ✗ pandoc not installed. Run: brew install pandoc")

    return output_path


def main():
    """CLI entry point for neut doc."""
    parser = get_parser()
    args = parser.parse_args()

    if args.command == "overview":
        cmd_overview(args)
    elif args.command == "publish":
        cmd_publish(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "pull":
        cmd_pull(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "check-links":
        cmd_check_links(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "onboard":
        cmd_onboard(args)
    elif args.command == "providers":
        cmd_providers(args)
    elif args.command == "push":
        cmd_push(args)
    elif args.command == "assemble":
        cmd_assemble(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
