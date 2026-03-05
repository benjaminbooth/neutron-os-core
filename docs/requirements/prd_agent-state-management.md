# NeutronOS Agent State Management PRD

**Status:** Draft  
**Owner:** Ben Lindley  
**Created:** 2026-02-24  
**Last Updated:** 2026-02-24

---

## Executive Summary

NeutronOS agents accumulate valuable state across 15+ filesystem locations—transcripts, corrections, session history, configuration, document registries, and learned preferences. This state currently exists only on individual developer machines, creating risks around data loss, device theft, team collaboration, forensic analysis, and IP retention. This PRD defines requirements for a comprehensive state management system that enables backup, encryption, migration, and eventually enterprise-grade collaboration while maintaining the offline-first, human-in-the-loop principles core to NeutronOS.

---

## Problem Statement

### Current State Distribution

Agent state is spread across the filesystem with no unified management:

| Category | Locations | Git Status | Risk |
|----------|-----------|------------|------|
| **Runtime** | `inbox/raw/`, `inbox/processed/`, `inbox/state/`, `sessions/` | Gitignored | Lost on device failure |
| **Configuration** | `config/people.md`, `config/initiatives.md`, `.doc-workflow.yaml` | Gitignored | Facility-specific, must migrate |
| **Document Lifecycle** | `.doc-registry.json`, `.doc-state.json`, `drafts/`, `approved/` | Gitignored | Published doc mappings lost |
| **Corrections** | `inbox/corrections/review_state.json`, `user_glossary.json` | Gitignored | Learned preferences lost |
| **Secrets** | `.env`, API keys in workflow configs | Gitignored | Security-sensitive |

### Business Risks Addressed

1. **Filesystem Corruption**: No backup mechanism; state loss requires manual reconstruction
2. **Device Theft**: Sensitive meeting transcripts, strategic documents exposed in plaintext
3. **Device Migration**: New laptop requires manual state reconstruction; no "clone my setup"
4. **Security Forensics**: Cannot replay historical system state to diagnose attacks
5. **IP Retention**: When team members leave, valuable institutional knowledge (corrections, preferences, document history) may be lost with their device

### User Pain Points

- "I got a new laptop and lost all my correction preferences"
- "My disk crashed and I lost 6 months of meeting transcripts"
- "Someone left the team and we lost access to their document mappings"
- "I can't tell what changed in the system over the last month"

---

## Goals & Non-Goals

### Goals

1. **Inventory**: Provide complete visibility into all agent state locations
2. **Backup/Restore**: Enable point-in-time backup and restoration of agent state
3. **Encryption**: Protect sensitive state at rest (device theft scenario)
4. **Migration**: Enable state transfer between devices
5. **Audit Trail**: Track state changes over time for forensics/compliance
6. **Team Sync** (Phase 2+): Enable collaborative state sharing with access control
7. **Document Sync Integration**: Include published document state in management scope

### Non-Goals

- Replacing Git for code version control
- Real-time collaborative editing (use external tools)
- Managing secrets rotation (defer to Vault/SOPS)
- Backing up raw audio/video files (large media excluded by default)

---

## User Stories

### Phase 0: Single Developer (MVP)

**US-001**: As a developer, I want to see a complete inventory of my agent state so I understand what exists on my machine.

**US-002**: As a developer, I want to backup my agent state to an encrypted archive so I can restore after device failure.

**US-003**: As a developer, I want to restore agent state from a backup so I can recover from data loss or migrate to a new device.

**US-004**: As a developer, I want my backups encrypted so device theft doesn't expose sensitive transcripts.

**US-005**: As a developer, I want to export my state in a portable format so I can migrate between machines.

### Phase 1: Git-Backed State

**US-010**: As a developer, I want selective state tracked in Git (encrypted) so I have version history and cloud backup.

**US-011**: As a developer, I want to decrypt state only on authorized machines so git-tracked state remains secure.

### Phase 2: Team Sync

**US-020**: As a team lead, I want shared configuration (people, initiatives) synced across team members so everyone has current context.

**US-021**: As an admin, I want access control on shared state so sensitive data is restricted appropriately.

