# Interactive OneDrive Publisher Usage Guide

The refactored `publish_to_onedrive.py` is now **fully interactive** and works with **any markdown files in docs/**, including nested folders.

## Quick Start

### 1. Set Your Credentials

```bash
export MS_GRAPH_CLIENT_ID="your-app-id"
export MS_GRAPH_CLIENT_SECRET="your-secret"
export MS_GRAPH_TENANT_ID="your-tenant-id"
export ONEDRIVE_FOLDER_ID="your-folder-id"  # optional, defaults to root
```

### 2. Run the Publisher

**Interactive Mode (Recommended)**
```bash
python3 docs/_tools/publish_to_onedrive.py
```

You'll see a menu:
```
📚 MARKDOWN FILE DISCOVERY
======================================================================

📁 Documentation folders:

  [1] prd                      (8 files)
  [2] research                 (10 files)
  [3] specs                    (3 files)
  [4] adr                      (25 files)
  [0] All files                (46 files)
  [S] Search by name

Select folder [0-4], [S] for search, or [Q] to quit:
```

---

## Usage Modes

### 📁 Interactive Menu (Default)

```bash
python3 docs/_tools/publish_to_onedrive.py
```

Browse folders, select files, confirm, and publish. Best for exploring what's available.

### 🎯 Publish Specific Folder

```bash
# Publish all PRDs
python3 docs/_tools/publish_to_onedrive.py docs/prd/*.md

# Publish all specs
python3 docs/_tools/publish_to_onedrive.py docs/specs/*.md

# Publish research
python3 docs/_tools/publish_to_onedrive.py docs/research/*.md
```

### 🔍 Search by Pattern

```bash
# Find and publish files matching "prd"
python3 docs/_tools/publish_to_onedrive.py --search prd

# Find files containing "experiment"
python3 docs/_tools/publish_to_onedrive.py --search experiment

# Find files containing "architecture"
python3 docs/_tools/publish_to_onedrive.py --search architecture
```

### 🌍 Recursive Glob (All Docs)

```bash
# Publish everything in docs/
python3 docs/_tools/publish_to_onedrive.py docs/**/*.md

