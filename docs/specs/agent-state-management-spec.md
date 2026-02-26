# NeutronOS Agent State Management Technical Specification

**Status:** Draft  
**Owner:** Ben Lindley  
**Created:** 2026-02-24  
**PRD Reference:** [agent-state-management-prd.md](../prd/agent-state-management-prd.md)

---

## Overview

This specification defines the technical implementation of NeutronOS agent state management, enabling backup, encryption, restoration, and migration of agent state across devices and team members.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         neut state CLI                          │
├─────────────┬─────────────┬─────────────┬─────────────┬────────┤
│  inventory  │   backup    │   restore   │   export    │  sync  │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────┬───┘
       │             │             │             │           │
       ▼             ▼             ▼             ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     State Manager Service                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Inventory  │  │  Archiver   │  │  Encryption Provider    │  │
│  │  Scanner    │  │  (tar/gz)   │  │  (age/git-crypt)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      State Locations                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Runtime  │ │  Config  │ │ DocFlow  │ │Corrections│ │Sessions│ │
│  │  State   │ │  State   │ │  State   │ │  State   │ │ State  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Module Structure

```
tools/agents/state/
├── __init__.py
├── locations.py        # State location definitions
├── inventory.py        # Inventory scanner
├── backup.py           # Backup/restore operations
├── encryption.py       # age/git-crypt integration
├── export.py           # Portable export format
└── cli.py              # CLI subcommands
```

---

## State Location Registry

### Location Definition