**US-022**: As a compliance officer, I want audit logs of state access so we can demonstrate data governance.

### Phase 3: Enterprise

**US-030**: As an enterprise admin, I want RBAC for state management so I can enforce organizational policies.

**US-031**: As a security team member, I want to replay historical state snapshots so I can investigate incidents.

**US-032**: As legal counsel, I want to export a departing employee's state so the organization retains IP rights.

### Phase 4: Retention & Compliance

**US-040**: As a developer, I want raw inbox data automatically cleaned up after processing so my disk doesn't fill up.

**US-041**: As an admin, I want configurable retention policies per data category so I can balance storage costs with compliance needs.

**US-042**: As a compliance officer, I want retention policies enforced automatically so we don't retain data longer than permitted.

**US-043**: As an auditor, I want a log of what was deleted and when so I can verify policy compliance.

---

## Data Retention & Lifecycle Management

Agent state has varying retention requirements based on sensitivity, storage cost, and compliance needs. This section defines the retention lifecycle and automation requirements.

### Retention Policy Framework

| Data Category | Default Retention | Rationale | Configurable |
|---------------|-------------------|-----------|--------------|
| **Raw voice memos** (`inbox/raw/voice/`) | 7 days after processing | Large files, transcript is derived artifact | Yes |
| **Raw signal sources** (`inbox/raw/{gitlab,teams,teams_chat}/`) | 30 days | Source of truth for processed signals | Yes |
| **Processed transcripts** (`inbox/processed/`) | 90 days | Reference for corrections, briefings | Yes |
| **Sessions** (`sessions/`) | 30 days | Chat history, can regenerate context | Yes |
| **Corrections/glossary** (`corrections/`) | Indefinite | Valuable learned preferences, small | No |
| **Configuration** (`config/`) | Indefinite | Critical operational data | No |
| **State backups** (`~/.neut-backups/`) | 30 days (keep last 5) | Balance recovery vs. disk usage | Yes |
| **Draft outputs** (`drafts/`) | 14 days | Regeneratable, ephemeral | Yes |
| **Echo suppression cache** | 7 days (auto-expires) | Already has expiration built-in | No |

### State Lifecycle Stages

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Ingested   │───▶│  Processed   │───▶│   Archived   │───▶│   Purged     │
│              │    │              │    │  (optional)  │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     │                    │                   │                   │
     ▼                    ▼                   ▼                   ▼
 inbox/raw/         inbox/processed/    encrypted backup      deleted
 voice/, teams/     transcripts,        (retained per         (logged)
                    signals             policy)
```

### Existing Retention Mechanisms

Current implementations that need unification:

| Component | Location | Current Behavior |
|-----------|----------|------------------|
| **Audio clips** | `correction_review_guided.py` | `CLIP_RETENTION_DAYS = 7` |
| **Echo suppression** | `echo_suppression.py` | `expires_at` field, `cleanup_expired()` |
| **DocFlow sync cache** | `docflow_providers/` | `expires_at` in cache records |

### Retention Policy Configuration

Retention policies should be configurable via `config/retention.yaml`:

```yaml
# tools/agents/config/retention.yaml
retention:
  # Raw input data
  raw_voice:
    days: 7
    after: processed  # Retain N days after processed flag set
    
  raw_signals:
    days: 30
    after: ingested
    
  # Processed data
  transcripts:
    days: 90
    after: created
    archive_before_delete: true  # Backup to archive before purge
    
  sessions:
    days: 30
    after: last_accessed
    
  # Outputs
  drafts:
    days: 14
    after: created
    
  # Backups
  state_backups:
    keep_count: 5
    max_age_days: 30

# Compliance overrides (e.g., legal hold)
legal_hold:
  enabled: false
  # When enabled, no deletion occurs
  
# Audit logging
audit:
  log_deletions: true
  log_path: logs/retention_audit.jsonl
