# DocFlow Architecture — Multi-Backend, Resilient Document Management

## Overview

DocFlow is a provider-agnostic document lifecycle management system for technical PRDs and specifications. It handles:

- **Multi-backend storage** (SharePoint, Google Drive, S3, local filesystem)
- **Multi-format conversion** (Word .docx ↔ Markdown, LaTeX, HTML via pandoc or native converters)
- **Resilient workflows** (recovery from missing files, corruption, network failures)
- **Metadata preservation** (comments, tracked changes, images extracted separately)
- **Automated cleanup** (fixes for pandoc conversion artifacts)

## Architecture

### 1. **Provider Abstractions** (Backend-Agnostic)

Located in `tools/docflow/providers/base.py`:

```
BaseProvider (ABC)
├── GenerationProvider  — Convert .md → publishable format (docx, pdf, html)
├── StorageProvider     — Upload/download/manage artifacts on backend
├── FeedbackProvider    — Extract comments/reviews from published docs
├── NotificationProvider — Send alerts to stakeholders
└── EmbeddingProvider   — Index/search document content
```

**Current Implementations:**
- `sharepoint.py` — SharePoint/OneDrive via Microsoft Graph API (device-code MSAL auth)

**Planned Implementations:**
- `box.py` — Box.com via REST API (OAuth 2.0 auth) — High Priority
- `google_drive.py` — Google Drive via Google API (OAuth 2.0 auth)
- `s3.py` — AWS S3 via boto3 (IAM auth)
- `local.py` — Filesystem (for testing/CI)

### 2. **Converter Abstractions** (Format-Agnostic)

Located in `tools/docflow/converters/base.py`:

```
BaseConverter (ABC)
├── pandoc.py       — Pandoc wrapper (docx↔md, md↔latex, md↔html, etc.)
├── latex.py        — Native LaTeX support (future)
└── html.py         — Native HTML support (future)
```

**Key Methods:**
- `convert()` — Transform between formats
- `extract_media()` — Pull images/diagrams
- `extract_comments()` — Pull reviewer feedback
- `extract_metadata()` — Pull title, author, created, modified, etc.

### 3. **Document Model** (Semantic Representation)

Located in `tools/docflow/models/document.py`:

```python
Document
├── title, subtitle, abstract
├── sections: List[Section]  # Recursive heading hierarchy
│   ├── level (1-6)
│   ├── images: List[Image]
│   │   ├── path (relative)
│   │   ├── alt_text
│   │   └── source (provider name)
│   └── links: List[Link]
│       ├── text, url
│       ├── is_internal
│       └── is_broken
├── author, created, modified, version
└── metadata, front_matter
```

**Usage:** Cleanup and validation logic works on this semantic model, not raw strings.

### 4. **Cleanup Framework** (`cleanup.py`)

Fixes common pandoc conversion bugs:

| Issue | Fix |
|-------|-----|
| Broken SharePoint URLs | → text references `(Published in SharePoint)` |
| Missing image alt text | → inferred from filename/context |
| Nested blockquotes (`> >`) | → clean bullet lists or single `>` |
| Inline pixel styles | → removed entirely |
| Diagram rendering failures | → mermaid placeholder |

**Design:** Works on markdown text directly, provider-agnostic, idempotent (safe to run multiple times).

### 5. **Validation Framework** (`validation.py`)

Detects all failure modes and suggests recovery:

```
Publication States:
├── unknown       — No .md or .docx found
├── draft         — .md exists, no source .docx
├── orphan        — .docx exists, no .md
├── published     — Both exist, should be in-sync
└── out-of-sync   — Both exist but checksums changed
```

**Validations:**
- File integrity (empty files, corruption)
- Metadata consistency (registry vs. disk)
- Image references (broken links)
- Comments preservation

**Recovery Suggestions:**
- Draft → first_publish (convert .md → .docx, upload)
- Orphan → first_ingest (pull .docx → convert → clean → commit)
- Out-of-sync → 3-way merge or user choice

