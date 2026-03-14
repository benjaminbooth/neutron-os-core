# NeutronOS Agent Architecture

---

## Context: What Already Exists

The Neutron_OS repo has a well-designed architecture that this agent work must
respect and extend, not replace:

```
Neutron_OS/
  docs/requirements/
    prd_neutron-os-executive.md     # Platform vision (modular, reactor-agnostic)
    prd_neut-cli.md                 # CLI with noun-verb: neut log|sim|model|twin|data|chat
    prd_compliance-tracking.md      # Audit automation module
    prd_medical-isotope.md          # Isotope workflow module
    prd_experiment-manager.md       # Experiment management module
    ...
  docs/specs/
    neut-cli-spec.md                # Rust CLI, clap v4, offline-first, WASM plugins
    data-architecture-spec.md       # Medallion lakehouse (Iceberg, DuckDB, Dagster)
    ...
  plugins/
    (stub) plugin-triga/            # Reactor-specific logic
    (stub) plugin-msr/
    (stub) plugin-mit-loop/
  tools/
    exports/                        # Weekly GitLab JSON dumps
    tracker/                        # Program tracker build scripts
    agents/inbox/                   # Agent sensing inbox (empty, ready)
  services/                         # (stub) Backend services
  packages/                         # (stub) Shared libraries
```

Key design decisions already made:
- **`neut` CLI** is the unified interface (Rust, noun-verb pattern)
- **Plugins** handle reactor-specific logic (TRIGA, MSR, MIT Loop)
- **meeting-intake** already specifies Teams → Transcribe → Extract → GitLab
- **Offline-first** is a hard requirement (nuclear facilities lose network)
- **Model-agnostic** — no vendor lock-in on LLM provider

---

## What We're Adding: Neut Sense

A new CLI noun (`neut sense`) that extends the existing `neut` command structure. Neut Sense is the
agentic module for continuous program awareness — ingesting signals from multiple
sources, extracting structured information, and maintaining program state.

### CLI Design (follows existing noun-verb pattern)

```bash
# ─── INGEST: Pull signals from sources ───
neut sense ingest                     # Process all new items in inbox
neut sense ingest --source voice      # Process only voice memos
neut sense ingest --source teams      # Process only Teams recordings
neut sense ingest --source gitlab     # Process latest GitLab export
neut sense ingest --source text       # Process freetext drops (notes, emails)

# ─── DRAFT: Synthesize signals into human-readable summaries ───
neut sense draft                      # Generate weekly status draft
neut sense draft --scope tracker      # Draft tracker update only
neut sense draft --scope issues       # Draft GitLab/Linear issue updates only
neut sense draft --scope minutes      # Draft meeting minutes only

# ─── REVIEW: Human-in-the-loop approval ───
neut sense review                     # Open latest draft in $EDITOR
neut sense review --approve           # Approve current draft
neut sense review --reject            # Reject and discard

# ─── PUBLISH: Apply approved changes ───
neut sense publish                    # Push approved changes to targets
neut sense publish --target onedrive  # Push tracker to SharePoint/OneDrive
neut sense publish --target gitlab    # Apply issue updates to GitLab
neut sense publish --target linear    # Apply issue updates to Linear

# ─── HEARTBEAT: Proactive sensing daemon ───
neut sense heartbeat                  # Run heartbeat checks now
neut sense heartbeat --start          # Start daemon (launchd/systemd)
neut sense heartbeat --stop           # Stop daemon
neut sense heartbeat --status         # Show daemon status + last run

# ─── STATUS: Current program state ───
neut sense status                     # Show program overview
neut sense status --stale             # Show items with no signal in 14+ days
neut sense status --people            # Show per-person activity summary
```

### Relationship to Existing Modules

```
neut log    — Reactor operations logging        (facility-facing)
neut sim    — Simulation orchestration           (facility-facing)
neut model  — Surrogate model management         (facility-facing)
neut twin   — Digital twin state                 (facility-facing)
neut data   — Data platform queries              (facility-facing)
neut chat   — Agentic assistant (interactive)    (facility-facing)
neut sense  — Program awareness (proactive)      (team-facing)     ← NEW
neut ext    — Extension management               (platform-facing)
neut infra  — Infrastructure management          (platform-facing)
```

Neut Sense is unique: it's the only noun that runs proactively (heartbeat) and
synthesizes across sources rather than querying a single system. But it follows
the same patterns: offline-first, human-in-the-loop for writes, JSON/table
output formats.

---

## Relationship to `meeting-intake`