```

### Retention Functional Requirements

**FR-010: Retention Status Command**

```bash
neut state retention [--status] [--dry-run]
```

Shows retention status across all data categories:
- Files approaching retention cutoff
- Space recoverable by cleanup
- Policy compliance status

**FR-011: Retention Cleanup Command**

```bash
neut state cleanup [--dry-run] [--category <cat>] [--force]
```

Executes retention policy:
- Dry-run shows what would be deleted
- Category filter for selective cleanup
- Logs all deletions to audit trail

**FR-012: Automated Retention Daemon**

Background process or cron job that:
- Runs daily (configurable)
- Applies retention policies
- Logs all actions
- Respects legal hold flags

**FR-013: Retention Audit Log**

All retention actions logged in JSONL format:
```json
{"timestamp": "2026-02-24T14:30:00Z", "action": "delete", "path": "inbox/raw/voice/memo_123.m4a", "reason": "retention_policy", "policy": "raw_voice", "age_days": 8}
```

### Compliance Considerations (Phase 4)

| Requirement | Implementation |
|-------------|----------------|
| **GDPR Right to Erasure** | `neut state purge --user <email>` command |
| **Legal Hold** | `legal_hold.enabled` flag suspends all deletion |
| **Audit Trail** | JSONL retention log with immutable append |
| **Data Minimization** | Default policies favor shorter retention |
| **Cross-border** | Archive encryption before any cloud backup |

### Example Cleanup Workflow

```bash
# Check what would be cleaned up
$ neut state cleanup --dry-run

Retention Cleanup Preview
═════════════════════════
Category: raw_voice (7 days after processed)
  • inbox/raw/voice/memo_2026-02-15.m4a (9 days old) → DELETE
  • inbox/raw/voice/memo_2026-02-16.m4a (8 days old) → DELETE
  Space recoverable: 45 MB

Category: sessions (30 days after last_accessed)
  • sessions/abc123.json (45 days) → DELETE
  Space recoverable: 2 MB

Total: 47 MB recoverable

# Execute cleanup
$ neut state cleanup
  ✓ Deleted 2 voice memos (45 MB)
  ✓ Deleted 1 session (2 MB)
  ✓ Audit log updated: logs/retention_audit.jsonl