### 6. **Resilience Workflows** (Automated State Transitions)

#### `scripts/first_publish.py`

**Workflow:** Local markdown → published Word document

```
Draft (local .md)
    ↓
1. Validate markdown exists
2. Run cleanup
3. Convert .md → .docx (pandoc reverse)
4. Upload to SharePoint (via provider)
5. Archive source .docx locally
6. Create registry entry
7. Commit to git
    ↓
Published (.md + .docx + registry entry + comments metadata)
```

#### `scripts/first_ingest.py`

**Workflow:** Orphan Word document → tracked markdown

```
Orphan (SharePoint .docx, no local .md)
    ↓
1. Pull .docx from SharePoint
2. Convert .docx → .md (pandoc)
3. Extract media (images → media/)
4. Extract comments (.comments-*.md)
5. Run cleanup
6. Archive source .docx locally
7. Create registry entry
8. Validate & commit
    ↓
Published (.md + .docx + images + comments metadata)
```

### 7. **Registry** (`models.py` + `registry.py`)

Enhanced document state tracking:

```json
{
  "doc_id": "medical-isotope-prd",
  "source_path": "docs/prd/medical-isotope-prd.md",
  "status": "published",
  "publication_status": "published",
  "source_of_truth": "docx",
  "first_published_date": "2026-02-25T...",
  "last_synced": "2026-02-25T...",
  "docx_checksum": "sha256:abc123...",
  "md_checksum": "sha256:def456...",
  "metadata_checksum": "sha256:ghi789...",
  "published": {
    "storage_id": "...",
    "url": "https://...",
    "version": "v2",
    "published_at": "2026-02-25T...",
    "commit_sha": "abc123def456"
  },
  "pending_comments": [
    {
      "comment_id": "c1",
      "author": "Alice",
      "timestamp": "2026-02-24T...",
      "text": "Improve layout",
      "resolved": false
    }
  ]
}
```

## Failure Modes & Recovery

### Scenario 1: Source .docx Deleted/Moved

**Detection:** Registry entry exists but source .docx not found.

**Fallback:**
1. Check git history for previous version
2. Offer to re-pull from SharePoint (if URL is current)
3. Rebuild from .md (convert back to .docx)

### Scenario 2: .md File Deleted

**Detection:** Registry entry exists but .md not found.

**Recovery:**
```bash
docflow first_ingest <doc_id> --rebuild-from-docx
```

### Scenario 3: .docx Moved on SharePoint (URL broken)

**Detection:** Validation fails to re-download.

**Recovery:**
```bash
docflow first_ingest <doc_id> --local-docx /path/to/moved/file.docx
```

### Scenario 4: Comments Lost in Conversion

**Design:** Comments extracted separately to `.comments-<doc_id>.md` and stored in registry.

**Preservation:** Never deleted during round-trips; manually reconciled if needed.

### Scenario 5: .md and .docx Out-of-Sync

**Detection:** Checksums in registry differ from disk.

**Recovery:**
1. User chooses source of truth (.md or .docx)
2. Merge or overwrite based on choice
3. Run cleanup if converting from .docx
4. Update checksums and registry

## Testing

Comprehensive test suite in `tools/docflow/tests/test_resilience.py`:

- **Cleanup robustness** — All pandoc artifacts handled correctly
- **Validation framework** — All states detected, recovery suggested
- **State transitions** — draft → published → published, orphan → published, etc.
- **Idempotence** — Cleanup safe to run multiple times
- **Document model** — Semantic validation, traversal

Run tests:
```bash
pytest tools/docflow/tests/test_resilience.py -v
```

## Usage Examples

### Example 1: Publish a Draft PRD

```bash
# Create local .md
cat > docs/prd/experiment-manager-prd.md << 'EOF'
# Experiment Manager PRD
...
EOF

# Publish
python tools/docflow/scripts/first_publish.py experiment-manager-prd --provider sharepoint

# Result: experiment-manager-prd.docx uploaded to SharePoint, registry created
```