The existing `tools/meeting-intake/` tool already specifies the Teams recording
pipeline. `neut sense` does NOT replace it — it wraps and extends it:

```
meeting-intake (existing)         neut sense (new)
─────────────────────────         ──────────────────
Teams → Transcribe → Extract      Teams → meeting-intake → sense inbox
→ Match GitLab → Review →         Voice Memos → Whisper → sense inbox
Apply to GitLab                   GitLab exports → sense inbox
                                  Teams messages → sense inbox
                                  Freetext/notes → sense inbox
                                  Email → sense inbox
                                  ─────────────────────────────
                                  All sources → Extract → Synthesize
                                  → Draft → Review → Publish
                                  (to tracker, GitLab, Linear, OneDrive)
```

`meeting-intake` is a specialized extractor that Neut Sense orchestrates. The
meeting-intake README already defines the right pipeline; Neut Sense adds:
1. Voice Memos as an additional audio source (same Whisper pipeline)
2. Non-audio sources (GitLab, Teams messages, freetext, email)
3. Cross-source synthesis (merge signals from all sources into one draft)
4. Multi-target publishing (not just GitLab — also tracker, Linear, OneDrive)
5. Heartbeat-driven proactive sensing

---

## Audio Pipeline: Voice Memos + Teams Recordings

Both audio sources flow through the same pipeline, with different ingestion paths:

### Source 1: iPhone Voice Memos
```
iPhone → iCloud → ~/Library/.../VoiceMemos/Recordings/*.m4a
  → fswatch/launchd detects new file
  → copies to tools/agents/inbox/raw/voice/
  → neut sense ingest --source voice
```

**launchd plist** (extends existing `com.utcomputational.gitlab-export.plist` pattern):
```xml
<!-- com.utcomputational.voice-sense.plist -->
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.utcomputational.voice-sense</string>
  <key>WatchPaths</key>
  <array>
    <string>~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings</string>
  </array>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/neut</string>
    <string>sense</string>
    <string>ingest</string>
    <string>--source</string>
    <string>voice</string>
  </array>
</dict>
</plist>
```

### Source 2: Microsoft Teams Recordings
```
Teams meeting ends → Recording appears in OneDrive/SharePoint
  → Microsoft Graph API webhook or polling (meeting-intake already specifies this)
  → Downloads to tools/agents/inbox/raw/teams/
  → neut sense ingest --source teams
```

Teams recordings come with auto-generated transcripts (via Microsoft's own
transcription). The pipeline can use those directly OR re-transcribe with
Whisper for higher quality + local privacy:

```python
def ingest_teams_recording(recording_path):
    """Process a Teams recording."""
    # Option A: Use Microsoft's transcript (faster, no compute)
    transcript = fetch_teams_transcript(recording_path)

    # Option B: Re-transcribe locally (higher quality, private)
    if config.prefer_local_transcription:
        transcript = whisper_transcribe(recording_path)

    # Both paths produce the same structured output
    return extract_signals(transcript)
```

### Shared Audio Processing Pipeline
```
Audio file (.m4a / .mp4 / .webm)
  │
  ├─ Transcribe (Whisper large-v3, local on Mac M-series)
  │  Output: timestamped text segments
  │
  ├─ Diarize (pyannote-audio, local)
  │  Output: speaker-labeled segments
  │
  ├─ Identify Speakers
  │  Input: diarized segments + config/people.md
  │  Method: Ask user to label first time; learn patterns over time
  │  Output: named speaker segments
  │
  ├─ Extract Signals (LLM, via gateway)
  │  Input: named transcript + config/initiatives.md
  │  Output: decisions, action items, status signals, blockers
  │
  ├─ Correlate (match to known entities)
  │  Input: extracted signals + GitLab issues + Linear issues
  │  Output: correlated signals with suggested targets
  │
  └─ Notify + Queue for Review
     Output: notification to Ben + draft in tools/agents/drafts/
```

---

## File Structure (within existing repo)

No new top-level directories. Everything fits in `tools/` and `docs/`:

