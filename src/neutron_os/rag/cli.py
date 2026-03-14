"""CLI entry point for the RAG subsystem.

Usage::

    python -m neutron_os.rag index [path]        # index workspace docs
    python -m neutron_os.rag search "query"      # hybrid search
    python -m neutron_os.rag status              # per-corpus statistics
    python -m neutron_os.rag load-community      # load community corpus dump
    python -m neutron_os.rag sync org            # sync org corpus
    python -m neutron_os.rag reindex             # force re-index all docs

Legacy aliases: ``ingest`` → ``index``, ``stats`` → ``status``
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def _load_env() -> None:
    """Try to load DATABASE_URL from .env or neut settings if not already set."""
    if os.environ.get("DATABASE_URL"):
        return
    # Try .env file
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[4] / ".env"):
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip().strip("\"'")
                    if key and key not in os.environ:
                        os.environ[key] = val
            break
    # Fall back to neut settings
    if not os.environ.get("DATABASE_URL"):
        try:
            from neutron_os.extensions.builtins.settings.store import SettingsStore
            url = SettingsStore().get("rag.database_url", "")
            if url:
                os.environ["DATABASE_URL"] = url
        except Exception:
            pass


def _get_store():
    from .store import RAGStore

    url = os.environ.get("DATABASE_URL")
    if not url:
        print(
            "ERROR: No RAG database configured.\n"
            "  Set via: neut settings set rag.database_url \"postgresql://...\"\n"
            "  Or:      export DATABASE_URL=postgresql://...",
            file=sys.stderr,
        )
        sys.exit(1)
    store = RAGStore(url)
    store.connect()
    return store


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_index(args: argparse.Namespace) -> None:
    """Index one or more paths (or the default repo paths)."""
    from neutron_os import REPO_ROOT
    from .ingest import ingest_file, ingest_repo
    from .store import CORPUS_INTERNAL

    corpus = getattr(args, "corpus", CORPUS_INTERNAL)
    store = _get_store()
    try:
        if args.paths:
            from .ingest import IngestStats, ingest_file
            from .extract import SUPPORTED_EXTENSIONS
            total = IngestStats()
            for raw in args.paths:
                p = Path(raw).resolve()
                if p.is_dir():
                    files = []
                    for ext in SUPPORTED_EXTENSIONS:
                        files.extend(p.rglob(f"*{ext}"))
                    files = [f for f in files if "__MACOSX" not in str(f) and not f.name.startswith(".")]
                    log.info("Found %d files under %s", len(files), p)
                    for fpath in sorted(files):
                        s = ingest_file(fpath, store, repo_root=p, corpus=corpus)
                        total.files_indexed += s.files_indexed
                        total.chunks_created += s.chunks_created
                        total.files_skipped += s.files_skipped
                elif p.is_file():
                    s = ingest_file(p, store, repo_root=p.parent, corpus=corpus)
                    total.files_indexed += s.files_indexed
                    total.chunks_created += s.chunks_created
                    total.files_skipped += s.files_skipped
                else:
                    print(f"WARNING: path not found: {p}", file=sys.stderr)
        else:
            total = ingest_repo(REPO_ROOT, store, corpus=corpus)

        print(
            f"Indexed: {total.files_indexed} files, "
            f"{total.chunks_created} chunks  "
            f"({total.files_skipped} unchanged/skipped)  "
            f"[corpus: {corpus}]"
        )
    finally:
        store.close()


def cmd_search(args: argparse.Namespace) -> None:
    from .embeddings import embed_texts

    store = _get_store()
    try:
        try:
            embs = embed_texts([args.query])
        except Exception as exc:
            log.warning("Embedding skipped (using text-only search): %s", exc)
            embs = None
        results = store.search(
            query_embedding=embs[0] if embs else None,
            query_text=args.query,
            limit=args.limit,
        )
        if not results:
            print("No results.")
            return

        for i, r in enumerate(results, 1):
            print(f"\n--- Result {i} (score: {r.combined_score:.4f}, corpus: {r.corpus}) ---")
            print(f"  Source: {r.source_path} (chunk {r.chunk_index})")
            print(f"  Title:  {r.source_title}")
            print(f"  {r.chunk_text[:300]}...")
    finally:
        store.close()


def cmd_status(args: argparse.Namespace) -> None:
    """Show per-corpus statistics."""
    store = _get_store()
    try:
        s = store.stats()
        print(f"RAG Index Status")
        print(f"  Total documents: {s['total_documents']}")
        print(f"  Total chunks:    {s['total_chunks']}")
        print()
        print(f"  {'Corpus':<20} {'Docs':>6} {'Chunks':>8}")
        print(f"  {'-'*20} {'-'*6} {'-'*8}")
        for corpus in ("rag-community", "rag-org", "rag-internal"):
            docs = s["documents_by_corpus"].get(corpus, 0)
            chunks = s["chunks_by_corpus"].get(corpus, 0)
            label = corpus.replace("rag-", "")
            print(f"  {label:<20} {docs:>6} {chunks:>8}")
    finally:
        store.close()


def cmd_load_community(args: argparse.Namespace) -> None:
    """Load the community corpus from a pre-built dump file."""
    from pathlib import Path

    store = _get_store()
    try:
        # If no path given, look for bundled dump
        if args.dump_path:
            dump = Path(args.dump_path)
        else:
            # Look for bundled community dump
            import importlib.resources as pkg_resources
            try:
                pkg_dir = Path(__file__).resolve().parents[1] / "data" / "rag"
                candidates = sorted(pkg_dir.glob("community-v*.sql")) + sorted(pkg_dir.glob("community-v*.pgdump"))
                if not candidates:
                    print(
                        "No community corpus dump found.\n"
                        "  Expected: src/neutron_os/data/rag/community-v*.sql\n"
                        "  Download: neut update --community-rag",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                dump = candidates[-1]  # latest by name sort
            except Exception as exc:
                print(f"ERROR locating community dump: {exc}", file=sys.stderr)
                sys.exit(1)

        print(f"Loading community corpus from {dump} ...")
        store.load_community_dump(dump)
        s = store.stats()
        chunks = s["chunks_by_corpus"].get("rag-community", 0)
        docs = s["documents_by_corpus"].get("rag-community", 0)
        print(f"Community corpus loaded: {docs} documents, {chunks} chunks")
    finally:
        store.close()


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync org corpus (v1: manual rsync instructions)."""
    target = getattr(args, "target", "org")
    if target == "org":
        print(
            "To sync the org corpus, run:\n"
            "\n"
            "  rsync -avz --progress \\\n"
            "    rascal.tacc.utexas.edu:/shared/neutron-os/rag/org-corpus/ \\\n"
            "    runtime/knowledge/org-corpus/\n"
            "\n"
            "  neut rag index runtime/knowledge/org-corpus/ --corpus rag-org\n"
            "\n"
            "Note: rascal requires UT VPN. Automated sync (neut rag sync org --auto)\n"
            "will be available in v2 once the snapshot pipeline is in place."
        )
    else:
        print(f"Unknown sync target: {target}", file=sys.stderr)
        sys.exit(1)