```

---

## State Taxonomy

### Category 1: Runtime State

Ephemeral data from agent operations:

| Location | Contents | Sensitivity | Backup Priority |
|----------|----------|-------------|-----------------|
| `inbox/raw/voice/` | Voice memo `.m4a` files | Medium | Optional (large) |
| `inbox/raw/gitlab/` | GitLab export JSON | Low | High |
| `inbox/raw/teams/` | Teams transcript JSON | High | High |
| `inbox/processed/` | Transcripts, signals, corrections | High | **Critical** |
| `inbox/state/` | Briefing state, sync timestamps | Medium | High |
| `sessions/` | Chat session JSON (UUID.json) | High | High |

### Category 2: Configuration State

Facility-specific settings:

| Location | Contents | Sensitivity | Backup Priority |
|----------|----------|-------------|-----------------|
| `config/people.md` | Team roster with aliases | Medium | **Critical** |
| `config/initiatives.md` | Active projects | Low | **Critical** |
| `config/models.yaml` | LLM endpoints | Low | High |
| `.doc-workflow.yaml` | DocFlow provider config | Medium | High |

### Category 3: Document Lifecycle State

Published document mappings and drafts:

| Location | Contents | Sensitivity | Backup Priority |
|----------|----------|-------------|-----------------|
| `.doc-registry.json` | Doc ID → URL mappings | Medium | **Critical** |
| `.doc-state.json` | Document lifecycle state | Medium | **Critical** |
| `drafts/` | Generated changelogs | Low | Medium |
| `approved/` | Human-approved outputs | Medium | High |

### Category 4: Learning State

User preferences and corrections:

| Location | Contents | Sensitivity | Backup Priority |
|----------|----------|-------------|-----------------|
| `corrections/review_state.json` | Correction review progress | Low | High |
| `corrections/user_glossary.json` | Learned transcription fixes | Low | **Critical** |
| `corrections/propagation_queue.json` | Pending corrections | Low | High |

### Category 5: Secrets (Special Handling)

| Location | Contents | Sensitivity | Backup Priority |
|----------|----------|-------------|-----------------|
| `.env` | API keys, tokens | **Critical** | Exclude (re-provision) |
| Provider credentials in configs | OAuth tokens | **Critical** | Exclude (re-provision) |

---

## Functional Requirements

### FR-001: State Inventory Command

```bash
neut state inventory [--verbose] [--json]
```

Lists all state locations with:
- Path and existence status
- File count and total size
- Last modified timestamp
- Git tracking status
- Sensitivity classification

### FR-002: State Backup Command

```bash
neut state backup [--output <path>] [--encrypt] [--include-media]
```

Creates point-in-time backup:
- Default output: `~/.neut-backups/neut-state-{timestamp}.tar.gz`
- Encryption via age (modern, audited crypto)
- Excludes `.env` and large media by default
- Includes manifest with checksums

### FR-003: State Restore Command

```bash
neut state restore <backup-path> [--decrypt] [--dry-run]
```

Restores from backup:
- Validates manifest checksums
- Dry-run mode shows what would change
- Prompts before overwriting existing state
- Logs restoration actions

### FR-004: State Export Command

```bash
neut state export <category> --output <path>
```

Exports specific state category for sharing:
- Categories: `config`, `corrections`, `documents`, `sessions`
- Portable JSON format with schema version
- Redacts secrets automatically

### FR-005: State Encryption

- At-rest encryption using age with passphrase or key file
- Optional git-crypt integration for selective Git tracking
- Key stored in macOS Keychain / Linux secret-service / Windows Credential Manager

### FR-006: Document Sync State Integration

Published document state (`.doc-registry.json`, `.doc-state.json`) included in:
- State inventory
- Backup scope
- Export capabilities

Cross-reference: See [docflow-spec.md](../specs/docflow-spec.md) for bidirectional sync patterns.

---

## Git Integration Model

Agent state management is designed to be **Git-aware but Git-optional**. Git provides powerful primitives (version history, distributed sync, branch-based workflows) that complement state management without being a hard dependency.

### Why Git Matters for State

| Git Capability | State Management Benefit |
|----------------|-------------------------|
| **Version history** | Roll back to previous state, audit changes over time |
| **Distributed sync** | Clone state to new machines via `git clone` |
| **Branch isolation** | Experiment with state changes without affecting main |
| **Remote backup** | Push encrypted state to GitHub/GitLab for cloud backup |
| **Access control** | Leverage existing Git permissions for state access |
| **Diff/merge** | See what changed between state versions |

### The Three-Tier Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                     State Storage Tiers                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Tier 1: Git-Tracked (Encrypted)          Tier 2: Git-Ignored      │
│  ─────────────────────────────            ──────────────────       │
│  • config/people.md                       • inbox/raw/voice/       │
│  • config/initiatives.md                  • inbox/processed/       │
│  • .doc-registry.json                     • sessions/              │
│  • corrections/user_glossary.json         • .env (secrets)         │
│                                                                     │
│  → Encrypted via git-crypt                → Backed up separately   │
│  → Version history available              → May be large/sensitive │
│  → Syncs with git push/pull               → Local-only by default  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Tier 3: External Sync (Phase 2+)                                   │
│  ────────────────────────────────                                   │
│  • PostgreSQL for team state                                        │
│  • S3/GCS for large media backup                                    │
│  • Enterprise state service                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Git-Crypt for Transparent Encryption

[git-crypt](https://github.com/AGWA/git-crypt) enables transparent encryption of files in Git:

- Files appear encrypted in the repository (on GitHub, in `git log`, etc.)
- Files are automatically decrypted on authorized machines
- Non-authorized users see encrypted blobs
- Works with existing Git workflows (`commit`, `push`, `pull`)

**Configuration via `.gitattributes`:**
```gitattributes
# Encrypted state files (decrypted only on authorized machines)
tools/agents/config/people.md filter=git-crypt diff=git-crypt
tools/agents/config/initiatives.md filter=git-crypt diff=git-crypt
.doc-registry.json filter=git-crypt diff=git-crypt
.doc-state.json filter=git-crypt diff=git-crypt
tools/agents/inbox/corrections/user_glossary.json filter=git-crypt diff=git-crypt
```

**Authorization model:**
- GPG key-based: Each team member's GPG key is added to `.git-crypt/keys/`
- Symmetric key: Export key file for sharing (less secure, simpler)

### Git Policy by State Location

| Location | Git Policy | Rationale |
|----------|------------|-----------|
| `config/people.md` | **Encrypted** | Team roster benefits from version history |
| `config/initiatives.md` | **Encrypted** | Project list shared across team |
| `.doc-registry.json` | **Encrypted** | Document URLs valuable for continuity |
| `.doc-state.json` | **Encrypted** | Document lifecycle state |
| `user_glossary.json` | **Encrypted** | Learned corrections are valuable |
| `inbox/processed/` | Ignored | Too large, use backup instead |
| `inbox/raw/voice/` | Ignored | Binary media, too large |
| `sessions/` | Ignored | Sensitive chat history |
| `drafts/` | Ignored | Regenerated, not critical |
| `.env` | Ignored | Secrets, never commit |

### Git-Aware Commands

State management commands are Git-aware when running in a Git repository:

```bash
# Inventory shows Git tracking status
neut state inventory
  config/people.md           1.2 KB  [CRITICAL] git:encrypted
  inbox/processed/           1.1 MB  [CRITICAL] git:ignored
  sessions/                  296 KB  [HIGH]     git:untracked ⚠️