```python
# tools/agents/state/locations.py

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

class Sensitivity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class BackupPriority(Enum):
    EXCLUDE = "exclude"
    OPTIONAL = "optional"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Category(Enum):
    RUNTIME = "runtime"
    CONFIG = "config"
    DOCUMENTS = "documents"
    CORRECTIONS = "corrections"
    SESSIONS = "sessions"
    SECRETS = "secrets"

class GitPolicy(Enum):
    """How this state location should be treated in Git."""
    IGNORE = "ignore"              # Always in .gitignore (large/sensitive)
    TRACK_ENCRYPTED = "encrypted"  # Track in Git, encrypted via git-crypt
    TRACK_PLAIN = "plain"          # Track in Git, unencrypted (non-sensitive)
    OPTIONAL = "optional"          # User choice (not in .gitignore, not required)

@dataclass
class StateLocation:
    """Definition of a state storage location."""
    path: str                          # Relative to Neutron_OS root
    category: Category
    description: str
    sensitivity: Sensitivity
    backup_priority: BackupPriority
    glob_pattern: Optional[str] = None  # For directories
    git_policy: GitPolicy = GitPolicy.IGNORE  # Default: gitignored
    merge_strategy: Optional[str] = None  # For Git merge conflicts
    
    def resolve(self, root: Path) -> Path:
        return root / self.path
    
    @property
    def should_encrypt_in_git(self) -> bool:
        """Whether this location should use git-crypt if tracked."""
        return self.git_policy == GitPolicy.TRACK_ENCRYPTED
    
    @property
    def should_gitignore(self) -> bool:
        """Whether this location should be in .gitignore."""
        return self.git_policy == GitPolicy.IGNORE

# Registry of all state locations
STATE_LOCATIONS: list[StateLocation] = [
    # Runtime State — Large/ephemeral, always gitignored
    StateLocation(
        path="tools/agents/inbox/raw/voice",
        category=Category.RUNTIME,
        description="Voice memo audio files",
        sensitivity=Sensitivity.MEDIUM,
        backup_priority=BackupPriority.OPTIONAL,
        glob_pattern="*.m4a",
        git_policy=GitPolicy.IGNORE,  # Too large for Git
    ),
    StateLocation(
        path="tools/agents/inbox/raw/gitlab",
        category=Category.RUNTIME,
        description="GitLab export JSON files",
        sensitivity=Sensitivity.LOW,
        backup_priority=BackupPriority.HIGH,
        glob_pattern="*.json",
        git_policy=GitPolicy.IGNORE,  # Ephemeral exports
    ),
    StateLocation(
        path="tools/agents/inbox/raw/teams",
        category=Category.RUNTIME,
        description="Teams transcript files",
        sensitivity=Sensitivity.HIGH,
        backup_priority=BackupPriority.HIGH,
        glob_pattern="*.json",
        git_policy=GitPolicy.IGNORE,  # Sensitive meeting content
    ),
    StateLocation(
        path="tools/agents/inbox/processed",
        category=Category.RUNTIME,
        description="Processed transcripts and signals",
        sensitivity=Sensitivity.HIGH,
        backup_priority=BackupPriority.CRITICAL,
        glob_pattern="*",
        git_policy=GitPolicy.IGNORE,  # Too large, use backup instead
    ),
    StateLocation(
        path="tools/agents/inbox/state",
        category=Category.RUNTIME,
        description="Briefing and sync state",
        sensitivity=Sensitivity.MEDIUM,
        backup_priority=BackupPriority.HIGH,
        glob_pattern="*.json",
        git_policy=GitPolicy.IGNORE,  # Machine-specific state
    ),
    
    # Configuration State — Valuable, should be Git-tracked with encryption
    StateLocation(
        path="tools/agents/config/people.md",
        category=Category.CONFIG,
        description="Team roster with aliases",
        sensitivity=Sensitivity.MEDIUM,
        backup_priority=BackupPriority.CRITICAL,
        git_policy=GitPolicy.TRACK_ENCRYPTED,  # Encrypted in Git
        merge_strategy="manual",  # Human review for team changes
    ),
    StateLocation(
        path="tools/agents/config/initiatives.md",
        category=Category.CONFIG,
        description="Active initiatives list",
        sensitivity=Sensitivity.LOW,
        backup_priority=BackupPriority.CRITICAL,
        git_policy=GitPolicy.TRACK_ENCRYPTED,  # Encrypted in Git
        merge_strategy="manual",
    ),
    StateLocation(
        path="tools/agents/config/models.yaml",
        category=Category.CONFIG,
        description="LLM endpoint configuration",
        sensitivity=Sensitivity.LOW,
        backup_priority=BackupPriority.HIGH,
        git_policy=GitPolicy.TRACK_ENCRYPTED,  # May contain API endpoints
    ),
    StateLocation(
        path=".doc-workflow.yaml",
        category=Category.CONFIG,
        description="DocFlow provider configuration",
        sensitivity=Sensitivity.MEDIUM,
        backup_priority=BackupPriority.HIGH,
        git_policy=GitPolicy.TRACK_ENCRYPTED,  # May reference credentials
    ),
    
    # Document Lifecycle State — Critical for continuity, Git-tracked encrypted
    StateLocation(
        path=".doc-registry.json",
        category=Category.DOCUMENTS,
        description="Published document URL mappings",
        sensitivity=Sensitivity.MEDIUM,
        backup_priority=BackupPriority.CRITICAL,
        git_policy=GitPolicy.TRACK_ENCRYPTED,
        merge_strategy="doc_registry",  # Merge by doc_id
    ),
    StateLocation(
        path=".doc-state.json",
        category=Category.DOCUMENTS,
        description="Document lifecycle state",
        sensitivity=Sensitivity.MEDIUM,
        backup_priority=BackupPriority.CRITICAL,
        git_policy=GitPolicy.TRACK_ENCRYPTED,
        merge_strategy="doc_registry",  # Same as registry
    ),
    StateLocation(
        path="tools/agents/drafts",
        category=Category.DOCUMENTS,
        description="Generated changelog drafts",
        sensitivity=Sensitivity.LOW,
        backup_priority=BackupPriority.MEDIUM,
        glob_pattern="*.md",
        git_policy=GitPolicy.IGNORE,  # Regenerated, not critical
    ),
    StateLocation(
        path="tools/agents/approved",
        category=Category.DOCUMENTS,
        description="Human-approved outputs",
        sensitivity=Sensitivity.MEDIUM,
        backup_priority=BackupPriority.HIGH,
        glob_pattern="*",
        git_policy=GitPolicy.OPTIONAL,  # User may want history
    ),
    
    # Corrections State — Valuable learning, Git-track the glossary
    StateLocation(
        path="tools/agents/inbox/corrections/review_state.json",
        category=Category.CORRECTIONS,
        description="Correction review progress",
        sensitivity=Sensitivity.LOW,
        backup_priority=BackupPriority.HIGH,
        git_policy=GitPolicy.IGNORE,  # Session-specific progress
    ),
    StateLocation(
        path="tools/agents/inbox/corrections/user_glossary.json",
        category=Category.CORRECTIONS,
        description="Learned transcription corrections",
        sensitivity=Sensitivity.LOW,
        backup_priority=BackupPriority.CRITICAL,
        git_policy=GitPolicy.TRACK_ENCRYPTED,  # Valuable learning
        merge_strategy="user_glossary",  # Additive merge
    ),
    StateLocation(
        path="tools/agents/inbox/corrections/propagation_queue.json",
        category=Category.CORRECTIONS,
        description="Pending correction propagations",
        sensitivity=Sensitivity.LOW,
        backup_priority=BackupPriority.HIGH,
        git_policy=GitPolicy.IGNORE,  # Transient queue
    ),
    
    # Sessions State — Sensitive, gitignored
    StateLocation(
        path="tools/agents/sessions",
        category=Category.SESSIONS,
        description="Chat session history",
        sensitivity=Sensitivity.HIGH,
        backup_priority=BackupPriority.HIGH,
        glob_pattern="*.json",
        git_policy=GitPolicy.IGNORE,  # Too sensitive for Git
    ),
    
    # Secrets (excluded from backup AND Git)
    StateLocation(
        path=".env",
        category=Category.SECRETS,
        description="API keys and tokens",
        sensitivity=Sensitivity.CRITICAL,
        backup_priority=BackupPriority.EXCLUDE,
    ),
]
```

