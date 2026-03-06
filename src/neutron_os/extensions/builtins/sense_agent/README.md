# neut sense — Signal Ingestion Pipeline

Collects signals from multiple sources (voice memos, GitLab, transcripts, freetext notes) and synthesizes them into structured changelogs.

## Quick Start

```bash
# From repo root
cd Neutron_OS

# Check pipeline status
python -m tools.extensions.builtins.sense.cli status

# Run all extractors on inbox data
python -m tools.extensions.builtins.sense.cli ingest --source all

# Synthesize into changelog draft
python -m tools.extensions.builtins.sense.cli draft
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SIGNAL SOURCES                              │
├──────────────┬──────────────┬───────────────┬──────────────────┤
│ Voice Memos  │ GitLab Diffs │ Teams Transc. │ Freetext Notes   │
│ (iPhone)     │ (weekly exp) │ (.vtt files)  │ (.md/.txt)       │
└──────┬───────┴──────┬───────┴───────┬───────┴─────────┬────────┘
       │              │               │                 │
       ▼              ▼               ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                   inbox/raw/                                     │
│    voice/     gitlab/     teams/      *.md, *.txt                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    neut sense ingest
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│   EXTRACTORS          →        CORRELATOR        →     SIGNALS  │
│   voice.py (Whisper)           (people/init)          inbox/    │
│   gitlab_diff.py               resolution            processed/ │
│   transcript.py                                                  │
│   freetext.py (LLM)                                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    neut sense draft
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│   SYNTHESIZER        →       drafts/                             │
│   Groups by initiative       changelog_YYYY-MM-DD.md             │
│   Deduplicates signals       weekly_summary.md                   │
└──────────────────────────────────────────────────────────────────┘
```

## Getting Data Into the Inbox

### Option 1: HTTP Ingestion Server (Recommended for Org-Wide)

Run the HTTP server to accept uploads from any device on the network:

```bash
# Start server (default port 8765)
python -m tools.extensions.builtins.sense.cli serve

# Custom port
python -m tools.extensions.builtins.sense.cli serve --port 8080
```

Then access `http://<your-ip>:8765/` from any browser to:
- Drag-and-drop files
- Submit quick text notes
- View inbox status

#### iOS Shortcut for Voice Memos

Create an iOS Shortcut to upload voice memos directly:

1. **Open Shortcuts app** on iPhone
2. **Create new Shortcut** with these actions:

```
Action 1: Get Latest Voice Memo
  - From: Voice Memos
  - Order: Latest First
  - Limit: 1

Action 2: Get Contents of File
  - Input: Voice Memo

Action 3: URL
  - http://<SERVER_IP>:8765/upload

Action 4: Get Contents of URL
  - Method: POST
  - Request Body: Form
  - Add new field:
    - Key: file
    - Value: (select Voice Memo file)
```

3. **Add to Home Screen** or trigger via Siri: "Upload voice memo"

#### Keep Server Running (macOS)

Create `~/Library/LaunchAgents/com.neutronos.sense-server.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neutronos.sense-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/ben/Projects/UT_Computational_NE/.venv/bin/python</string>
        <string>-m</string>
        <string>tools.extensions.builtins.sense.cli</string>
        <string>serve</string>
        <string>--port</string>
        <string>8765</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/ben/Projects/UT_Computational_NE/Neutron_OS</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/neutronos-sense.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/neutronos-sense.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.neutronos.sense-server.plist
```

### Option 2: Manual File Placement

Copy files directly to inbox:
```bash
# Voice memos
cp ~/Downloads/memo.m4a tools/agents/inbox/raw/voice/

# Teams transcripts
cp ~/Downloads/meeting.vtt tools/agents/inbox/raw/teams/

# Freetext notes
cp ~/Downloads/notes.md tools/agents/inbox/raw/
```

### Option 3: GitLab Export (Automatic)

GitLab data flows via the weekly export job:
```bash
# Manual run
python tools/gitlab_tracker_export.py --output-dir tools/exports/

# Automatic via launchd (see tools/com.utcomputational.gitlab-export.plist)
```

## Extractor Dependencies

| Extractor | Dependency | Install |
|-----------|------------|---------|
| voice | openai-whisper | `pip install openai-whisper` |
| voice (diarization) | pyannote.audio | `pip install pyannote.audio` + HF_TOKEN |
| freetext (LLM) | anthropic or openai | `pip install anthropic` |
| gitlab | - | None (uses JSON exports) |
| transcript | - | None (parses .vtt/.srt) |

Install voice dependencies:
```bash
pip install openai-whisper
# Optional: for speaker identification
pip install pyannote.audio
export HF_TOKEN="your-huggingface-token"
```

## Configuration

Copy and customize:
```bash
cp -r tools/agents/config.example tools/agents/config
```

Edit `config/people.md` and `config/initiatives.md` for entity resolution.

## Commands

| Command | Description |
|---------|-------------|
| `neut sense status` | Show inbox/processed/drafts counts |
| `neut sense ingest --source all` | Run all extractors |
| `neut sense ingest --source voice` | Process voice memos only |
| `neut sense ingest --source gitlab` | Process GitLab diffs only |
| `neut sense ingest --source prd` | Fetch PRD comments from OneDrive |
| `neut sense draft` | Synthesize signals into changelog |
| `neut sense serve` | Start HTTP ingestion server |

## PRD Comments (Office 365 / OneDrive)

To enable PRD comment extraction from Word documents:

### Azure AD Setup

1. Go to https://portal.azure.com → Azure Active Directory → App registrations
2. New registration:
   - Name: `NeutronOS Sense`
   - Supported account types: Single tenant
3. Under API permissions, add:
   - Microsoft Graph → `Files.Read.All`
   - Microsoft Graph → `Sites.Read.All`
4. Create a client secret under Certificates & secrets

### Environment Variables

```bash
export AZURE_CLIENT_ID="your-app-id"
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_SECRET="your-secret"  # Optional for background jobs
```

### Configuration

Edit `inbox/raw/prd_comments_config.json`:
```json
{
  "folder_path": "/Documents/NeutronOS/PRDs",
  "days_back": 14,
  "status_filter": "In Review"
}
```

### First Run (Interactive)

Without `AZURE_CLIENT_SECRET`, the extractor uses device code flow:
```bash
neut sense ingest --source prd
# Follow the device login prompt in your browser
```

## Workflow

1. **Collect** — Voice memos, notes, transcripts arrive in `inbox/raw/`
2. **Ingest** — `neut sense ingest` extracts signals to `inbox/processed/`
3. **Synthesize** — `neut sense draft` creates changelog in `drafts/`
4. **Review** — Human reviews and edits drafts
5. **Approve** — Move to `approved/` for publishing

## Troubleshooting

### "No voice memos found"
Check that files exist in `tools/agents/inbox/raw/voice/` and have supported extensions (.m4a, .mp3, .wav).

### "openai-whisper not installed"
```bash
pip install openai-whisper
```

### Server not accessible from iPhone
- Ensure firewall allows port 8765
- Use `ifconfig | grep "inet "` to find your LAN IP
- iPhone and server must be on same network

### Empty transcription
The base Whisper model may struggle with accents or low-quality audio. Try:
```python
# In voice.py, change model_size
extraction = extractor.extract(audio_file, model_size="medium")
```