def cmd_watch(args: argparse.Namespace) -> None:
    """Watch workspace directories and re-index changed files automatically."""
    from neutron_os import REPO_ROOT
    from .store import CORPUS_INTERNAL
    from .watcher import watch

    corpus = getattr(args, "corpus", CORPUS_INTERNAL)
    store = _get_store()
    try:
        watch(REPO_ROOT, store, corpus=corpus, quiet=args.quiet)
    finally:
        store.close()


def cmd_reindex(args: argparse.Namespace) -> None:
    """Force re-index by clearing checksums and re-running index."""
    from neutron_os import REPO_ROOT
    from .ingest import ingest_repo
    from .store import CORPUS_INTERNAL

    corpus = getattr(args, "corpus", CORPUS_INTERNAL)
    store = _get_store()
    try:
        # Clear existing corpus so checksums don't skip anything
        deleted = store.delete_corpus(corpus)
        print(f"Cleared {deleted} chunks from {corpus}")
        stats = ingest_repo(REPO_ROOT, store, corpus=corpus)
        print(
            f"Re-indexed: {stats.files_indexed} files, "
            f"{stats.chunks_created} chunks  [corpus: {corpus}]"
        )
    finally:
        store.close()


# Legacy alias
def cmd_ingest(args: argparse.Namespace) -> None:
    """Legacy alias for cmd_index."""
    if not hasattr(args, "paths"):
        args.paths = []
    cmd_index(args)


# ---------------------------------------------------------------------------
# Main / argument parser
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    _load_env()

    parser = argparse.ArgumentParser(prog="neutron_os.rag", description="RAG subsystem CLI")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # index
    p_index = sub.add_parser("index", help="Index documents into the RAG store")
    p_index.add_argument("paths", nargs="*", help="Paths to index (default: repo docs/)")
    p_index.add_argument("--corpus", default="rag-internal", help="Target corpus (default: rag-internal)")

    # search
    p_search = sub.add_parser("search", help="Search the RAG index")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("-n", "--limit", type=int, default=5, help="Max results")

    # status
    sub.add_parser("status", help="Show per-corpus index statistics")

    # load-community
    p_lc = sub.add_parser("load-community", help="Load pre-built community corpus")
    p_lc.add_argument("dump_path", nargs="?", default=None, help="Path to .sql dump (default: bundled)")

    # sync
    p_sync = sub.add_parser("sync", help="Sync a corpus from remote source")
    p_sync.add_argument("target", choices=["org"], help="Corpus to sync")

    # watch
    p_watch = sub.add_parser("watch", help="Watch workspace dirs and re-index on change")
    p_watch.add_argument("--corpus", default="rag-internal", help="Target corpus")
    p_watch.add_argument("--quiet", action="store_true", help="Suppress startup output")

    # reindex
    p_reindex = sub.add_parser("reindex", help="Force full re-index of a corpus")
    p_reindex.add_argument("--corpus", default="rag-internal", help="Corpus to reindex")

    # Legacy aliases
    p_ingest = sub.add_parser("ingest", help="[legacy] Alias for index")
    p_ingest.add_argument("--corpus", default="rag-internal")
    p_ingest.add_argument("paths", nargs="*")

    p_stats = sub.add_parser("stats", help="[legacy] Alias for status")
    del p_stats  # suppress unused warning

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    dispatch = {
        "index": cmd_index,
        "ingest": cmd_ingest,
        "search": cmd_search,
        "status": cmd_status,
        "stats": cmd_status,
        "load-community": cmd_load_community,
        "sync": cmd_sync,
        "reindex": cmd_reindex,
        "watch": cmd_watch,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
