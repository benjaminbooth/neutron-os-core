# NeutronOS Agent State Management — Technical Specification

**Status:** Draft
**Owner:** Ben Booth
**Created:** 2026-02-24
**Last Updated:** 2026-03-14
**PRD Reference:** [agent-state-management PRD](../requirements/prd-agent-state-management.md)

---

## Overview

This specification defines three infrastructure capabilities for NeutronOS agent state:

1. **Safe concurrent access** — A shared module (`neutron_os.infra.state`) that provides locked, atomic JSON file I/O for any agent or extension.
2. **Hybrid state backend** — A unified `StateBackend` protocol (`neutron_os.infra.state`) that routes to flat files or PostgreSQL with automatic fallback.
3. **Retention enforcement** — M-O integration for configurable, auditable data lifecycle management.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        M-O Agent                                 │
│  ┌───────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Scratch Mgmt  │  │ Retention Sweep  │  │ State Vitals     │  │
│  │ (existing)    │  │ (new)            │  │ (new)            │  │
│  └───────┬───────┘  └────────┬─────────┘  └────────┬─────────┘  │
└──────────┼───────────────────┼──────────────────────┼────────────┘
           │                   │                      │
           ▼                   ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              neutron_os.infra.state                        │
│                                                                  │
│  StateBackend protocol    HybridStateStore                       │
│  get_state_store()        auto-detect backend                    │
│                                                                  │
│  ┌────────────────────┐   ┌────────────────────────────────┐     │
│  │ FileStateBackend   │   │ PgStateBackend                 │     │
│  │ (LockedJsonFile)   │   │ (PgStateStore / ACID)          │     │
│  └────────────────────┘   └────────────────────────────────┘     │
│                                                                  │
│  StateRegistry: STATE_LOCATIONS, RetentionPolicy                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Module Structure

```
src/neutron_os/infra/
├── state.py                # LockedJsonFile, hybrid store, protocols, StateLocation registry
├── state_pg.py             # PostgreSQL backend (PgStateStore)
└── ...

src/neutron_os/extensions/builtins/mo_agent/
├── manager.py              # Add retention sweep to existing sweep cycle
├── manifest.py             # Refactor: import LockedFile from infra.state
├── retention.py            # Retention policy engine (NEW)
├── cli.py                  # Add `neut mo retention` subcommand (EXTEND)
└── ...

runtime/config.example/
├── retention.yaml          # Default retention policies (NEW)
└── ...
```

---

## Safe Concurrent Access Layer

### Design

The core insight: M-O's `manifest.py` already has a working `_LockedFile` implementation. We extract and generalize it into `neutron_os.infra.state` so all agents can use it.

### `LockedJsonFile`

```python
# src/neutron_os/infra/state.py

from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LockedJsonFile:
    """Safe concurrent JSON file access with advisory locking.

    Uses fcntl.flock on Unix for process-level coordination.
    Writes are atomic (tempfile + rename) to prevent corruption on crash.

    Usage:
        # Read-only (shared lock)
        with LockedJsonFile(path) as f:
            data = f.read()

        # Read-modify-write (exclusive lock)
        with LockedJsonFile(path, exclusive=True) as f:
            data = f.read()
            data["key"] = "value"
            f.write(data)
    """

    def __init__(self, path: str | Path, *, exclusive: bool = False, timeout: float = 5.0):
        self._path = Path(path)
        self._exclusive = exclusive
        self._timeout = timeout
        self._fd: int | None = None
        self._data: Any = None

    def __enter__(self) -> LockedJsonFile:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Open or create the file
        flags = os.O_RDWR | os.O_CREAT if self._exclusive else os.O_RDONLY | os.O_CREAT
        self._fd = os.open(str(self._path), flags, 0o644)
        self._acquire_lock()
        return self

    def __exit__(self, *exc) -> bool:
        if self._fd is not None:
            self._release_lock()
            os.close(self._fd)
            self._fd = None
        return False

    def read(self) -> Any:
        """Read and parse JSON content. Returns empty dict if file is empty."""
        if self._fd is None:
            raise RuntimeError("Must be used as context manager")
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return {}
            return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def write(self, data: Any) -> None:
        """Atomically write JSON data (tempfile + rename)."""
        if self._fd is None or not self._exclusive:
            raise RuntimeError("write() requires exclusive=True in context manager")
        # Write to temp file in same directory (ensures same filesystem for rename)
        dir_path = self._path.parent
        fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(self._path))
        except BaseException:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _acquire_lock(self) -> None:
        if sys.platform == "win32" or self._fd is None:
            return
        try:
            import fcntl
            lock_type = fcntl.LOCK_EX if self._exclusive else fcntl.LOCK_SH
            fcntl.flock(self._fd, lock_type)
        except (ImportError, OSError):
            pass

    def _release_lock(self) -> None:
        if sys.platform == "win32" or self._fd is None:
            return
        try:
            import fcntl
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
```