---

## CLI Commands

### `neut state inventory`

```
Usage: neut state inventory [OPTIONS]

  Display inventory of all agent state locations.

Options:
  --verbose, -v    Show file-level details
  --json           Output as JSON
  --category TEXT  Filter by category (runtime, config, documents, corrections, sessions)
  --help           Show this message and exit.

Example Output:
  neut state — inventory

  Category: config (3 locations, 2 KB)
    ✓ config/people.md           1.2 KB  [CRITICAL]
    ✓ config/initiatives.md      0.5 KB  [CRITICAL]
    ✗ config/models.yaml         (missing)

  Category: corrections (3 locations, 45 KB)
    ✓ corrections/review_state.json    12 KB  [HIGH]
    ✓ corrections/user_glossary.json    8 KB  [CRITICAL]
    ✓ corrections/propagation_queue.json  25 KB  [HIGH]

  Category: runtime (5 locations, 1.2 MB)
    ✓ inbox/processed/           1.1 MB (23 files)  [CRITICAL]
    ✓ inbox/state/               45 KB (3 files)    [HIGH]
    ...

  Total: 15 locations, 1.4 MB
  Critical: 5 | High: 6 | Medium: 3 | Optional: 1
```

### `neut state backup`

```
Usage: neut state backup [OPTIONS]

  Create encrypted backup of agent state.

Options:
  --output, -o PATH      Output path (default: ~/.neut-backups/neut-state-{timestamp}.tar.gz.age)
  --no-encrypt           Skip encryption (not recommended)
  --include-media        Include voice/video files (large)
  --include-secrets      Include .env (requires explicit opt-in)
  --passphrase TEXT      Encryption passphrase (prompted if not provided)
  --key-file PATH        Use age key file instead of passphrase
  --help                 Show this message and exit.

Example:
  $ neut state backup
  Enter passphrase: ********
  Confirm passphrase: ********

  neut state — backup

  Scanning state locations...
  ✓ config/people.md (1.2 KB)
  ✓ config/initiatives.md (0.5 KB)
  ✓ inbox/processed/ (23 files, 1.1 MB)
  ✓ corrections/user_glossary.json (8 KB)
  ...
  ⊘ .env (excluded: secrets)
  ⊘ inbox/raw/voice/ (excluded: media)

  Creating archive...
  Encrypting with age...

  ✓ Backup created: ~/.neut-backups/neut-state-2026-02-24T143022.tar.gz.age
    Size: 892 KB (compressed from 1.4 MB)
    Files: 47
    Checksum: sha256:a1b2c3d4...
```