### Example 2: Ingest an Orphan Word Doc

```bash
# Someone has a .docx on SharePoint but it's not in the repo

python tools/docflow/scripts/first_ingest.py experiment-manager-prd \
  "https://utk.sharepoint.com/sites/.../experiment-manager-prd.docx"

# Result: .md created, images extracted, comments preserved, registered
```

### Example 3: Validate All Documents

```bash
python tools/docflow/scripts/docflow_scan.py

# Output:
# ✓ medical-isotope-prd: published
# ⚠️ experiment-manager-prd: draft (missing source .docx)
# ⚠️ reactor-ops-log-prd: orphan (missing .md)
# ...
```

### Example 4: Recover from Corruption

```bash
# If .md was accidentally deleted
git checkout docs/prd/medical-isotope-prd.md

# Or rebuild from source .docx
python tools/docflow/scripts/first_ingest.py medical-isotope-prd \
  --local-docx docs/prd/_source/medical-isotope-prd.docx
```

## Round-Trip Workflow

**Goal:** Edit .md in repo, republish to Word without losing formatting, comments, TOC.

**Merge-based approach:**
1. Extract changes from .md (git diff)
2. Load source .docx (python-docx)
3. Merge changes into document programmatically
4. Preserve Word-generated TOC, tracked changes, comments
5. Upload revised .docx to SharePoint

**Status:** Foundation ready; merge logic implementation pending.

## Provider Extension

To add a new backend:

1. Create `tools/docflow/providers/<backend>.py`
2. Inherit from `StorageProvider` (in `base.py`)
3. Implement abstract methods: `upload()`, `download()`, `get_canonical_url()`, `list_artifacts()`, `delete()`, `move()`
4. Implement auth (OAuth2, JWT, API keys, etc.)
5. Handle provider-specific quirks (path resolution, shared links, versioning, etc.)
6. Register in provider factory
7. Add tests to `test_resilience.py`

### Box.com Example (`box.py`)

Box is an enterprise collaboration platform with:
- **Auth**: OAuth 2.0 (user-initiated or service account JWT)
- **File IDs**: Opaque identifiers (not path-based like SharePoint)
- **Shared links**: Generated via API (separate from file metadata)
- **Comments**: Extracted via API (not embedded in file)
- **Metadata**: Custom JSON properties on file object
- **Version history**: Automatic via Box API

**Key differences from SharePoint:**
- SharePoint uses path-based URLs; Box uses file/folder IDs
- SharePoint embeds comments in Word; Box stores comments separately
- Box webhooks enable reactive sync (trigger DocFlow on file change)
- Box metadata templates useful for storing DocFlow state

**Round-trip strategy for Box (future):**
1. Pull .docx from Box
2. Convert to .md + extract comments
3. User edits .md in repo
4. Merge changes back into .docx (preserving Box version history, permissions)
5. Upload revised .docx
6. Update DocFlow metadata on Box file

Similar pattern for Google Drive, S3, etc. The `StorageProvider` ABC ensures consistency across backends.

## Future Enhancements

### High Priority
- [ ] **Box.com provider** (skeleton in place, awaiting OAuth2 implementation)
- [ ] Merge-based round-trip (.md → .docx with formatting preservation)
- [ ] Box-specific: Webhook-based reactive sync (trigger DocFlow on file change)

### Medium Priority
- [ ] Google Drive provider implementation
- [ ] AWS S3 provider implementation
- [ ] Automated diff/change detection (.md vs .docx)
- [ ] Version history visualization
- [ ] Stakeholder notification on publication

### Lower Priority
- [ ] LaTeX native converter
- [ ] Embedded feedback dashboard (PRD comments UI)
- [ ] Markdown linting (orphan sections, broken refs, etc.)
- [ ] Box-specific: Custom metadata template management