```
tools/
  agents/
    inbox/
      raw/                          # Drop zone for unprocessed inputs
        voice/                      # Voice memo .m4a files
        teams/                      # Teams recording downloads
        gitlab/                     # GitLab export JSONs (symlink to ../exports/)
        text/                       # Freetext: Teams msgs, emails, notes
      processed/                    # Extracted signal JSONs
    drafts/                         # Agent-generated summaries for review
    approved/                       # Human-approved updates (audit trail)
    config/
      heartbeat.md                  # Proactive task schedule
      models.toml                   # LLM provider config (gateway)
    extractors/
      __init__.py
      base.py                       # Abstract extractor interface
      audio.py                      # Whisper + pyannote (shared by voice + teams)
      gitlab.py                     # GitLab export diff → signals
      freetext.py                   # General text → signals
      linear.py                     # Linear issue state changes → signals
    synthesizer.py                  # Merge signals → weekly draft
    correlator.py                   # Map signals to people/initiatives/issues
    publisher.py                    # Apply changes → xlsx/OneDrive/GitLab/Linear
    gateway.py                      # Model-agnostic LLM interface
    notifier.py                     # macOS notifications, iMessage, Teams webhook

  meeting-intake/                   # EXISTING — Teams-specific pipeline
    README.md                       # Already specifies Teams → Whisper → GitLab
    ...

  tracker/                          # EXISTING — Program tracker build
    build_tracker.py                # openpyxl tracker generator
    ...

  exports/                          # EXISTING — GitLab weekly dumps
    gitlab_export_YYYY-MM-DD.json
    ...
```

---

## Instance vs. Platform Separation

NeutronOS is designed for any nuclear facility. The `tools/agents/config/`
directory contains instance-specific configuration. Everything else is generic.

### Instance Config (facility-specific, .gitignored)

```toml
# tools/agents/config/facility.toml

[facility]
name = "UT NETL TRIGA"
type = "research"          # research | commercial | government
reactor = "triga"          # triga | msr | lwr | htgr | sfr | ...
plugin = "plugin-triga"    # links to plugins/ reactor-specific logic

[sense.sources]
voice_memos = true
teams_recordings = true
gitlab_export = true
email_forwarding = false   # future

[sense.heartbeat]
interval_minutes = 30
active_hours = "08:00-18:00"
active_days = "Mon-Fri"

[sense.publish]
onedrive_path = "Documents/Clarno_Group_Master_Program_Tracker.xlsx"
teams_channel = ""         # optional webhook for status posts
```

```markdown
# tools/agents/config/people.md
# Facility-specific team roster — .gitignored

| Name | GitLab | Linear | Role | Initiative |
|------|--------|--------|------|-----------|
| Kevin Clarno | clarno | — | Dept. Head | Strategic direction |
| Cole Gentry | cgentry7 | — | Sr. Eng. Scientist | TRIGA, Bubble, MIT DTs |
| Jeongwon Seo | jay-nuclear-phd, starone1204 | — | TRIGA DT lead | TRIGA DT |
...
```

```markdown
# tools/agents/config/initiatives.md
# Facility-specific project list — .gitignored

| ID | Name | Status | Owners | Repos |
|----|------|--------|--------|-------|
| 1 | TRIGA Digital Twin | Active | Gentry, Seo, Booth | triga_digital_twin, TRIGA_DT_website |
| 2 | Bubble Flow Loop DT | Active | Gentry | bubble_flow_loop_digital_twin |
...
```

### For Another Facility

Oregon State installs NeutronOS, creates their own config:
```toml
[facility]
name = "OSU TRIGA"
type = "research"
reactor = "triga"
plugin = "plugin-triga"    # same plugin, different config
```

They fill in their own `people.md` and `initiatives.md`. The extractors,
synthesizer, publisher, and CLI are all identical. The config is theirs.

---

## LLM Gateway (Model + IDE Agnostic)

You use Cursor, VS Code, Claude Code, and may run Qwen on TACC. The gateway
must not assume any specific provider.

```toml
# tools/agents/config/models.toml

[gateway]
format = "openai"          # All providers speak OpenAI chat completions

[[gateway.providers]]
name = "anthropic"
endpoint = "https://api.anthropic.com/v1"
model = "claude-sonnet-4-20250514"
api_key_env = "ANTHROPIC_API_KEY"
priority = 1
use_for = ["extraction", "synthesis", "correlation"]

[[gateway.providers]]
name = "qwen-rascal"
endpoint = "http://localhost:8000/v1"
model = "qwen2.5-32b-instruct"
priority = 2
use_for = ["extraction", "synthesis"]

[[gateway.providers]]
name = "openai"
endpoint = "https://api.openai.com/v1"
model = "gpt-4o"
api_key_env = "OPENAI_API_KEY"
priority = 3
use_for = ["multimodal", "fallback"]
```

The gateway tries providers in priority order with fallback. Any IDE that
can call the OpenAI API format (Cursor, Claude Code, Copilot) can also use
the gateway endpoint if exposed locally.