# Publish all markdown anywhere (use with caution!)
python3 docs/_tools/publish_to_onedrive.py "docs/**/*.md"
```

### 📋 Publish Multiple Patterns

```bash
# Publish PRDs and specs together
python3 docs/_tools/publish_to_onedrive.py docs/prd/*.md docs/specs/*.md

# Publish specific files
python3 docs/_tools/publish_to_onedrive.py docs/prd/experiment-manager-prd.md docs/research/deeplynx-assessment.md
```

---

## Folder Structure

The publisher respects your `docs/` folder hierarchy:

```
docs/
├── prd/
│   ├── experiment-manager-prd.md
│   ├── data-platform-prd.md
│   └── ...
├── specs/
│   ├── neutron-os-master-tech-spec.md
│   └── ...
├── research/
│   ├── deeplynx-assessment.md
│   └── ...
└── adr/
    ├── ADR-001-streaming-first.md
    └── ...
```

When you publish, documents are organized the same way in `docs/_tools/generated/`:

```
generated/
├── prd/
│   ├── experiment-manager-prd.docx
│   └── ...
├── specs/
│   └── ...
└── research/
    └── ...
```

OneDrive file names are friendly:
- `prd > experiment-manager-prd.docx`
- `specs > data-architecture-spec.docx`
- `research > deeplynx-assessment.docx`

---

## Examples

### Publish All PRDs (8 documents)

```bash
python3 docs/_tools/publish_to_onedrive.py docs/prd/*.md
```

Output:
```
📋 Found 8 file(s):

  [1] prd/experiment-manager-prd.md
  [2] prd/data-platform-prd.md
  [3] prd/reactor-ops-log-prd.md
  [4] prd/neutron-os-executive-prd.md
  [5] prd/scheduling-system-prd.md
  [6] prd/compliance-tracking-prd.md
  [7] prd/analytics-dashboards-prd.md
  [8] prd/medical-isotope-prd.md

Publish these files? [y/N]: y

🚀 ONEDRIVE DOCUMENT PUBLISHER
======================================================================

  📝 Generating experiment-manager-prd.md...
  ✅ Generated experiment-manager-prd.docx
  📤 Uploading prd > experiment-manager-prd.docx...
  ✅ Uploaded (ID: 01AB2CD...)
  🔗 Creating shareable link...
  ✅ Link created: https://utexas-my.sharepoint.com/...
  🔐 Setting permissions for utexas.edu...
  ✅ Permissions set
✅ Published: prd > experiment-manager-prd.docx

[... repeats for other files ...]

📊 PUBLICATION SUMMARY
======================================================================

✅ prd > experiment-manager-prd.docx
   https://utexas-my.sharepoint.com/...
✅ prd > data-platform-prd.docx
   https://utexas-my.sharepoint.com/...
[... etc ...]

📋 Link manifest saved to docs/_tools/onedrive_manifest.json
```

### Search for Architecture Documents

```bash
python3 docs/_tools/publish_to_onedrive.py --search architecture
```

Output:
```
Enter search pattern (e.g., 'prd' or 'experiment'): architecture

📋 Found 4 match(es):

  [1] research/deeplynx-assessment.md
  [2] specs/digital-twin-architecture-spec.md
  [3] specs/data-architecture-spec.md
  [4] adr/ADR-007-streaming-first.md

Publish these files? [y/N]: y
```

### Interactive Menu

```bash
python3 docs/_tools/publish_to_onedrive.py
```

Menu:
```
📚 MARKDOWN FILE DISCOVERY
======================================================================

📁 Documentation folders:

  [1] prd                      (8 files)
  [2] research                 (10 files)
  [3] specs                    (3 files)
  [4] adr                      (25 files)
  [0] All files                (46 files)
  [S] Search by name

Select folder [0-4], [S] for search, or [Q] to quit: 1
```

---

## Output Files

### `onedrive_manifest.json`

Every publish run creates/updates `docs/_tools/onedrive_manifest.json`:

```json
{
  "published_at": "2026-01-28 16:45:23",
  "documents": {
    "prd > experiment-manager-prd.docx": "https://utexas-my.sharepoint.com/personal/bdb3732_eid_utexas_edu/Documents/prd%20%3E%20experiment-manager-prd.docx?web=1",
    "prd > data-platform-prd.docx": "https://utexas-my.sharepoint.com/personal/bdb3732_eid_utexas_edu/Documents/prd%20%3E%20data-platform-prd.docx?web=1",
    ...
  }
}
```

### Generated `.docx` Files

Local copies with updated links in `docs/_tools/generated/`:

```
docs/_tools/generated/
├── prd/
│   ├── experiment-manager-prd.docx
│   ├── data-platform-prd.docx
│   └── ...
├── specs/
│   └── ...
└── research/
    └── ...
```

---

## Advanced Features

### Cross-Document Linking

The publisher automatically updates all markdown links (e.g., `[Experiment Manager](experiment-manager-prd.md)`) to point to the OneDrive URLs in the generated `.docx` files.

### Sharing Permissions

All published files are automatically shared with:
- ✅ UT Austin domain users (`utexas.edu`)
- ✅ Anyone with the shareable link

Set via the `MS_GRAPH_TENANT_ID` environment variable.

### Folder Organization

OneDrive folder names mirror your local structure:
- `docs/prd/` → OneDrive `prd/`
- `docs/specs/` → OneDrive `specs/`
- `docs/research/` → OneDrive `research/`

This makes it easy to find published documents.

---

## Troubleshooting

### "Authentication failed"

Check credentials:
```bash
echo "CLIENT_ID: $MS_GRAPH_CLIENT_ID"
echo "SECRET: $MS_GRAPH_CLIENT_SECRET"
echo "TENANT: $MS_GRAPH_TENANT_ID"
```

### "Upload failed: 401"

Verify permissions in Azure portal:
- ✅ `Files.ReadWrite.All`
- ✅ `Sites.ReadWrite.All`
- ✅ "Grant admin consent"

### "No markdown files found"

Check working directory:
```bash
cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS
ls docs/prd/*.md
```

### "File not found" in glob

Quote your patterns:
```bash
# Good
python3 docs/_tools/publish_to_onedrive.py "docs/**/*.md"

# Bad (shell expands glob)
python3 docs/_tools/publish_to_onedrive.py docs/**/*.md
```

---

## Tips

1. **Start interactive** → Explore what's available before writing scripts
2. **Use search** for one-off publications (e.g., `--search deeplynx`)
3. **Check manifest** → See all published URLs in `onedrive_manifest.json`
4. **Re-publish anytime** → Upload same file again to update it
5. **Share the manifest** → Send JSON file to colleagues who need the URLs

---

## Setup Reminders

If you haven't set up yet:

1. **Create Azure AD app** → https://portal.azure.com
   - Register app
   - Grant `Files.ReadWrite.All` + `Sites.ReadWrite.All`
   - Get CLIENT_ID, CLIENT_SECRET, TENANT_ID

2. **Set environment variables**
   ```bash
   export MS_GRAPH_CLIENT_ID="..."
   export MS_GRAPH_CLIENT_SECRET="..."
   export MS_GRAPH_TENANT_ID="..."
   ```

3. **Run publisher**
   ```bash
   python3 docs/_tools/publish_to_onedrive.py
   ```

See `PUBLISH_CHECKLIST.md` for detailed setup.