### `atomic_write` Convenience Function

```python
def atomic_write(path: str | Path, data: Any) -> None:
    """Atomically write JSON data to a file with exclusive locking."""
    with LockedJsonFile(path, exclusive=True) as f:
        f.write(data)
```

### Refactoring M-O's Manifest

M-O's `manifest.py` should be refactored to import from `neutron_os.infra.state`:

```python
# Before (manifest.py)
class _LockedFile: ...  # 35 lines of locking logic

# After (manifest.py)
from neutron_os.infra.state import LockedJsonFile

class Manifest:
    def _load(self) -> None:
        with LockedJsonFile(self._path) as f:
            data = f.read()
        # ... parse entries

    def _save(self) -> None:
        with LockedJsonFile(self._path, exclusive=True) as f:
            f.write([e.to_dict() for e in self._entries.values()])
```

### Migration Path for Existing State Files

Files that currently use raw `json.load`/`json.dump`:

| File | Current Access | Migration |
|------|---------------|-----------|
| `.publisher-registry.json` | `json.load(open(...))` | `LockedJsonFile` |
| `.publisher-state.json` | `json.load(open(...))` | `LockedJsonFile` |
| `briefing_state.json` | `json.load(open(...))` | `LockedJsonFile` |
| `review_state.json` | `json.load(open(...))` | `LockedJsonFile` |
| `user_glossary.json` | `json.load(open(...))` | `LockedJsonFile` |
| `propagation_queue.json` | `json.load(open(...))` | `LockedJsonFile` |
| `.mo-manifest.json` | Custom `_LockedFile` | `LockedJsonFile` (already locked) |

Priority: Publisher state files first (most likely to see concurrent access), then signal pipeline state.

---

## Hybrid State Backend

### Protocols

```python
# src/neutron_os/infra/state_hybrid.py

@runtime_checkable
class StateHandle(Protocol):
    """Handle to a single state document within a transaction/lock."""
    def read(self) -> Any: ...
    def write(self, data: Any) -> None: ...

@runtime_checkable
class StateBackend(Protocol):
    """Backend that can open state documents for read/write."""
    @contextmanager
    def open(self, path: str, *, exclusive: bool = False) -> Generator[StateHandle]: ...
    def read(self, path: str) -> Any: ...
    def write(self, path: str, data: Any) -> None: ...
    @property
    def name(self) -> str: ...
```

### Backend Selection

`HybridStateStore` resolves the backend once at initialization:

1. `NEUTRON_STATE_BACKEND=file` → always flat files
2. `NEUTRON_STATE_BACKEND=postgresql` → always PostgreSQL (fails if unavailable)
3. `NEUTRON_STATE_DSN` or `DATABASE_URL` set → try PostgreSQL, fall back to file
4. Nothing set → flat files (default)

### Usage