For RAG: the gateway doesn't own RAG. RAG is a capability of the extractors
and the `neut chat` module. The extractors use the gateway to call an LLM,
but they also have access to the retrieval layer (GitLab issues, Linear
items, the initiatives.md knowledge base, and eventually the Iceberg
lakehouse via DuckDB). The gateway is just the LLM routing layer; RAG
is assembled by the caller:

```python
def extract_signals(transcript, config):
    """Extraction uses RAG pattern: retrieve context, then generate."""
    # 1. Retrieve relevant context
    people = load_people(config)
    initiatives = load_initiatives(config)
    open_issues = fetch_gitlab_open_issues()
    linear_items = fetch_linear_items()

    # 2. Build prompt with retrieved context
    prompt = build_extraction_prompt(
        transcript=transcript,
        people=people,
        initiatives=initiatives,
        issues=open_issues + linear_items,
    )

    # 3. Call LLM via gateway (model-agnostic)
    response = gateway.complete(prompt)

    # 4. Parse structured output
    return parse_signals(response)
```

---

## Service Layer

Always-on agents (`publisher_agent`, `sense_agent`, `doctor_agent`) each expose a `service.py` module with a `main()` entry point. The service layer handles OS registration, process lifecycle, and graceful shutdown — the agent's domain logic is unchanged whether it runs interactively or as a system service.

### `service.py` Entry Point Pattern

```python
# src/neutron_os/extensions/builtins/<agent>/service.py
import signal
import sys

_shutdown = False

def _handle_sigterm(signum, frame):
    global _shutdown
    _shutdown = True

def main():
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    agent = Agent()
    agent.start()

    while not _shutdown:
        agent.tick()

    agent.shutdown()   # flush queues, close DB connections, write state
    sys.exit(0)
```

The `tick()` / `shutdown()` contract is the only interface the service layer requires from each agent. Agents must complete in-flight work before `shutdown()` returns. Maximum shutdown time is 10 seconds; after that the OS kills the process.

### launchd Plist Structure (macOS)

One plist per workspace, stored in `~/Library/LaunchAgents/`. Key fields:

```xml
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.neutron-os.sense-agent.<workspace-hash></string>

  <key>ProgramArguments</key>
  <array>
    <string>/path/to/.venv/bin/python</string>
    <string>-m</string>
    <string>neutron_os.extensions.builtins.sense_agent.service</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/path/to/workspace</string>

  <key>KeepAlive</key>
  <true/>

  <key>ThrottleInterval</key>
  <integer>10</integer>

  <key>StandardOutPath</key>
  <string>/path/to/workspace/runtime/logs/sense-agent.stdout.log</string>

  <key>StandardErrorPath</key>
  <string>/path/to/workspace/runtime/logs/sense-agent.stderr.log</string>
</dict>
</plist>
```

`ThrottleInterval` (seconds) is the minimum time between restarts. Set to 10 to prevent tight crash loops while still recovering quickly from transient failures.

### systemd User Unit Structure (Linux)

```ini
# ~/.config/systemd/user/neutron-os-sense-agent-<workspace-hash>.service
[Unit]
Description=NeutronOS Sense Agent (<workspace-name>)
After=network.target

[Service]
ExecStart=/path/to/.venv/bin/python -m neutron_os.extensions.builtins.sense_agent.service
WorkingDirectory=/path/to/workspace
Restart=on-failure
RestartSec=10
StandardOutput=append:/path/to/workspace/runtime/logs/sense-agent.stdout.log
StandardError=append:/path/to/workspace/runtime/logs/sense-agent.stderr.log

[Install]
WantedBy=default.target
```

`WantedBy=default.target` ensures the unit starts at user login without requiring root. `Restart=on-failure` restarts only on non-zero exit; `_shutdown` path exits 0 (clean stop), so `neut agents stop` does not trigger a restart.

---

## Implementation Plan

### Week 1: Audio Pipeline (Voice Memos + Teams)

**Goal:** Record a meeting → get a structured, correlated summary within minutes.

**Build order:**
1. `tools/agents/extractors/audio.py` — Whisper transcription + pyannote diarization
2. `tools/agents/gateway.py` — Model-agnostic LLM client (litellm or custom)
3. `tools/agents/correlator.py` — Map extracted entities to people.md + initiatives.md
4. `tools/agents/notifier.py` — macOS notification when processing complete
5. Ingest scripts for both sources:
   - Voice Memos: launchd watcher on iCloud sync directory
   - Teams: extend `meeting-intake` to also deposit in `inbox/raw/teams/`
     OR poll Microsoft Graph API for new recordings