### `neut state restore`

```
Usage: neut state restore [OPTIONS] BACKUP_PATH

  Restore agent state from backup.

Arguments:
  BACKUP_PATH  Path to backup file (.tar.gz or .tar.gz.age)

Options:
  --passphrase TEXT   Decryption passphrase (prompted if encrypted)
  --key-file PATH     Use age key file for decryption
  --dry-run           Show what would be restored without making changes
  --force             Overwrite existing files without prompting
  --category TEXT     Restore only specific category
  --help              Show this message and exit.

Example:
  $ neut state restore ~/.neut-backups/neut-state-2026-02-24T143022.tar.gz.age --dry-run
  Enter passphrase: ********

  neut state — restore (dry run)

  Validating backup...
  ✓ Checksum verified
  ✓ Manifest version: 1.0
  ✓ Created: 2026-02-24 14:30:22

  Would restore:
    config/people.md (1.2 KB) → exists, would overwrite
    config/initiatives.md (0.5 KB) → exists, would overwrite
    inbox/processed/meeting_2026-02-20.json → new
    corrections/user_glossary.json (8 KB) → exists, would merge

  Total: 47 files, 892 KB
  Run without --dry-run to apply.
```

### `neut state export`

```
Usage: neut state export [OPTIONS] CATEGORY

  Export state category to portable format.

Arguments:
  CATEGORY  Category to export (config, corrections, documents, sessions)

Options:
  --output, -o PATH   Output path (default: stdout)
  --format TEXT       Output format: json, yaml (default: json)
  --help              Show this message and exit.

Example:
  $ neut state export corrections -o my-corrections.json
  
  neut state — export

  Exporting corrections state...
  ✓ review_state.json
  ✓ user_glossary.json
  ✓ propagation_queue.json

  Exported to: my-corrections.json
  Schema version: 1.0
```

---

## Backup Format

### Archive Structure

```
neut-state-{timestamp}.tar.gz
├── manifest.json           # Backup metadata
├── config/
│   ├── people.md
│   ├── initiatives.md
│   └── models.yaml
├── documents/
│   ├── .doc-registry.json
│   ├── .doc-state.json
│   └── .doc-workflow.yaml
├── corrections/
│   ├── review_state.json
│   ├── user_glossary.json
│   └── propagation_queue.json
├── runtime/
│   ├── inbox_processed/
│   │   └── *.json
│   └── inbox_state/
│       └── *.json
└── sessions/
    └── *.json
```

### Manifest Schema

```json
{
  "$schema": "https://neutronos.dev/schemas/state-backup-manifest-v1.json",
  "version": "1.0",
  "created_at": "2026-02-24T14:30:22Z",
  "neutron_os_version": "0.1.0",
  "machine_id": "ME-A94401",
  "user": "ben",
  "checksum": "sha256:a1b2c3d4e5f6...",
  "encryption": {
    "algorithm": "age-x25519-chacha20poly1305",
    "key_derivation": "scrypt"
  },
  "contents": {
    "total_files": 47,
    "total_bytes": 1474560,
    "compressed_bytes": 913408,
    "categories": {
      "config": {"files": 3, "bytes": 2048},
      "documents": {"files": 5, "bytes": 4096},
      "corrections": {"files": 3, "bytes": 46080},
      "runtime": {"files": 26, "bytes": 1126400},
      "sessions": {"files": 10, "bytes": 296936}
    }
  },
  "excluded": [
    {"path": ".env", "reason": "secrets"},
    {"path": "inbox/raw/voice/", "reason": "media", "files": 5, "bytes": 52428800}
  ],
  "files": [
    {
      "path": "config/people.md",
      "size": 1234,
      "modified": "2026-02-23T10:15:00Z",
      "checksum": "sha256:..."
    }
  ]
}
```

---

## Encryption

### age Integration