```python
from neutron_os.infra.state import get_state_store

store = get_state_store()

# Read (backend-agnostic)
data = store.read("runtime/inbox/state/briefing_state.json")

# Read-modify-write (backend-agnostic)
with store.open("runtime/inbox/state/briefing_state.json", exclusive=True) as h:
    data = h.read()
    data["counter"] += 1
    h.write(data)

# Check which backend is active
print(store.backend_name)  # "file" or "postgresql"
```

### PostgreSQL Schema

```sql
CREATE TABLE IF NOT EXISTS agent_state (
    path         TEXT PRIMARY KEY,
    data         JSONB NOT NULL DEFAULT '{}',
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by   TEXT NOT NULL DEFAULT '',
    version      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS state_audit_log (
    id           BIGSERIAL PRIMARY KEY,
    path         TEXT NOT NULL,
    action       TEXT NOT NULL,
    old_version  INTEGER,
    new_version  INTEGER,
    actor        TEXT NOT NULL DEFAULT '',
    timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details      JSONB
);
```

Key features:
- **Optimistic concurrency** — `version` column incremented on write; raises `ConcurrentModificationError` on conflict
- **Row-level locking** — `SELECT ... FOR UPDATE` (exclusive) / `FOR SHARE` (shared)
- **Transactional audit** — audit log entry written in same transaction as state change

---

## State Location Registry

### Declaration

```python
# src/neutron_os/infra/state.py

@dataclass(frozen=True)
class StateLocation:
    """Metadata about a known state storage location."""
    path: str                          # Relative to project root
    category: str                      # runtime | config | documents | corrections | sessions
    description: str
    sensitivity: str                   # low | medium | high | critical
    retention_key: str | None = None   # Key in retention.yaml, or None = indefinite
    glob_pattern: str = "*"            # For scanning directories


STATE_LOCATIONS: list[StateLocation] = [
    # Runtime — ephemeral, has retention
    StateLocation("runtime/inbox/raw/voice",     "runtime",     "Voice memo audio files",         "medium",   "raw_voice",     "*.m4a"),
    StateLocation("runtime/inbox/raw/gitlab",    "runtime",     "GitLab export JSON files",       "low",      "raw_signals",   "*.json"),
    StateLocation("runtime/inbox/raw/teams",     "runtime",     "Teams transcript files",         "high",     "raw_signals",   "*.json"),
    StateLocation("runtime/inbox/processed",     "runtime",     "Processed transcripts/signals",  "high",     "transcripts",   "*"),
    StateLocation("runtime/inbox/state",         "runtime",     "Briefing and sync state",        "medium",   None),

    # Configuration — indefinite, critical
    StateLocation("runtime/config/people.md",       "config", "Team roster with aliases",    "medium"),
    StateLocation("runtime/config/initiatives.md",  "config", "Active initiatives list",     "low"),
    StateLocation("runtime/config/models.toml",     "config", "LLM endpoint configuration", "low"),

    # Documents — publisher lifecycle
    StateLocation(".publisher-registry.json", "documents", "Published doc URL mappings",   "medium"),
    StateLocation(".publisher-state.json",    "documents", "Document lifecycle state",     "medium"),
    StateLocation("runtime/drafts",           "documents", "Generated drafts",            "low",    "drafts",  "*.md"),

    # Corrections — learned preferences
    StateLocation("runtime/inbox/corrections/review_state.json",      "corrections", "Review progress",       "low"),
    StateLocation("runtime/inbox/corrections/user_glossary.json",     "corrections", "Learned corrections",   "low"),
    StateLocation("runtime/inbox/corrections/propagation_queue.json", "corrections", "Pending propagations",  "low"),

    # Sessions
    StateLocation("runtime/sessions", "sessions", "Chat session history", "high", "sessions", "*.json"),
]
```

---

## Retention Policy Engine

### Configuration Schema

