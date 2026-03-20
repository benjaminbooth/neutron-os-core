# ADR-006: Agentic Access — MCP Server + CLI as Primary Interfaces

**Status:** Accepted (updated 2026-03-16)
**Date:** 2026-01-15 (original), 2026-03-16 (revised)
**Decision Makers:** Ben Booth, Team

## Context

NeutronOS agents and LLM-powered applications need programmatic access to
platform data and operations. Two access patterns have emerged:

1. **MCP (Model Context Protocol)** — Anthropic's open standard for LLM ↔ tool
   communication. Claude Code, Cursor, and other AI IDEs use MCP to discover
   and invoke tools. NeutronOS exposes tools via an MCP server so any MCP-capable
   client can query reactor data, run signal pipeline operations, and publish docs.

2. **CLI as agentic interface** — The `neut` CLI is not just for humans. When an
   LLM agent runs inside `neut chat`, it should bias toward invoking deterministic
   CLI nouns+verbs (e.g., `neut signal ingest`, `neut pub push`) when a good match
   exists for the user's prompt. This gives agents predictable, testable behavior
   rather than generating ad-hoc code for every request.

**Key insight:** MCP and CLI are complementary, not competing. MCP is for
external clients (Claude Code, VS Code). The CLI is for the built-in chat agent
and terminal workflows. Both expose the same underlying operations.

## Decision

### 1. MCP Server (external agentic access)

We implement a Python MCP server exposing NeutronOS operations as tools.

**Implementation status:** ✅ Shipped (`src/neutron_os/mcp_server/`)

**Tool categories:**

| Category | Examples | Status |
|----------|----------|--------|
| Signal pipeline | `ingest_signals`, `get_briefing`, `search_signals` | ✅ Shipped |
| Publisher | `generate_docx`, `publish_document`, `check_links` | ✅ Shipped |
| RAG | `search_knowledge`, `index_document` | ✅ Shipped |
| Status | `system_health`, `connection_status` | ✅ Shipped |
| Query | `query_reactor_timeseries`, `search_log_entries` | 🔲 Planned (needs data platform) |
| Digital twin | `get_dt_prediction`, `compare_prediction_actual` | 🔲 Planned (needs DT implementation) |

### 2. CLI as agentic interface (internal chat agent)

The `neut chat` agent biases toward deterministic CLI operations:

```
User: "catch me up on what happened this week"
  → Agent recognizes: neut signal brief
  → Runs CLI command (deterministic, testable)
  → Presents results in chat context

User: "publish the weekly summary to OneDrive"
  → Agent recognizes: neut pub push --endpoint onedrive
  → Runs CLI command
  → Reports success/failure

User: "what's the keff convergence in my latest MCNP run?"
  → No CLI match → LLM generates response from context/RAG
```

**CLI slash commands** are a human-centric subset of the full CLI:

| Slash Command | Maps To | Context |
|---------------|---------|---------|
| `/brief` | `neut signal brief` | Catch up on signals |
| `/status` | `neut status` | System health |
| `/publish <file>` | `neut pub push <file>` | Publish a document |
| `/connect` | `neut connect` | Manage connections |
| `/update` | `neut update` | Self-update |

The full CLI (`neut signal ingest --source teams-browser --days 30`) remains
available to both humans and agents. Slash commands are shortcuts for the
most common operations during chat.

### 3. Terminal activity monitoring (future)

The chat agent will be able to monitor terminal activity and offer to
"continue" in an LLM context. When the user runs a CLI command that
produces output (e.g., `neut signal status`), the chat agent can pick up
that context and discuss it — similar to how Claude Code observes terminal
output and offers follow-up assistance.

This enables fluid transitions:
```
$ neut signal status           # User runs CLI command
  Inbox: 3 unprocessed
  Drafts: 1 ready for review

$ neut chat                    # User enters chat
  [Context: you just ran neut signal status and saw 3 unprocessed signals]

> process those signals and draft a summary
  → Agent runs: neut signal ingest && neut signal draft
```

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    External Clients                             │
│  Claude Code  │  VS Code  │  Cursor  │  Custom Agents          │
└───────┬───────┴─────┬─────┴────┬─────┴──────┬──────────────────┘
        │ MCP (stdio) │          │            │
        ▼             ▼          ▼            ▼
┌────────────────────────────────────────────────────────────────┐
│                    NeutronOS MCP Server                         │
│              src/neutron_os/mcp_server/                         │
└───────────────────────┬────────────────────────────────────────┘
                        │ same operations
┌───────────────────────▼────────────────────────────────────────┐
│                    neut CLI                                      │
│  neut signal  │  neut pub  │  neut chat  │  neut connect  │ ...│
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│                    Extension System                              │
│  signal_agent  │  publisher  │  chat_agent  │  mo_agent  │ ... │
└────────────────────────────────────────────────────────────────┘
```

## Alternatives Considered

| Alternative | Reason Not Selected |
|-------------|---------------------|
| GraphQL API only | LLMs work better with tool-call patterns than query languages |
| REST endpoints only | No standardized tool discovery for agents |
| MCP only (no CLI bias) | CLI commands are more predictable and testable than LLM-generated code |
| Separate agent framework | Unnecessary — CLI commands ARE the agent actions |

## Consequences

### Positive
- AI agents get structured, discoverable tool access (MCP)
- Chat agent uses deterministic operations when possible (CLI bias)
- Same operations available through both interfaces
- Slash commands give humans quick access to common operations
- Terminal continuity creates fluid CLI ↔ chat transitions

### Negative
- Two interfaces to maintain (MCP + CLI), though they share the same backend
- CLI bias requires maintaining a mapping of prompts → CLI commands
- Terminal monitoring adds complexity to the chat agent

### Mitigations
- MCP tools and CLI commands are thin wrappers around the same extension functions
- Prompt → CLI mapping uses the existing extension registry (no separate config)
- Terminal monitoring is opt-in and degrades gracefully

## Related Documents

- [ADR-010: CLI Architecture](adr-010-cli-architecture.md) — Tech stack, terminal monitoring, slash commands
- [Connections Spec](../tech-specs/spec-connections.md) — Connection-level access for MCP tools
- [Model Routing Spec](../tech-specs/spec-model-routing.md) — Export control for agent queries
- [MCP Protocol](https://modelcontextprotocol.io/) — Anthropic's open standard