# Backup can commit and push
neut state backup --git-commit --git-push
  Creating backup...
  ✓ Committed: "state backup 2026-02-24T14:30"
  ✓ Pushed to origin/main

# Sync pulls latest state from Git
neut state sync
  Pulling latest from origin/main...
  ✓ config/people.md updated (3 new team members)
  ✓ user_glossary.json merged (12 new corrections)
```

### When to Use Git vs. External Backup

| Scenario | Recommendation |
|----------|----------------|
| Single developer, small team | Git-crypt for config, `neut state backup` for runtime |
| Team sharing config | Git-crypt with shared GPG keys |
| Large transcripts/media | External backup (S3, local NAS) |
| Compliance/audit requirements | Git for audit trail + PostgreSQL for access logs |
| Departing employee | `neut state export` + Git history preservation |

### Relationship to Code vs. State

NeutronOS treats code and state differently:

| Aspect | Code | Agent State |
|--------|------|-------------|
| **Source of truth** | Git repository | Filesystem (optionally Git-backed) |
| **Versioning** | Always tracked | Optionally tracked |
| **Sharing** | Public/team repo | Encrypted, access-controlled |
| **Merge conflicts** | Manual resolution | Schema-aware auto-merge |
| **Backup frequency** | On commit | On change or scheduled |

The key insight: **State is runtime data that evolves differently than code.** Some state (config, corrections) benefits from Git's versioning. Other state (transcripts, sessions) is better suited to backup/restore workflows.

---

## Phased Implementation

### Phase 0: Local Backup (MVP) — Target: 1 week

**Deliverables:**
- `neut state inventory` command
- `neut state backup` with age encryption
- `neut state restore` with validation
- State location constants in `tools/agents/state/locations.py`

**Success Criteria:**
- Developer can backup and restore all critical state
- Backup is encrypted by default
- Restore works on fresh machine

### Phase 1: Git-Backed State — Target: 2 weeks

**Deliverables:**
- git-crypt integration for selective encryption
- `.gitattributes` patterns for encrypted state
- `neut state sync` for push/pull
- Documentation for team onboarding

**Success Criteria:**
- Selected state tracked in Git (encrypted)
- Only authorized machines can decrypt
- Version history available

### Phase 2: Team Sync — Target: 4 weeks

**Deliverables:**
- PostgreSQL schema for state storage
- `neut state share` command
- Access control (owner, editor, viewer)
- Conflict resolution for concurrent edits

**Success Criteria:**
- Team can share configuration state
- Access control enforced
- Audit log captures access

### Phase 3: Enterprise — Target: 8 weeks

**Deliverables:**
- RBAC integration (LDAP/SAML)
- State snapshot API for forensics
- Compliance export (departing employee)
- Multi-tenant isolation

**Success Criteria:**
- Organization can enforce state policies
- Historical state replay possible
- IP retention on employee departure

### Phase 4: Retention & Compliance — Target: 2 weeks (can parallelize with Phase 1)

**Deliverables:**
- `neut state retention` status command
- `neut state cleanup` with dry-run and audit logging
- `config/retention.yaml` configuration file
- Retention audit log in JSONL format
- Unify existing retention mechanisms (audio clips, echo cache)

**Success Criteria:**
- Automated cleanup respects configured policies
- All deletions logged for audit
- Disk usage stays bounded over time
- Legal hold flag prevents all deletion

---

## Security Considerations

### Encryption

- **Algorithm**: age (X25519 + ChaCha20-Poly1305)
- **Key Management**: Platform keychain integration
- **Passphrase**: PBKDF2 with high iteration count

### Access Control (Phase 2+)

- **Authentication**: Delegated to Git/SSO provider
- **Authorization**: Per-category permissions
- **Audit**: All state access logged with timestamp, user, action

### Secrets Handling

- Secrets excluded from backup by default
- `.env` files require re-provisioning
- OAuth tokens require re-authentication

---

## Success Metrics

| Metric | Phase 0 Target | Phase 2 Target | Phase 4 Target |
|--------|----------------|----------------|----------------|
| Backup creation time | < 30 seconds | < 30 seconds | < 30 seconds |
| Restore success rate | 100% | 100% | 100% |
| State inventory accuracy | 100% coverage | 100% coverage | 100% coverage |
| Encryption coverage | All sensitive state | All sensitive state | All sensitive state |
| Audit log retention | N/A | 90 days | 90 days |
| Retention policy compliance | N/A | N/A | 100% of categories |
| Disk usage growth | Unbounded | Unbounded | < 10% monthly |
| Cleanup audit coverage | N/A | N/A | 100% logged |

---

## Dependencies

- **age**: Encryption tool (Go implementation)
- **git-crypt**: Transparent Git encryption (Phase 1)
- **PostgreSQL**: Team state storage (Phase 2)
- **Platform keychain APIs**: Secure key storage

---

## Open Questions

1. Should raw voice memos be included in backup by default? (Currently excluded due to size)
2. ~~What's the retention policy for state backups?~~ → Addressed in Data Retention section
3. How do we handle state schema migrations between NeutronOS versions?
4. Should we support S3/GCS as backup targets in Phase 1?
5. Should retention cleanup require explicit opt-in, or run automatically after initial setup?
6. How do we handle retention for data that spans multiple categories (e.g., a transcript with embedded corrections)?
7. What's the notification UX when cleanup deletes significant data (e.g., "Freed 500MB")?

---

## Appendix A: State Location Reference

Complete inventory of all agent state locations:

```
Neutron_OS/
├── .doc-registry.json          # Published doc URL mappings
├── .doc-state.json             # Document lifecycle state
├── .doc-workflow.yaml          # DocFlow provider config
├── .neut/                      # CLI setup state
│   └── setup-state.json
├── tools/agents/
│   ├── config/                 # Facility-specific config
│   │   ├── people.md
│   │   ├── initiatives.md
│   │   └── models.yaml
│   ├── inbox/
│   │   ├── raw/
│   │   │   ├── voice/          # Voice memo files
│   │   │   ├── gitlab/         # GitLab exports
│   │   │   └── teams/          # Teams transcripts
│   │   ├── processed/          # Transcripts, signals, corrections
│   │   ├── state/              # Briefing state, sync state
│   │   │   ├── briefing_state.json
│   │   │   └── docflow_sync.json
│   │   └── corrections/        # Review state, glossary
│   │       ├── review_state.json
│   │       ├── user_glossary.json
│   │       └── propagation_queue.json
│   ├── drafts/                 # Generated changelogs
│   ├── approved/               # Human-approved outputs
│   └── sessions/               # Chat session JSON
└── .env                        # Secrets (excluded from backup)
```

---

## Appendix B: Related Documents

- [NeutronOS Master PRD](neutron-os-executive-prd.md)
- [Agent State Management Tech Spec](../specs/agent-state-management-spec.md)
- [DocFlow Specification](../specs/docflow-spec.md) — Document lifecycle and sync
- [Data Architecture Specification](../specs/data-architecture-spec.md)
- [Sense & Synthesis MVP Spec](../specs/sense-synthesis-mvp-spec.md)