**Speaker identification flow:**
```
First recording with unknown speakers:
  → Agent: "I found 3 speakers. Based on context, I think:
            Speaker A = Kevin (mentioned 'as dept head...')
            Speaker B = Cole (discussed thermal-hydraulics)
            Speaker C = Unknown
            Please confirm or correct."
  → Ben confirms/corrects
  → Agent saves speaker profiles in config/speaker_profiles.json

Subsequent recordings:
  → Agent: "Identified Kevin and Cole. One new speaker — who is this?"
  → Ben: "That's Nick"
  → Agent adds to profiles
```

**Deliverable:** `neut sense ingest --source voice` and `neut sense ingest --source teams`
both produce structured JSON in `inbox/processed/` with named speakers,
decisions, action items, and initiative correlations.

### Week 2: GitLab + Linear Diff Summaries

**Goal:** Weekly human-readable summary of what changed across all repos.

**Build order:**
1. `tools/agents/extractors/gitlab.py` — Diff two weekly exports → signals
2. `tools/agents/extractors/linear.py` — Fetch Linear changes → signals
3. Summary template for human-readable output

**Deliverable:** `neut sense ingest --source gitlab` produces a summary like:
```markdown
## GitLab Activity — Week of Feb 17, 2026

### 🔥 Active Repos
- **TRIGA_DT_website** — 12 commits by Seo. Login improvements, op log updates.
- **NETL_PXI** — 4 commits by Max Hoffing. Streaming SMU data, noise mitigation.

### 📋 Issue Movement
- Opened: 5 new (TRIGA DT: 3, Bubble Flow: 2)
- Closed: 2 (TRIGA DT #298, #294)

### ⚠️ Stale
- MIT Irradiation Loop — 41 open issues, 0 commits in 90 days
```

### Week 3: Synthesis + Tracker Update

**Goal:** Merge all signals → generate tracker diff → apply on approval.

**Build order:**
1. `tools/agents/synthesizer.py` — Merge processed signals into weekly draft
2. `tools/agents/publisher.py` — Apply approved diff to xlsx + push to OneDrive
3. `neut sense draft` and `neut sense publish` commands

### Week 4: Heartbeat + Notifications

**Goal:** Agent proactively checks for new inputs and alerts when needed.

**Build order:**
1. `tools/agents/config/heartbeat.md` — Checklist of proactive checks
2. launchd plist for heartbeat daemon
3. `neut sense heartbeat` command
4. Stale detection: flag people/initiatives with no signals in 14+ days

---

## CLAUDE.md Update

The existing `CLAUDE.md` in the repo covers repo standards (git, terminology,
mermaid, INL framing). It should NOT be replaced with agent context.

Instead, **append a section** for agent development:

```markdown
## Agent Development (Neut Sense)

### Architecture
See `docs/requirements/prd_neut-cli.md` for CLI design. Neut Sense extends
the existing command structure for proactive program awareness.

Agent code lives in `tools/agents/`. Instance config in `tools/agents/config/`
is .gitignored.

### Key Files
- `tools/agents/gateway.py` — Model-agnostic LLM routing
- `tools/agents/extractors/` — Source-specific signal extraction
- `tools/agents/correlator.py` — Entity resolution (people, initiatives, issues)
- `tools/agents/synthesizer.py` — Cross-source signal merging
- `tools/agents/publisher.py` — Multi-target publishing
- `tools/meeting-intake/` — Teams recording pipeline (pre-existing)

### Design Principles
- **Extend, don't replace:** `meeting-intake` is an extractor that Neut Sense orchestrates
- **Human-in-the-loop:** All writes require explicit approval
- **Model-agnostic:** Gateway routes to any OpenAI-compatible endpoint
- **IDE-agnostic:** CLI-first, no IDE plugins, MCP server for tool integration
- **Offline-first:** Follows neut CLI spec — queue locally, sync on restore
- **Instance separation:** Platform code is generic; config/ is facility-specific

### Running Locally
```bash
# Process voice memos
neut sense ingest --source voice

# Process Teams recordings
neut sense ingest --source teams

# Generate weekly status draft
neut sense draft

# Review and approve
neut sense review
neut sense publish --target onedrive
```
```

---

## Open Source Boundary

### Public (neutron-os repo):
- All code in `tools/agents/` (extractors, gateway, synthesizer, publisher)
- CLI commands (`neut sense`)
- Plugin interface for reactor-specific extractors
- Config file schemas and examples (.example files)
- Documentation