```yaml
# runtime/config/retention.yaml
retention:
  raw_voice:
    days: 7
    after: processed     # "processed" | "ingested" | "created" | "last_accessed"

  raw_signals:
    days: 30
    after: ingested

  transcripts:
    days: 90
    after: created

  sessions:
    days: 30
    after: last_accessed

  drafts:
    days: 14
    after: created

legal_hold:
  enabled: false

audit:
  log_deletions: true
  log_path: runtime/logs/retention_audit.jsonl
```

### Retention Engine

```python
# src/neutron_os/extensions/builtins/mo_agent/retention.py

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from neutron_os.infra.state import STATE_LOCATIONS, StateLocation


@dataclass
class RetentionPolicy:
    key: str
    days: int
    after: str  # "processed" | "ingested" | "created" | "last_accessed"


@dataclass
class RetentionAction:
    path: Path
    policy_key: str
    age_days: int
    action: str  # "delete" | "skip"
    reason: str  # "retention_policy" | "legal_hold"


def load_retention_config(config_dir: Path) -> tuple[list[RetentionPolicy], bool, Path]:
    """Load retention config. Returns (policies, legal_hold, audit_path)."""
    config_path = config_dir / "retention.yaml"
    if not config_path.exists():
        # Fall back to example defaults
        config_path = config_dir.parent / "config.example" / "retention.yaml"
    if not config_path.exists():
        return [], False, config_dir.parent / "logs" / "retention_audit.jsonl"

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    policies = []
    for key, val in cfg.get("retention", {}).items():
        policies.append(RetentionPolicy(key=key, days=val["days"], after=val.get("after", "created")))

    legal_hold = cfg.get("legal_hold", {}).get("enabled", False)
    audit_path = Path(cfg.get("audit", {}).get("log_path", "runtime/logs/retention_audit.jsonl"))
    return policies, legal_hold, audit_path


def get_file_age_reference(path: Path, after: str) -> datetime:
    """Determine the reference timestamp for retention calculation."""
    stat = path.stat()
    if after == "last_accessed":
        return datetime.fromtimestamp(stat.st_atime, tz=timezone.utc)
    elif after == "created":
        return datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
    else:
        # "processed", "ingested" — use mtime as proxy
        return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)


def scan_retention(
    project_root: Path,
    policies: list[RetentionPolicy],
    legal_hold: bool,
) -> list[RetentionAction]:
    """Scan state locations and identify files past retention."""
    now = datetime.now(timezone.utc)
    actions: list[RetentionAction] = []

    policy_map = {p.key: p for p in policies}

    for loc in STATE_LOCATIONS:
        if loc.retention_key is None or loc.retention_key not in policy_map:
            continue

        policy = policy_map[loc.retention_key]
        cutoff = now - timedelta(days=policy.days)
        loc_path = project_root / loc.path

        if not loc_path.exists():
            continue

        # Collect files to check
        files: list[Path] = []
        if loc_path.is_dir():
            files = list(loc_path.glob(loc.glob_pattern))
        elif loc_path.is_file():
            files = [loc_path]

        for file_path in files:
            if not file_path.is_file():
                continue
            ref_time = get_file_age_reference(file_path, policy.after)
            age_days = (now - ref_time).days

            if ref_time < cutoff:
                action = "skip" if legal_hold else "delete"
                reason = "legal_hold" if legal_hold else "retention_policy"
                actions.append(RetentionAction(
                    path=file_path,
                    policy_key=policy.key,
                    age_days=age_days,
                    action=action,
                    reason=reason,
                ))

    return actions


def execute_retention(
    actions: list[RetentionAction],
    audit_path: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    """Execute retention actions and log to audit trail.

    Returns summary: {"deleted": N, "skipped": N, "bytes_freed": N}
    """
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {"deleted": 0, "skipped": 0, "bytes_freed": 0}

    for action in actions:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action.action if not dry_run else "dry_run",
            "path": str(action.path),
            "reason": action.reason,
            "policy": action.policy_key,
            "age_days": action.age_days,
        }

        if action.action == "delete" and not dry_run:
            try:
                size = action.path.stat().st_size
                action.path.unlink()
                summary["deleted"] += 1
                summary["bytes_freed"] += size
            except OSError:
                entry["action"] = "error"
        elif action.action == "skip":
            summary["skipped"] += 1

        with open(audit_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    return summary
```

