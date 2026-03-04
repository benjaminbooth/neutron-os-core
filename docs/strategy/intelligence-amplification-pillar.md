# Intelligence Amplification Pillar

**Strategic capability: Maximizing the impact of human and agent intelligence through continuous signal sensing, synthesis, and adaptive feedback.**

---

| Property | Value |
|----------|-------|
| Version | 1.0 |
| Last Updated | 2026-02-24 |
| Status | Draft |
| Owner | Ben Booth |

---

## Executive Summary

NeutronOS isn't just a platform for nuclear facility operations—it's an **intelligence amplification system**. This pillar formalizes the continuous feedback loop that:

1. **Casts the widest net** on value signal (voice memos, meetings, code, research, decisions)
2. **Synthesizes atomic signals** into actionable intelligence (PRDs, Tech Specs, issues)
3. **Routes to subscriber endpoints** for maximum impact (GitLab, OneDrive, RAG, briefings)
4. **Senses downstream effects** to measure impact and close the loop
5. **Continuously improves** loop velocity, quality, and coverage over time

### Why This Matters

Mission-critical systems (nuclear reactors, medical isotope production, research facilities) require:

- **Decisions informed by all available intelligence** — not just what's in email
- **Creators empowered with context** — not drowning in fragmented inputs
- **Continuous learning** — loop health metrics that improve over time
- **Human-in-the-loop governance** — agents inform, humans approve
- **Safer operations** — fewer missed signals, faster response to emerging issues

---

## The Intelligence Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│    ┌──────────┐      ┌─────────────┐      ┌──────────┐      ┌───────────┐  │
│    │  SENSE   │ ──── │  SYNTHESIZE │ ──── │  CREATE  │ ──── │  PUBLISH  │  │
│    └──────────┘      └─────────────┘      └──────────┘      └───────────┘  │
│         ▲                                                         │        │
│         │                                                         │        │
│         │                    FEEDBACK SENSED                      │        │
│         └─────────────────────────────────────────────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stage 1: SENSE — Signal Extraction

**Goal:** Capture intelligence from everywhere humans and agents communicate.

**Sources:**
| Source Type | Examples | Extractor |
|-------------|----------|-----------|
| **Voice/Video** | Voice memos, meetings, lectures, 1:1s | Whisper → Media Library |
| **Calendar** | Events, attendees, notes | Calendar extractor |
| **Notes** | Personal notes, whiteboards, freetext | Text extractor |
| **Code** | GitLab MRs, commits, issues | GitLab extractor |
| **Chat** | Slack, Teams threads | Chat extractor |
| **Documents** | PRDs, Tech Specs, research papers | Document extractor |
| **Operational** | Logs, metrics, alerts | Ops extractor |

**Outputs:** Raw `Signal` entities with metadata (source, timestamp, people, type, confidence)

**Key Capability: Media Library**

The [Media Library](../../tools/pipelines/sense/media_library.py) indexes all recorded audio/video:
- Hybrid search (keyword + semantic with auto-detection)
- Participant detection (maps speakers to people registry)
- Segment extraction for sharing in PRDs
- `NeutExplainer` for LLM-powered discussion, summarization, teaching

```bash
# Search recordings
neut media search "DocFlow architecture decision" --discuss

# Extract action items
neut media discuss <id> --actions

# Explain technical concepts
neut media discuss <id> --concepts
```

### Stage 2: SYNTHESIZE — Pattern Recognition & Actionable Outputs

**Goal:** Transform raw signals into actionable intelligence.

**Activities:**
- Cluster signals by PRD/initiative/person
- Generate PRD update drafts
- Generate design briefs for designers
- Generate issue drafts for builders
- Generate stakeholder briefings

**Key Components:**
- `correlator.py` — Entity resolution (map signals to people, initiatives, issues)
- `synthesizer.py` — Cross-source signal merging
- `signal_rag.py` — Unified RAG for all NeutronOS knowledge

**Outputs:**
| Artifact | Audience | Purpose |
|----------|----------|---------|
| PRD update drafts | Product | Requirements changes |
| Design briefs | Designers | UX/UI work items |
| Issue drafts | Builders | Implementation tasks |
| Briefing narratives | Stakeholders | Status communication |

### Stage 3: CREATE — Design & Development

**Goal:** Produce hardened designs and implementations from synthesized intelligence.

**Subscribers:**
- Designers receive design briefs + early feedback signals
- Builders receive design specs + PRD clarifications
- Researchers receive relevant signals for their initiatives

**Outputs:**
- Design specifications
- Wireframes / prototypes
- Implementation-ready code
- Research publications