### Private (.gitignored):
- `tools/agents/config/people.md` — your team roster
- `tools/agents/config/initiatives.md` — your project list
- `tools/agents/config/facility.toml` — your facility details
- `tools/agents/config/models.toml` — your API keys
- `tools/agents/config/speaker_profiles.json` — voice ID data
- `tools/agents/inbox/` — all input data
- `tools/agents/drafts/` — generated summaries
- `tools/agents/approved/` — approval audit trail

---

## M-O Corpus Stewardship

M-O (the resource steward agent) owns the health and lifecycle of the personal RAG
corpus — analogous to how it manages `archive/` and `spikes/`. This is ongoing
housekeeping that runs on a schedule without user involvement.

*Cross-reference: `neutron-os-rag-architecture-spec.md` §7.4 (Corpus Lifecycle)*

### M-O RAG Responsibilities

| Task | Trigger | Implementation |
|------|---------|---------------|
| Nightly incremental index | Scheduled (off-hours) | `neut rag index` — checksum-skipping, fast after first run |
| Session pruning | Weekly | `store.delete_corpus_older_than(CORPUS_INTERNAL, days=ttl)` |
| Corpus health check | On `neut status` | Detect source/index drift; report stale document count |
| Watch daemon supervision | On login / after crash | launchd plist or systemd user unit wrapping `neut rag watch --quiet` |
| Index size reporting | On `neut status` | Surface chunk counts without requiring explicit `neut rag status` |

### Watch Daemon Installation

During `neut config` (setup wizard), M-O generates and installs the appropriate
OS-level service to supervise `neut rag watch --quiet`:

**macOS** — `~/Library/LaunchAgents/io.neutronos.rag-watch.plist`:
```xml
<plist version="1.0"><dict>
  <key>Label</key><string>io.neutronos.rag-watch</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/.venv/bin/neut</string>
    <string>rag</string><string>watch</string><string>--quiet</string>
  </array>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>WorkingDirectory</key><string>/path/to/Neutron_OS</string>
  <key>StandardErrorPath</key>
  <string>~/Library/Logs/neutronos-rag-watch.log</string>
</dict></plist>
```

**Linux** — `~/.config/systemd/user/neutron-os-rag-watch.service`:
```ini
[Unit]
Description=Neutron OS RAG filesystem watcher
After=default.target

[Service]
Type=simple
WorkingDirectory=/path/to/Neutron_OS
ExecStart=/path/to/.venv/bin/neut rag watch --quiet
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

### Session TTL Pruning

The session corpus grows indefinitely without pruning. M-O's weekly sweep respects
the user-configurable TTL:

```bash
neut settings set rag.session_ttl_days 90    # default: 90
```

The scheduled task calls `store.delete_corpus_older_than(corpus, days)` which removes
chunks and document records older than the TTL window from `rag-internal`. Old sessions
remain as JSON files on disk — only the index entries are pruned.

### What M-O Does NOT Own

- The `neut rag watch` process itself — that's just a subprocess it supervises
- Deciding what content is valuable — policy is expressed through `rag.session_ttl_days`
  and other settings; M-O enforces but does not decide
- The actual ingest logic — stays in `rag/personal.py` and `rag/ingest.py`

---

## Dependencies

| Component | Choice | Why |
|-----------|--------|-----|
| Transcription | whisper (openai/whisper) | Local, M-series native, privacy-safe |
| Diarization | pyannote-audio | Pairs with Whisper, good accuracy |
| LLM Gateway | litellm | OpenAI-compatible, 100+ providers, fallback chains |
| File watching | launchd (Mac) / inotify (Linux) | Native, no deps |
| Teams API | msgraph-sdk-python | Microsoft Graph for recordings + transcripts |
| OneDrive push | msgraph-sdk-python | Same SDK, same auth |
| Excel | openpyxl | Already used in tracker/ |
| GitLab | python-gitlab | Already used in exports/ |
| Notifications | pync (macOS) + ntfy.sh (remote) | Local + mobile push |
| CLI framework | Click/Typer (Python prototype) → Rust (production) | Match neut CLI spec |

**Note on CLI language:** The neut CLI spec says Rust. For the Neut Sense prototype,
Python is fine — it wraps existing Python tools (Whisper, openpyxl, python-gitlab).
If Neut Sense needs to be compiled into the Rust `neut` binary later, it can be
called as a subprocess or rewritten. Don't let language choice block week 1.