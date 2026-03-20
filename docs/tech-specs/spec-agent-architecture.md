# NeutronOS Agent Architecture

> **Implementation Status:** This spec covers both built-in agents (Signal, Chat, M-O, Doctor) and domain agents. Digital Twin Automation (GOAL_DT_001–005) is the flagship domain capability — see [Digital Twin Agent Architecture](#digital-twin-agent-architecture) below.

---

## Architecture Overview

NeutronOS agents are modular, autonomous processes that perceive signals from the environment, reason using LLMs, and take bounded actions subject to safety guardrails. **Digital Twin Automation is the flagship capability** — agents that coordinate Shadow runs, ROM training, bias corrections, and model validation.

| Agent Category | Primary Focus | Status |
|---------------|--------------|--------|
| **Digital Twin Agents** | Shadow orchestration, ROM lifecycle, bias monitoring | 🔲 Planned (flagship) |
| **Signal Agent** | Program awareness, voice/document ingest | ✅ Shipped |
| **Chat Agent** | Interactive LLM assistant | ✅ Shipped |
| **M-O Agent** | Resource stewardship, system hygiene | ✅ Shipped |
| **Doctor Agent** | System diagnostics, security health | ✅ Shipped |

All agents follow the design principles and safety guardrails defined in [prd-agents.md](../requirements/prd-agents.md).

---

## Context: What Already Exists

The Neutron_OS repo has a well-designed architecture that this agent work must
respect and extend, not replace:

```
Neutron_OS/
  src/neutron_os/                   # Python package root
    extensions/builtins/
      signal_agent/                 # Signal ingestion agent (this spec)
      chat_agent/                   # Interactive LLM assistant
      publisher/                    # Document lifecycle
      mo_agent/                     # Resource steward
      doctor_agent/                 # AI diagnostics
      ...                           # See CLAUDE.md for full list
    infra/                          # Shared infra (gateway, auth)
  runtime/                          # Instance-specific data (mostly gitignored)
    config/                         # Facility config
    inbox/                          # Signal inbox
    drafts/                         # Agent-generated drafts
    sessions/                       # Agent sessions
  docs/
    requirements/                   # PRDs
    specs/                          # Architecture specs
  tools/
    exports/                        # Weekly GitLab JSON dumps
```

Key design decisions already made:
- **`neut` CLI** is the unified interface (Python/argparse, noun-verb pattern)
- **Extensions** handle reactor-specific logic (external repos, installed to `.neut/extensions/`)
- **Signal pipeline** handles Teams → Transcribe → Extract → GitLab
- **Offline-first** is a hard requirement (nuclear facilities lose network)
- **Model-agnostic** — no vendor lock-in on LLM provider

---

## Digital Twin Agent Architecture

**This is the flagship capability.** Digital Twin agents automate the lifecycle of reactor digital twins — from data acquisition through ROM deployment. These agents coordinate with the infrastructure defined in [spec-digital-twin-architecture.md](spec-digital-twin-architecture.md).

### Agent Overview

```mermaid
flowchart TB
    subgraph DAQ["DAQ → Shadow"]
        daq_in[Reactor DAQ] --> quality[Quality Check]
        quality --> snapshot[State Snapshots]
        snapshot --> shadow_submit[Submit Shadow]
        shadow_submit --> notify[Notify Operator]
    end

    DAQ --> ROM

    subgraph ROM["ROM Training"]
        drift[Drift Detection] --> trigger[Training Trigger]
        trigger --> train[Submit Training]
        train --> validate[Validate ROM]
        validate --> propose[Propose Deploy]
    end

    ROM --> Bias

    subgraph Bias["Bias Update"]
        deviations[Analyze Deviations] --> patterns[Detect Patterns]
        patterns --> correction[Calc Correction]
        correction --> review[Route to Operator]
    end

    style DAQ fill:#e3f2fd,color:#000000
    style ROM fill:#fff3e0,color:#000000
    style Bias fill:#e8f5e9,color:#000000
```

### CLI Design (`neut twin`)

```bash
# ─── SHADOW: Nightly physics code runs ───
neut twin shadow status                 # Show last Shadow run status
neut twin shadow trigger --facility=netl  # Manually trigger Shadow
neut twin shadow history --days=30      # Show Shadow run history

# ─── ROM: Reduced-order model lifecycle ───
neut twin rom list                      # List deployed ROMs
neut twin rom drift --model=triga-rom2  # Check ROM drift metrics
neut twin rom train --model=triga-rom2  # Trigger retraining
neut twin rom deploy --version=v2.1     # Deploy new ROM (requires approval)

# ─── BIAS: Systematic correction monitoring ───
neut twin bias analyze --facility=netl  # Analyze systematic deviations
neut twin bias propose --correction=... # Submit bias correction proposal
neut twin bias history                  # View correction history

# ─── PREDICT: Real-time ROM inference ───
neut twin predict --facility=netl       # Get current ROM prediction
neut twin compare --run=run-2026-03-17  # Compare prediction vs measured
```

### Agent Code Structure

```
src/neutron_os/extensions/builtins/twin_agent/
  __init__.py
  daq_shadow_agent.py       # GOAL_DT_001: DAQ → Shadow workflow
  rom_training_agent.py     # GOAL_DT_002: ROM retraining automation
  bias_update_agent.py      # GOAL_DT_003: Bias correction proposals
  operator_learning_agent.py # GOAL_DT_004: Operator feedback integration
  rom_failure_handler.py    # GOAL_DT_005: ROM failure detection & recovery
  cli.py                    # neut twin commands
```

### RACI Integration

| Agent | Autonomous (Informed) | Requires Approval |
|-------|----------------------|-------------------|
| **DAQ → Shadow** | Routine data quality checks, Shadow submissions | Data quality below threshold, Shadow failures |
| **ROM Training** | Drift monitoring, training job submission | New ROM deployment to production |
| **Bias Update** | Deviation analysis, pattern detection | Application of bias corrections |
| **Failure Handler** | Error detection, fallback activation | ROM disabling, operator alerts |

### Data Quality Prerequisites

Per Dr. Clarno's guidance, Digital Twin agents enforce data quality before Shadow runs:

| Check | Validation | Action on Failure |
|-------|------------|-------------------|
| Time synchronization | Rod position, neutron power, Cherenkov aligned | Alert data team, delay Shadow |
| Correlation | Rod movements → predictable power response | Flag for manual review |
| Noise characterization | Distinguish correlated physics from noise | Filter or flag spikes |

---

## Signal Agent Architecture

### What We're Adding: Neut Signal

A new CLI noun (`neut signal`) that extends the existing `neut` command structure. Neut Signal is the
agentic module for continuous program awareness — ingesting signals from multiple
sources, extracting structured information, and maintaining program state.

### CLI Design (follows existing noun-verb pattern)

```bash
# ─── INGEST: Pull signals from sources ───
neut signal ingest                     # Process all new items in inbox
neut signal ingest --source voice      # Process only voice memos
neut signal ingest --source teams      # Process only Teams recordings
neut signal ingest --source gitlab     # Process latest GitLab export
neut signal ingest --source text       # Process freetext drops (notes, emails)

# ─── DRAFT: Synthesize signals into human-readable summaries ───
neut signal draft                      # Generate weekly status draft
neut signal draft --scope tracker      # Draft tracker update only
neut signal draft --scope issues       # Draft GitLab/Linear issue updates only
neut signal draft --scope minutes      # Draft meeting minutes only

# ─── REVIEW: Human-in-the-loop approval ───
neut signal review                     # Open latest draft in $EDITOR
neut signal review --approve           # Approve current draft
neut signal review --reject            # Reject and discard

# ─── PUBLISH: Apply approved changes ───
neut signal publish                    # Push approved changes to targets
neut signal publish --target onedrive  # Push tracker to SharePoint/OneDrive
neut signal publish --target gitlab    # Apply issue updates to GitLab
neut signal publish --target linear    # Apply issue updates to Linear

# ─── HEARTBEAT: Proactive sensing daemon ───
neut signal heartbeat                  # Run heartbeat checks now
neut signal heartbeat --start          # Start daemon (launchd/systemd)
neut signal heartbeat --stop           # Stop daemon
neut signal heartbeat --status         # Show daemon status + last run

# ─── STATUS: Current program state ───
neut signal status                     # Show program overview
neut signal status --stale             # Show items with no signal in 14+ days
neut signal status --people            # Show per-person activity summary
```

### Relationship to Existing Modules

```
neut log    — Reactor operations logging        (facility-facing)
neut sim    — Simulation orchestration           (facility-facing)
neut model  — Surrogate model management         (facility-facing)
neut twin   — Digital twin state                 (facility-facing)
neut data   — Data platform queries              (facility-facing)
neut chat   — Agentic assistant (interactive)    (facility-facing)
neut signal  — Program awareness (proactive)      (team-facing)     ← NEW
neut ext    — Extension management               (platform-facing)
neut infra  — Infrastructure management          (platform-facing)
```

Neut Signal is unique: it's the only noun that runs proactively (heartbeat) and
synthesizes across sources rather than querying a single system. But it follows
the same patterns: offline-first, RACI-governed autonomy (per-user per-agent
trust levels), JSON/table output formats.

---

## Relationship to `meeting-intake`

The original `meeting-intake` concept specified a Teams recording pipeline.
`neut signal` subsumes and extends that concept:

```
meeting-intake (existing)         neut signal (new)
─────────────────────────         ──────────────────
Teams → Transcribe → Extract      Teams → meeting-intake → signal inbox
→ Match GitLab → Review →         Voice Memos → Whisper → signal inbox
Apply to GitLab                   GitLab exports → signal inbox
                                  Teams messages → signal inbox
                                  Freetext/notes → signal inbox
                                  Email → signal inbox
                                  ─────────────────────────────
                                  All sources → Extract → Synthesize
                                  → Draft → Review → Publish
                                  (to tracker, GitLab, Linear, OneDrive)
```

`meeting-intake` is a specialized extractor that Neut Signal orchestrates. The
meeting-intake README already defines the right pipeline; Neut Signal adds:
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
  → copies to runtime/inbox/raw/voice/
  → neut signal ingest --source voice
```

**launchd plist** (extends existing `com.utcomputational.gitlab-export.plist` pattern):
```xml
<!-- com.utcomputational.voice-signal.plist -->
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.utcomputational.voice-signal</string>
  <key>WatchPaths</key>
  <array>
    <string>~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings</string>
  </array>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/neut</string>
    <string>signal</string>
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
  → Downloads to runtime/inbox/raw/teams/
  → neut signal ingest --source teams
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
     Output: notification to Ben + draft in runtime/drafts/
```

---

## File Structure (within existing repo)

Code lives in the extension directory; runtime data in `runtime/`:

```
src/neutron_os/extensions/builtins/signal_agent/
  __init__.py
  cli.py                            # CLI commands for `neut signal`
  service.py                        # Always-on service entry point
  extractors/
    __init__.py
    base.py                         # Abstract extractor interface
    audio.py                        # Whisper + pyannote (shared by voice + teams)
    gitlab.py                       # GitLab export diff → signals
    freetext.py                     # General text → signals
    linear.py                       # Linear issue state changes → signals
  correlator.py                     # Map signals to people/initiatives/issues
  synthesizer.py                    # Merge signals → weekly draft
  neut-extension.toml               # Extension manifest (noun = "signal")

src/neutron_os/infra/
  gateway.py                        # Model-agnostic LLM interface

runtime/
  inbox/
    raw/                            # Drop zone for unprocessed inputs
      voice/                        # Voice memo .m4a files
      teams/                        # Teams recording downloads
      gitlab/                       # GitLab export JSONs
      text/                         # Freetext: Teams msgs, emails, notes
    processed/                      # Extracted signal JSONs
  config/                           # Facility config (gitignored)
    heartbeat.md                    # Proactive task schedule
    models.toml                     # LLM provider config (gateway)
  drafts/                           # Agent-generated summaries for review

tools/
  exports/                          # GitLab weekly dumps
    gitlab_export_YYYY-MM-DD.json
```

---

## Instance vs. Platform Separation

NeutronOS is designed for any nuclear facility. The `runtime/config/`
directory contains instance-specific configuration. Everything else is generic.

### Instance Config (facility-specific, .gitignored)

```toml
# runtime/config/facility.toml

[facility]
name = "UT NETL TRIGA"
type = "research"          # research | commercial | government
reactor = "triga"          # triga | msr | lwr | htgr | sfr | ...
plugin = "plugin-triga"    # links to plugins/ reactor-specific logic

[signal.sources]
voice_memos = true
teams_recordings = true
gitlab_export = true
email_forwarding = false   # future

[signal.heartbeat]
interval_minutes = 30
active_hours = "08:00-18:00"
active_days = "Mon-Fri"

[signal.publish]
onedrive_path = "Documents/Clarno_Group_Master_Program_Tracker.xlsx"
teams_channel = ""         # optional webhook for status posts
```

```markdown
# runtime/config/people.md
# Facility-specific team roster — .gitignored

| Name | GitLab | Linear | Role | Initiative |
|------|--------|--------|------|-----------|
| Kevin Clarno | clarno | — | Dept. Head | Strategic direction |
| Cole Gentry | cgentry7 | — | Sr. Eng. Scientist | TRIGA, Bubble, MIT DTs |
| Jeongwon Seo | jay-nuclear-phd, starone1204 | — | TRIGA DT lead | TRIGA DT |
...
```

```markdown
# runtime/config/initiatives.md
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

> **Design Note (v0.5.x):** Both `people.md` and `initiatives.md` are
> static bootstrap files that should be replaced by dynamic sources:
>
> **People:** Once Ory Kratos ships (Security PRD FR-ID-005), the
> correlator reads from the Kratos identity store instead of a markdown
> file. People are added/removed through `neut login`, not file edits.
>
> **Initiatives:** Static lists are unsustainable — new initiatives
> emerge, old ones retire, and nobody maintains the file. Initiatives
> should be derived dynamically from:
> 1. PRD files (`docs/requirements/prd-*.md`) — each PRD is an initiative with lifecycle status
> 2. OKR key results (`prd-okrs-2026.md`) — measurable targets with timelines
> 3. GitLab milestones/epics (via connection) — tracked project work
> 4. Active git branches (`feat/*`) — in-progress development initiatives
> 5. Extension manifests (`neut-extension.toml`) — each extension is an initiative
>
> The correlator would query these sources at ingest time, building a
> live initiative graph with relationships (depends-on, enables, blocks).
> This is a significant design effort — needs ideation before implementation.
> See: [GitHub Discussion TBD] or [ADR TBD]

---

## LLM Gateway (Model + IDE Agnostic)

You use Cursor, VS Code, Claude Code, and may run Qwen on TACC. The gateway
must not assume any specific provider.

```toml
# runtime/config/models.toml

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

### Per-Agent Routing Profiles (v0.5.0)

Each agent declares a routing profile that defines its provider preferences
and failure behavior. See [Model Routing Spec §10](spec-model-routing.md)
for the full design.

| Agent | Profile | Priority | On Failure |
|-------|---------|----------|------------|
| Neut (chat) | `chat` | Quality (Opus → Sonnet → local) | Queue |
| EVE (extraction) | `extraction` | Speed (Haiku → local → skip) | Skip |
| D-FIB (diagnosis) | `diagnosis` | Reliability (Sonnet → Haiku) | Queue |
| PR-T (publishing) | `publishing` | Quality (Sonnet → Opus) | Retry |
| M-O (steward) | `extraction` | Speed (shared with EVE) | Skip |

```python
# Agent declares its profile at construction
class EVEAgent:
    ROUTING_PROFILE = "extraction"  # Cheap, fast, skip-on-fail

    def extract(self, text):
        return self._gateway.complete(text, profile=self.ROUTING_PROFILE)
```

### RACI-Based Human-in-the-Loop (v0.5.0)

Every agent action checks the user's RACI preference before executing.
See [Agents PRD — RACI Framework](../requirements/prd-agents.md) for
the full design.

**Three-dimensional trust model:** RACI settings are scoped to the
combination of **user** (identified) + **agent** (specific) + **action**
(category). Trust doesn't transfer between agents — each agent builds
its own track record with each user.

```python
# In any agent before taking action:
from neutron_os.infra.raci import check_raci, RACILevel, EmergencyMode

# Check RACI for this specific agent + action combination
level = check_raci(agent="eve", action="issue.update")

# Emergency mode check (takes precedence)
if level.emergency_mode == EmergencyMode.FREEZE:
    return  # Do nothing — agent is frozen
if level.emergency_mode == EmergencyMode.LOG_INTENT_ONLY:
    log_intent(action="issue.update", target=issue_url, body=body)
    return  # Log but don't execute or propose

if level == RACILevel.EXECUTE:
    # R or I — just do it (notify if I)
    provider.add_comment(issue_url, body)
    if level.notify:
        notify(f"Updated issue #{iid}")

elif level == RACILevel.APPROVE:
    # A — pause for human (also used in PROPOSE_ONLY emergency mode)
    print(f"  Update issue #{iid}? [Y/n]")
    if confirmed():
        provider.add_comment(issue_url, body)

elif level == RACILevel.CONSULT:
    # C — show context, ask for input
    print(f"  Proposed comment on #{iid}:")
    print(f"  {body[:200]}...")
    feedback = input("  Edit, approve, or skip? ")
    ...
```

**Settings storage (per-agent):**
```bash
neut settings set raci.eve.issue.update informed     # Trust EVE to update issues
neut settings set raci.prt.publish.document approve  # PR-T still needs approval
neut settings set raci.*.issue.create approve        # All agents need approval to create issues
```

**Emergency controls:**
```bash
neut raci all-propose-only          # All agents pause for approval
neut raci all-log-intent-only       # All agents log intent, no proposals
neut raci all-freeze                # All agents stop processing
neut raci resume                    # Restore pre-emergency settings
```

**Default RACI per ActionCategory:**
- `ActionCategory.READ` → Informed (auto-execute, notify)
- `ActionCategory.WRITE` → Approve (pause for confirmation)
- Safety-adjacent actions → always Approve (NSG-005 override, cannot be loosened)

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

Always-on agents (`publisher_agent`, `signal_agent`, `doctor_agent`) each expose a `service.py` module with a `main()` entry point. The service layer handles OS registration, process lifecycle, and graceful shutdown — the agent's domain logic is unchanged whether it runs interactively or as a system service.

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
  <string>com.neutron-os.signal-agent.<workspace-hash></string>

  <key>ProgramArguments</key>
  <array>
    <string>/path/to/.venv/bin/python</string>
    <string>-m</string>
    <string>neutron_os.extensions.builtins.signal_agent.service</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/path/to/workspace</string>

  <key>KeepAlive</key>
  <true/>

  <key>ThrottleInterval</key>
  <integer>10</integer>

  <key>StandardOutPath</key>
  <string>/path/to/workspace/runtime/logs/signal-agent.stdout.log</string>

  <key>StandardErrorPath</key>
  <string>/path/to/workspace/runtime/logs/signal-agent.stderr.log</string>
</dict>
</plist>
```

`ThrottleInterval` (seconds) is the minimum time between restarts. Set to 10 to prevent tight crash loops while still recovering quickly from transient failures.

### systemd User Unit Structure (Linux)

```ini
# ~/.config/systemd/user/neutron-os-signal-agent-<workspace-hash>.service
[Unit]
Description=NeutronOS Signal Agent (<workspace-name>)
After=network.target

[Service]
ExecStart=/path/to/.venv/bin/python -m neutron_os.extensions.builtins.signal_agent.service
WorkingDirectory=/path/to/workspace
Restart=on-failure
RestartSec=10
StandardOutput=append:/path/to/workspace/runtime/logs/signal-agent.stdout.log
StandardError=append:/path/to/workspace/runtime/logs/signal-agent.stderr.log

[Install]
WantedBy=default.target
```

`WantedBy=default.target` ensures the unit starts at user login without requiring root. `Restart=on-failure` restarts only on non-zero exit; `_shutdown` path exits 0 (clean stop), so `neut agents stop` does not trigger a restart.

---

## Implementation Plan

### Phase 1: Digital Twin Agent Foundation (Priority)

**Goal:** Formalize the existing VERA Shadow workflow into NeutronOS agent framework.

> **Building on existing work:** Shadowcaster already runs nightly VERA simulations and emails daily predictions. Phase 1 extracts this workflow into the NeutronOS agent framework, generalizing for multi-reactor support.

**Build order:**
1. `src/neutron_os/extensions/builtins/twin_agent/daq_shadow_agent.py` — Generalize Shadowcaster's TRIGA workflow
2. `src/neutron_os/extensions/builtins/twin_agent/cli.py` — `neut twin` commands
3. Data quality validation hooks (time sync, correlation checks per Dr. Clarno)
4. Integration with existing PostgreSQL schema (`shadowcaster_data`, `triga_derived_data`)
5. Operator notification pipeline (email + optional Teams webhook)

**Deliverable:** `neut twin shadow status` and `neut twin shadow trigger` operational for NETL TRIGA, with data quality prereqs enforced.

### Phase 2: ROM Lifecycle Agents

**Goal:** Automate ROM retraining and drift monitoring.

**Build order:**
1. `src/neutron_os/extensions/builtins/twin_agent/rom_training_agent.py` — Training trigger logic
2. Drift detection metrics and thresholds
3. Training job submission to HPC scheduler
4. ROM validation against holdout data
5. Deployment proposal workflow (requires human approval)

**Deliverable:** `neut twin rom drift` detects degradation; `neut twin rom train` submits jobs with reproducible configs.

### Phase 3: Bias & Failure Handling

**Goal:** Autonomous bias correction proposals and ROM failure recovery.

**Build order:**
1. `src/neutron_os/extensions/builtins/twin_agent/bias_update_agent.py` — Systematic deviation analysis
2. `src/neutron_os/extensions/builtins/twin_agent/rom_failure_handler.py` — Fallback chains
3. Calibration target tracking (per Dr. Clarno: cross sections, initial isotopes, geometry)

**Deliverable:** `neut twin bias analyze` detects systematic patterns; ROM failures trigger automatic fallback to Shadow.

---

### Signal Agent: Week 1 — Audio Pipeline (Voice Memos + Teams)

**Goal:** Record a meeting → get a structured, correlated summary within minutes.

**Build order:**
1. `src/neutron_os/extensions/builtins/signal_agent/extractors/audio.py` — Whisper transcription + pyannote diarization
2. `src/neutron_os/infra/gateway.py` — Model-agnostic LLM client (litellm or custom)
3. `src/neutron_os/extensions/builtins/signal_agent/correlator.py` — Map extracted entities to people.md + initiatives.md
4. Notifier module — macOS notification when processing complete
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

**Deliverable:** `neut signal ingest --source voice` and `neut signal ingest --source teams`
both produce structured JSON in `inbox/processed/` with named speakers,
decisions, action items, and initiative correlations.

### Signal Agent: Week 2 — GitLab + Linear Diff Summaries

**Goal:** Weekly human-readable summary of what changed across all repos.

**Build order:**
1. `src/neutron_os/extensions/builtins/signal_agent/extractors/gitlab.py` — Diff two weekly exports → signals
2. `src/neutron_os/extensions/builtins/signal_agent/extractors/linear.py` — Fetch Linear changes → signals
3. Summary template for human-readable output

**Deliverable:** `neut signal ingest --source gitlab` produces a summary like:
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

### Signal Agent: Week 3 — Synthesis + Tracker Update

**Goal:** Merge all signals → generate tracker diff → apply on approval.

**Build order:**
1. `src/neutron_os/extensions/builtins/signal_agent/synthesizer.py` — Merge processed signals into weekly draft
2. Publisher module — Apply approved diff to xlsx + push to OneDrive
3. `neut signal draft` and `neut signal publish` commands

### Signal Agent: Week 4 — Heartbeat + Notifications

**Goal:** Agent proactively checks for new inputs and alerts when needed.

**Build order:**
1. `runtime/config/heartbeat.md` — Checklist of proactive checks
2. launchd plist for heartbeat daemon
3. `neut signal heartbeat` command
4. Stale detection: flag people/initiatives with no signals in 14+ days

---

## CLAUDE.md Update

The existing `CLAUDE.md` in the repo covers repo standards (git, terminology,
mermaid, INL framing). It should NOT be replaced with agent context.

Instead, **append a section** for agent development:

```markdown
## Agent Development (Neut Signal)

### Architecture
See `docs/requirements/prd-neut-cli.md` for CLI design. Neut Signal extends
the existing command structure for proactive program awareness.

Agent code lives in `src/neutron_os/extensions/builtins/signal_agent/`. Instance config in `runtime/config/`
is .gitignored.

### Key Files
- `src/neutron_os/infra/gateway.py` — Model-agnostic LLM routing
- `src/neutron_os/extensions/builtins/signal_agent/extractors/` — Source-specific signal extraction
- `src/neutron_os/extensions/builtins/signal_agent/correlator.py` — Entity resolution (people, initiatives, issues)
- `src/neutron_os/extensions/builtins/signal_agent/synthesizer.py` — Cross-source signal merging

### Design Principles
- **Extend, don't replace:** `meeting-intake` is an extractor that Neut Signal orchestrates
- **RACI-governed autonomy:** Write actions follow user's per-agent RACI settings; safety-critical actions always require approval (NSG-005)
- **Model-agnostic:** Gateway routes to any OpenAI-compatible endpoint
- **IDE-agnostic:** CLI-first, no IDE plugins, MCP server for tool integration
- **Offline-first:** Follows neut CLI spec — queue locally, sync on restore
- **Instance separation:** Platform code is generic; config/ is facility-specific

### Running Locally
```bash
# Process voice memos
neut signal ingest --source voice

# Process Teams recordings
neut signal ingest --source teams

# Generate weekly status draft
neut signal draft

# Review and approve
neut signal review
neut signal publish --target onedrive
```
```

---

## Open Source Boundary

### Public (neutron-os repo):
- All code in `src/neutron_os/extensions/builtins/signal_agent/` (extractors, correlator, synthesizer)
- CLI commands (`neut signal`)
- Plugin interface for reactor-specific extractors
- Config file schemas and examples (.example files)
- Documentation

### Private (.gitignored):
- `runtime/config/people.md` — your team roster
- `runtime/config/initiatives.md` — your project list
- `runtime/config/facility.toml` — your facility details
- `runtime/config/models.toml` — your API keys
- `runtime/config/speaker_profiles.json` — voice ID data
- `runtime/inbox/` — all input data
- `runtime/drafts/` — generated summaries

---

## M-O Corpus Stewardship

M-O (the resource steward agent) owns the health and lifecycle of the personal RAG
corpus — analogous to how it manages `archive/` and `spikes/`. This is ongoing
housekeeping that runs on a schedule without user involvement.

*Cross-reference: `spec-rag-architecture.md` §7.4 (Corpus Lifecycle)*

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

**Note on CLI language:** The neut CLI spec says Rust. For the Neut Signal prototype,
Python is fine — it wraps existing Python tools (Whisper, openpyxl, python-gitlab).
If Neut Signal needs to be compiled into the Rust `neut` binary later, it can be
called as a subprocess or rewritten. Don't let language choice block week 1.