### Stage 4: PUBLISH — Delivery to Endpoints

**Goal:** Route intelligence and artifacts to where they create impact.

**Subscriber Endpoints:**

| Endpoint | Purpose | Provider(s) |
|----------|---------|-------------|
| **Unified RAG (Neut)** | All NeutronOS knowledge | pgvector + signal_rag |
| **PRD/Tech Spec** | Formalized requirements | GitLab repo (.md), OneDrive (.docx) |
| **Issue Tracking** | Action items → issues | GitLab (primary), Linear, Jira |
| **Collaborative Docs** | Stakeholder review/edit | OneDrive, Google Workspace |
| **Stakeholder Briefings** | Narrative summaries | Email, Slack, Teams |

**DocFlow Integration:**

DocFlow synchronizes `.md` (repo) and `.docx` (collaborative) versions:
- Human edits in Office 365 → reconcile back to `.md`
- Agent edits in `.md` → publish to Office 365
- Diagram intelligence (Mermaid parsing) is a Sense capability

### Stage 5: FEEDBACK — Close the Loop

**Goal:** Sense the downstream effects of published intelligence.

**Feedback Sources:**
- User feedback (usability studies, support tickets, analytics)
- Review comments on published docs
- Issue status changes (closed, blocked, reopened)
- Deployment metrics (features shipped, bugs introduced)

**Feedback Types:**
| Type | Question | Measurement |
|------|----------|-------------|
| **Usefulness** | Does it solve the problem? | User feedback, adoption |
| **Ease of use** | Is it intuitive? | Usability studies, support tickets |
| **Performance** | Is it fast/reliable? | Metrics, error rates |
| **Completeness** | What's missing? | Feature requests, gaps |

**Loop Closure:** When feedback is sensed, it becomes a new signal → feeds back into SENSE.

---

## Loop Health Metrics

### Velocity Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Cycle Time** | Signal sensed → feature shipped | Decreasing |
| **Sense Latency** | Event occurs → signal captured | < 24 hours |
| **Synthesis Latency** | Signal captured → actionable output | < 4 hours |
| **Create Latency** | Brief received → design complete | Tracked |
| **Publish Latency** | Design approved → shipped | Tracked |
| **Feedback Latency** | Feature shipped → feedback sensed | < 7 days |

### Quality Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Signal Quality** | Average confidence of extracted signals | > 0.7 |
| **Synthesis Accuracy** | % of drafts approved without major edits | > 80% |
| **Design Hit Rate** | % of designs that ship without major rework | > 70% |
| **Rework Rate** | % of features requiring post-ship fixes | Decreasing |

### Throughput Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Signals/Day** | Raw signals captured daily | Tracked |
| **Synthesis/Day** | PRD updates, briefs generated | Tracked |
| **Designs/Week** | Design specs completed | Tracked |
| **Features/Sprint** | Features shipped per sprint | Tracked |

### Loop Health Score

```
Loop Health Score = f(
  velocity_improvement,
  quality_scores,
  throughput_trend,
  feedback_loop_closure_rate
)

Target: Loop Health Score improving quarter-over-quarter
```

---

## Unified RAG Architecture

**Principle:** ONE RAG system for all NeutronOS knowledge.

```
Signal Sources (all feed into ONE RAG)
├── Media Library (voice memos, meetings, lectures)
├── Calendar + Notes
├── GitLab (issues, MRs, code, wiki)
├── PRDs / Tech Specs (.md files)
├── Slack / Teams
├── Email
└── Operational data (logs, metrics)

       ↓ embeddings (pgvector)
       
   [UNIFIED RAG: signal_rag.py + pgvector_store.py]
   
       ↓
       
   Neut answers questions about ANYTHING
   - "What was decided about DocFlow?" → surfaces session notes, meetings, ADRs
   - "Who is working on the pump experiment?" → calendar, project tracking, recordings
   - "What's the status of medical isotope production?" → PRDs, ops logs, signals
```

**Key Design Decisions:**
- **PostgreSQL + pgvector** — single embedding store, scales with infrastructure
- **No parallel RAG systems** — DocFlow diagram intelligence is a Sense capability, not separate
- **Model-agnostic** — supports OpenAI, local LLMs (Llama, Mistral), keyword fallback

---

## Provider/Factory Architecture

Intelligence Amplification uses the NeutronOS Provider/Factory pattern for extensibility:

### Issue Tracking Provider

```python
# tools/pipelines/sense/providers/issue_tracking/base.py
class IssueTrackingProvider(ABC):
    @abstractmethod
    def create_issue(self, title: str, body: str, labels: list[str]) -> str: ...
    
    @abstractmethod
    def update_issue(self, issue_id: str, updates: dict) -> bool: ...
    
    @abstractmethod
    def link_signal(self, issue_id: str, signal_id: str) -> bool: ...
```