### M-O Sweep Integration

M-O's existing periodic sweep in `manager.py` gains retention awareness:

```python
# In MoManager.sweep() — extend existing method

def sweep(self) -> dict:
    """Periodic resource sweep — existing scratch cleanup + retention."""
    results = self._sweep_scratch()  # existing

    # Retention sweep (new)
    config_dir = self._project_root / "runtime" / "config"
    policies, legal_hold, audit_path = load_retention_config(config_dir)
    if policies:
        actions = scan_retention(self._project_root, policies, legal_hold)
        retention_results = execute_retention(actions, self._project_root / audit_path)
        results["retention"] = retention_results

    return results
```

### CLI Extension

```python
# Extend mo_agent/cli.py

def register_retention_commands(subparsers):
    ret_parser = subparsers.add_parser("retention", help="Data retention status and cleanup")
    ret_parser.add_argument("--status", action="store_true", help="Show retention status")
    ret_parser.add_argument("--dry-run", action="store_true", help="Preview cleanup without deleting")
    ret_parser.add_argument("--cleanup", action="store_true", help="Execute retention cleanup")
    ret_parser.add_argument("--category", help="Filter by retention category")
```

---

## Testing Strategy

### Unit Tests

```python
# src/neutron_os/extensions/builtins/mo_agent/tests/test_retention.py

def test_scan_finds_expired_files(tmp_path):
    """Files past retention cutoff are identified."""
    ...

def test_legal_hold_prevents_deletion(tmp_path):
    """Legal hold flag changes action from delete to skip."""
    ...

def test_audit_log_written(tmp_path):
    """Every retention action produces an audit log entry."""
    ...

def test_dry_run_deletes_nothing(tmp_path):
    """Dry run logs but doesn't delete."""
    ...
```

```python
# tests/infra/test_state.py

def test_locked_json_read_write(tmp_path):
    """Basic read-modify-write cycle works."""
    ...

def test_atomic_write_survives_crash(tmp_path):
    """Partial writes don't corrupt the file."""
    ...

def test_concurrent_writes_no_corruption(tmp_path):
    """Two processes writing simultaneously produce valid JSON."""
    # Fork or use multiprocessing to verify locking
    ...

def test_exclusive_lock_blocks_concurrent_write(tmp_path):
    """Second exclusive lock waits for first to release."""
    ...
```

### Integration Tests

```python
def test_mo_sweep_includes_retention(tmp_path):
    """M-O's sweep cycle runs retention when config exists."""
    ...

def test_retention_config_missing_is_noop(tmp_path):
    """No retention.yaml = no retention actions."""
    ...
```

---

## Migration Plan

### Phase 0: Safe State Access (3 days)

1. Create `src/neutron_os/infra/state.py` with `LockedJsonFile`, `atomic_write`, `StateLocation`, `STATE_LOCATIONS`
2. Refactor M-O's `manifest.py` to import `LockedJsonFile` from `infra.state`
3. Migrate publisher state files to use `LockedJsonFile`
4. Tests for concurrent access safety

### Phase 1: Retention (1 week)

1. Create `runtime/config.example/retention.yaml`
2. Create `mo_agent/retention.py`
3. Integrate retention sweep into M-O's `manager.py`
4. Add `neut mo retention` CLI subcommand
5. Migrate `CLIP_RETENTION_DAYS` to read from `retention.yaml`
6. Tests for retention engine

---

## Related Documents

- [Agent State Management PRD](../requirements/prd-agent-state-management.md)
- [M-O Agent Extension](../../src/neutron_os/extensions/builtins/mo_agent/)
- [RAG Architecture Spec](spec-rag-architecture.md)
- [Data Architecture Spec](spec-data-architecture.md)