[age](https://age-encryption.org/) is a modern, audited encryption tool:

```python
# tools/agents/state/encryption.py

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

class AgeEncryption:
    """Encrypt/decrypt using age."""
    
    @staticmethod
    def encrypt_file(
        input_path: Path,
        output_path: Path,
        passphrase: Optional[str] = None,
        key_file: Optional[Path] = None,
    ) -> None:
        """Encrypt a file with age."""
        cmd = ["age", "--encrypt", "--output", str(output_path)]
        
        if key_file:
            cmd.extend(["--recipients-file", str(key_file)])
        else:
            cmd.append("--passphrase")
        
        cmd.append(str(input_path))
        
        env = None
        if passphrase and not key_file:
            # age reads passphrase from AGE_PASSPHRASE env var
            env = {"AGE_PASSPHRASE": passphrase}
        
        subprocess.run(cmd, check=True, env=env)
    
    @staticmethod
    def decrypt_file(
        input_path: Path,
        output_path: Path,
        passphrase: Optional[str] = None,
        key_file: Optional[Path] = None,
    ) -> None:
        """Decrypt a file with age."""
        cmd = ["age", "--decrypt", "--output", str(output_path)]
        
        if key_file:
            cmd.extend(["--identity", str(key_file)])
        
        cmd.append(str(input_path))
        
        env = None
        if passphrase and not key_file:
            env = {"AGE_PASSPHRASE": passphrase}
        
        subprocess.run(cmd, check=True, env=env)
```

### Keychain Integration (macOS)

```python
import subprocess

def store_passphrase_keychain(service: str, account: str, passphrase: str) -> None:
    """Store passphrase in macOS Keychain."""
    subprocess.run([
        "security", "add-generic-password",
        "-s", service,
        "-a", account,
        "-w", passphrase,
        "-U",  # Update if exists
    ], check=True)

def get_passphrase_keychain(service: str, account: str) -> str:
    """Retrieve passphrase from macOS Keychain."""
    result = subprocess.run([
        "security", "find-generic-password",
        "-s", service,
        "-a", account,
        "-w",
    ], capture_output=True, text=True, check=True)
    return result.stdout.strip()
```

---

## Git Integration

State management is designed to be **Git-aware but Git-optional**. When running in a Git repository, the system can leverage Git for versioning, sync, and backup while remaining fully functional without Git.

### Git Detection

```python
# tools/agents/state/git_integration.py

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class GitStatus:
    """Git repository status for state management."""
    is_git_repo: bool
    root: Optional[Path]
    current_branch: Optional[str]
    has_remote: bool
    remote_url: Optional[str]
    is_clean: bool
    git_crypt_enabled: bool
    git_crypt_unlocked: bool

def detect_git_status(path: Path) -> GitStatus:
    """Detect Git repository status at path."""
    try:
        # Check if in git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return GitStatus(
                is_git_repo=False, root=None, current_branch=None,
                has_remote=False, remote_url=None, is_clean=True,
                git_crypt_enabled=False, git_crypt_unlocked=False,
            )
        
        # Get repo root
        root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        root = Path(root_result.stdout.strip()) if root_result.returncode == 0 else None
        
        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        branch = branch_result.stdout.strip() or None
        
        # Check for remote
        remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        has_remote = remote_result.returncode == 0
        remote_url = remote_result.stdout.strip() if has_remote else None
        
        # Check if clean
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        is_clean = len(status_result.stdout.strip()) == 0
        
        # Check git-crypt status
        git_crypt_enabled = (root / ".git-crypt").exists() if root else False
        git_crypt_unlocked = False
        if git_crypt_enabled:
            unlock_result = subprocess.run(
                ["git-crypt", "status", "-e"],
                cwd=path, capture_output=True, text=True, timeout=5,
            )
            # If exit code is 0 and no output, all files are decrypted
            git_crypt_unlocked = unlock_result.returncode == 0
        
        return GitStatus(
            is_git_repo=True,
            root=root,
            current_branch=branch,
            has_remote=has_remote,
            remote_url=remote_url,
            is_clean=is_clean,
            git_crypt_enabled=git_crypt_enabled,
            git_crypt_unlocked=git_crypt_unlocked,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return GitStatus(
            is_git_repo=False, root=None, current_branch=None,
            has_remote=False, remote_url=None, is_clean=True,
            git_crypt_enabled=False, git_crypt_unlocked=False,
        )
```

### Git-Aware Inventory Display

```python
def format_git_status(location: StateLocation, git_status: GitStatus) -> str:
    """Format Git tracking status for display."""
    if not git_status.is_git_repo:
        return ""
    
    path = location.resolve(git_status.root)
    
    # Check if in .gitignore
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=git_status.root, capture_output=True, timeout=5,
    )
    if result.returncode == 0:
        return "git:ignored"
    
    # Check if tracked
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)],
        cwd=git_status.root, capture_output=True, timeout=5,
    )
    if result.returncode != 0:
        return "git:untracked ⚠️"
    
    # Check if encrypted via git-crypt
    if git_status.git_crypt_enabled:
        result = subprocess.run(
            ["git-crypt", "status", str(path)],
            cwd=git_status.root, capture_output=True, text=True, timeout=5,
        )
        if "encrypted" in result.stdout.lower():
            return "git:encrypted"
    
    return "git:tracked"
```

### Git-Crypt Integration (Phase 1)

[git-crypt](https://github.com/AGWA/git-crypt) provides transparent encryption for Git-tracked files.

#### Setup

```bash
# Initialize git-crypt in repo
git-crypt init

# Export symmetric key for team sharing
git-crypt export-key /path/to/neutron-os.key

# Or add GPG key for a team member
git-crypt add-gpg-user --trusted KEYID

# Add patterns to .gitattributes
cat >> .gitattributes << 'EOF'
# State files encrypted via git-crypt
tools/agents/config/people.md filter=git-crypt diff=git-crypt
tools/agents/config/initiatives.md filter=git-crypt diff=git-crypt
.doc-registry.json filter=git-crypt diff=git-crypt
.doc-state.json filter=git-crypt diff=git-crypt
tools/agents/inbox/corrections/user_glossary.json filter=git-crypt diff=git-crypt
EOF

# Commit the configuration
git add .gitattributes
git commit -m "Configure git-crypt for state encryption"
```

#### `.gitattributes` Patterns

```gitattributes
# Tier 1: Encrypted state (decrypted only on authorized machines)
tools/agents/config/people.md filter=git-crypt diff=git-crypt
tools/agents/config/initiatives.md filter=git-crypt diff=git-crypt
tools/agents/config/models.yaml filter=git-crypt diff=git-crypt
.doc-registry.json filter=git-crypt diff=git-crypt
.doc-state.json filter=git-crypt diff=git-crypt
.doc-workflow.yaml filter=git-crypt diff=git-crypt
tools/agents/inbox/corrections/user_glossary.json filter=git-crypt diff=git-crypt

# Note: Large/sensitive state stays in .gitignore (Tier 2)
# inbox/raw/, inbox/processed/, sessions/ are NOT tracked
```

#### Unlock on New Machine

```bash
# Using symmetric key
git-crypt unlock /path/to/neutron-os.key

# Using GPG (if your key was added)
git-crypt unlock
```

### Git-Aware Commands

#### `neut state sync`

```
Usage: neut state sync [OPTIONS]

  Synchronize state with Git remote.

Options:
  --pull           Pull latest state from remote (default)
  --push           Push local state to remote
  --force          Force push/pull (use with caution)
  --dry-run        Show what would change without applying
  --help           Show this message and exit.

Example:
  $ neut state sync --pull

  neut state — sync

  Git status:
    Repository: /Users/ben/Projects/UT_Computational_NE/Neutron_OS
    Branch: main
    Remote: origin (github.com:ut-nuclear/neutron-os.git)
    git-crypt: enabled, unlocked

  Pulling from origin/main...
  ✓ config/people.md updated
      + Alice Chen (new team member)
      + Bob Smith (new team member)
  ✓ user_glossary.json merged
      + 12 new correction entries

  State synchronized.
```

#### `neut state backup --git-commit`

```
Usage: neut state backup [OPTIONS]

Options:
  --git-commit     Commit encrypted state to Git after backup
  --git-push       Push to remote after commit (implies --git-commit)
  --git-message    Custom commit message

Example:
  $ neut state backup --git-push

  neut state — backup

  Creating backup archive...
  ✓ 47 files, 892 KB (encrypted)

  Git operations:
  ✓ Updated .gitattributes for new state files
  ✓ Staged encrypted state files
  ✓ Committed: "state backup 2026-02-24T14:30:22"
  ✓ Pushed to origin/main

  Backup complete.
```

### State Merge Strategy

When pulling state from Git, conflicts may occur. The system uses schema-aware merge:

```python
# tools/agents/state/merge.py

from typing import Any
import json

def merge_user_glossary(local: dict, remote: dict) -> dict:
    """Merge user glossary entries (corrections are additive)."""
    merged = {"entries": {}, "metadata": remote.get("metadata", {})}
    
    # Corrections are keyed by (original_text, corrected_text)
    # Take the union, preferring remote for conflicts
    all_entries = {}
    
    for entry in local.get("entries", {}).values():
        key = (entry["original"], entry["corrected"])
        all_entries[key] = entry
    
    for entry in remote.get("entries", {}).values():
        key = (entry["original"], entry["corrected"])
        # Remote wins on conflict (more recent)
        all_entries[key] = entry
    
    merged["entries"] = {
        f"{i}": entry for i, entry in enumerate(all_entries.values())
    }
    return merged

def merge_doc_registry(local: dict, remote: dict) -> dict:
    """Merge document registry (by doc_id, remote wins)."""
    merged = {"documents": []}
    
    local_docs = {d["doc_id"]: d for d in local.get("documents", [])}
    remote_docs = {d["doc_id"]: d for d in remote.get("documents", [])}
    
    # Union of all doc_ids, remote wins on conflict
    all_ids = set(local_docs.keys()) | set(remote_docs.keys())
    for doc_id in sorted(all_ids):
        if doc_id in remote_docs:
            merged["documents"].append(remote_docs[doc_id])
        else:
            merged["documents"].append(local_docs[doc_id])
    
    return merged

MERGE_STRATEGIES = {
    "user_glossary.json": merge_user_glossary,
    ".doc-registry.json": merge_doc_registry,
    ".doc-state.json": merge_doc_registry,  # Same strategy
    # For config files, prefer manual merge or remote-wins
}
```

### Migration: Existing Repo to Git-Crypt

For repositories with existing unencrypted state:

```bash
# 1. Ensure state is in .gitignore first
echo "tools/agents/config/" >> .gitignore
git add .gitignore
git commit -m "Temporarily ignore state for git-crypt migration"

# 2. Initialize git-crypt
git-crypt init

# 3. Configure .gitattributes
# (add patterns as shown above)
git add .gitattributes
git commit -m "Configure git-crypt encryption patterns"

# 4. Remove state from .gitignore
# Edit .gitignore to remove tools/agents/config/

# 5. Add state files (now encrypted)
git add tools/agents/config/
git commit -m "Add encrypted state files"

# 6. Force-push to rewrite history (optional, if state was previously tracked unencrypted)
# WARNING: This rewrites history and requires team coordination
# git filter-branch --force --tree-filter 'git-crypt status -e || true' HEAD
```

---

## PostgreSQL Schema (Phase 2)

```sql
-- State snapshots for team sync
CREATE TABLE state_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    category TEXT NOT NULL,
    path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content BYTEA NOT NULL,  -- Encrypted blob
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (user_id, category, path)
);

-- Access control
CREATE TABLE state_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES state_snapshots(id),
    shared_with_user_id UUID REFERENCES users(id),
    shared_with_team_id UUID REFERENCES teams(id),
    permission TEXT NOT NULL CHECK (permission IN ('viewer', 'editor', 'owner')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CHECK (shared_with_user_id IS NOT NULL OR shared_with_team_id IS NOT NULL)
);

-- Audit log
CREATE TABLE state_access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    snapshot_id UUID REFERENCES state_snapshots(id),
    action TEXT NOT NULL,  -- 'view', 'download', 'upload', 'delete', 'share'
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_state_snapshots_user ON state_snapshots(user_id);
CREATE INDEX idx_state_access_log_user ON state_access_log(user_id);
CREATE INDEX idx_state_access_log_time ON state_access_log(created_at);
```

---

## Testing Strategy

### Unit Tests

```python
# tests/agents/state/test_inventory.py

def test_inventory_scanner_finds_all_locations():
    """Scanner identifies all defined state locations."""
    scanner = InventoryScanner(root=FIXTURES_ROOT)
    inventory = scanner.scan()
    
    assert len(inventory.locations) == len(STATE_LOCATIONS)
    assert inventory.total_size > 0

def test_inventory_handles_missing_locations():
    """Scanner gracefully handles missing directories."""
    scanner = InventoryScanner(root=EMPTY_ROOT)
    inventory = scanner.scan()
    
    missing = [loc for loc in inventory.locations if not loc.exists]
    assert len(missing) > 0

# tests/agents/state/test_backup.py

def test_backup_creates_valid_archive():
    """Backup creates tar.gz with manifest."""
    backup = StateBackup(root=FIXTURES_ROOT)
    archive_path = backup.create(output_dir=TMP_DIR)
    
    assert archive_path.exists()
    assert archive_path.suffix == ".gz"
    
    with tarfile.open(archive_path) as tar:
        assert "manifest.json" in tar.getnames()

def test_backup_excludes_secrets():
    """Backup never includes .env by default."""
    backup = StateBackup(root=FIXTURES_ROOT)
    archive_path = backup.create(output_dir=TMP_DIR)
    
    with tarfile.open(archive_path) as tar:
        assert ".env" not in tar.getnames()

def test_restore_validates_checksum():
    """Restore fails on corrupted archive."""
    backup = StateBackup(root=FIXTURES_ROOT)
    archive_path = backup.create(output_dir=TMP_DIR)
    
    # Corrupt the archive
    with open(archive_path, "r+b") as f:
        f.seek(100)
        f.write(b"CORRUPTED")
    
    with pytest.raises(ChecksumError):
        backup.restore(archive_path)
```

### Integration Tests

```python
def test_backup_restore_roundtrip():
    """Full backup and restore preserves all state."""
    # Create state
    with temp_neutron_root() as root:
        (root / "tools/agents/config/people.md").write_text("# People\n")
        (root / ".doc-registry.json").write_text("{}")
        
        # Backup
        backup = StateBackup(root=root)
        archive = backup.create(output_dir=TMP_DIR, encrypt=True, passphrase="test")
        
        # Clear state
        shutil.rmtree(root / "tools/agents/config")
        (root / ".doc-registry.json").unlink()
        
        # Restore
        backup.restore(archive, passphrase="test")
        
        # Verify
        assert (root / "tools/agents/config/people.md").read_text() == "# People\n"
        assert (root / ".doc-registry.json").exists()
```

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| age | ≥1.0 | File encryption |
| git-crypt | ≥0.7 | Git-transparent encryption (Phase 1) |
| python-gnupg | ≥0.5 | GPG operations (optional) |
| keyring | ≥24.0 | Cross-platform keychain access |

### Installation

```bash
# macOS
brew install age git-crypt

# Linux (apt)
sudo apt install age git-crypt

# Python dependencies
pip install keyring
```

---

## Migration Notes

### Schema Versioning

The manifest includes a `version` field for forward compatibility:

- **v1.0**: Initial schema (Phase 0)
- **v1.1**: Added git-crypt metadata (Phase 1)
- **v2.0**: PostgreSQL sync metadata (Phase 2)

Migration code checks version and applies transforms:

```python
def migrate_manifest(manifest: dict) -> dict:
    version = manifest.get("version", "1.0")
    
    if version == "1.0":
        # v1.0 → v1.1: Add git_crypt field
        manifest["git_crypt"] = {"enabled": False}
        manifest["version"] = "1.1"
    
    return manifest
```

---

## Related Documents

- [Agent State Management PRD](../prd/agent-state-management-prd.md)
- [DocFlow Specification](docflow-spec.md) — Document lifecycle state
- [Data Architecture Specification](data-architecture-spec.md)