**Implementations:**
| Provider | Status | Notes |
|----------|--------|-------|
| `GitLabIssueProvider` | Primary | Main issue tracker |
| `LinearIssueProvider` | Extension | For teams using Linear |
| `JiraIssueProvider` | Future | Enterprise integration |

### Document Publishing Provider

```python
# tools/docflow/providers/storage.py
class StorageProvider(ABC):
    @abstractmethod
    def upload(self, content: bytes, path: str) -> str: ...
    
    @abstractmethod
    def download(self, path: str) -> bytes: ...
```

**Implementations:**
| Provider | Status | Notes |
|----------|--------|-------|
| `OneDriveProvider` | Active | Office 365 integration |
| `GoogleDriveProvider` | Active | Google Workspace |
| `LocalStorageProvider` | Active | Development/testing |

---

## Competitive Moat

Most "AI assistant" systems are one-shot: prompt in, response out. Intelligence Amplification is a **continuous, measured, self-improving loop**.

### Moat Deepens Through:

1. **Signal Diversity** — More sources → richer synthesis → better decisions
2. **Correlation Accuracy** — Entity resolution (people, initiatives) improves with feedback
3. **Loop Velocity** — Faster cycles → more learning → better adaptation
4. **Institutional Memory** — RAG accumulates context; new team members onboard faster
5. **Measurable Improvement** — Loop health metrics drive continuous optimization

### What Competitors Miss:

| Gap | NeutronOS Approach |
|-----|-------------------|
| One-shot LLM calls | Continuous feedback loop |
| Single-source context | Omnichannel signal sensing |
| No measurement | Loop health metrics |
| Human OR agent | Human-in-the-loop governance |
| Generic assistant | Domain-specific (nuclear, research, ops) |

---

## Implementation Phases

### Phase 0: Foundation (Current)
- [x] Sense extractors (voice, calendar, notes)
- [x] Media Library with hybrid search
- [x] NeutExplainer for recording discussion
- [x] Basic signal correlation
- [x] PRD/briefing synthesis
- [ ] Infrastructure (K3D, PostgreSQL, pgvector)
- [ ] DocFlow → Sense consolidation

### Phase 1: Loop Instrumentation
- [ ] Signal quality scoring
- [ ] Synthesis accuracy tracking
- [ ] Loop closure detection
- [ ] Basic health dashboard

### Phase 2: Subscriber Expansion
- [ ] GitLab issue generation from signals
- [ ] Design brief synthesis
- [ ] Automated stakeholder briefings
- [ ] Cross-initiative signal routing

### Phase 3: Feedback Loop
- [ ] User feedback extractors
- [ ] Review comment sensing
- [ ] Deployment impact tracking
- [ ] Loop velocity optimization

### Phase 4: Self-Improvement
- [ ] ML-based signal routing
- [ ] Automated bottleneck detection
- [ ] Velocity optimization recommendations
- [ ] Cross-initiative learning

---

## Success Criteria

**Year 1:**
- Loop fully instrumented with baseline metrics
- Sense latency < 24 hours for all configured sources
- Synthesis accuracy > 60% (drafts approved with minor edits)
- Manual loop closure < 30 days average

**Year 2:**
- 50% reduction in cycle time
- Automated synthesis for 80% of signals
- Designer/builder subscriptions active
- Loop health dashboard operational

**Year 3:**
- Continuous improvement loop self-optimizing
- < 14 day average cycle time
- User feedback integrated within 48 hours
- Institution-wide adoption across research programs

---

## Related Documents

- [Design Loop Architecture](../specs/design-loop-architecture.md) — Technical specification
- [Agent State Management PRD](../prd/agent-state-management-prd.md) — Agent patterns
- [Data Platform PRD](../prd/data-platform-prd.md) — Lakehouse architecture
- [Neut CLI PRD](../prd/neut-cli-prd.md) — CLI commands
- [DocFlow Consolidation Session](.neut/SESSION_2026-02-24_docflow_consolidation.md) — Architecture decision

---

## Open Questions

1. How do we handle conflicting signals from different sources?
2. What's the right granularity for loop tracking (feature vs. initiative vs. signal)?
3. How do agents participate in CREATE/PUBLISH stages without human approval bottleneck?
4. How do we measure "joy to use" quantitatively?
5. When does a loop "close" vs. continue iterating?
6. How do we balance signal breadth (cast wide net) vs. noise filtering?
