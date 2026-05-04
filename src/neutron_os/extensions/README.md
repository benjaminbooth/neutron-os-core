# `extensions/` — Extension System

The extension system implements NeutronOS's core principle: **everything is
an extension**. Web apps, agents, tools, utilities — all extensions.

## Structure

```
extensions/
  __init__.py        # Docstring: discovery order
  contracts.py       # Extension, CLICommandDef, provider ABCs
  discovery.py       # 3-tier discovery engine
  scaffold.py        # neut ext init
  cli.py             # neut ext list/info commands
  builtins/          # Domain-agnostic extensions shipped with the repo
```

## 3-Tier Discovery

Extensions are discovered in priority order:
1. **Project-local**: `.neut/extensions/` (highest priority)
2. **User-global**: `~/.neut/extensions/`
3. **Builtin**: `extensions/builtins/` (this repo)

## Extension Kinds

- `agent` — Has LLM autonomy (chat, sense, mo, doctor)
- `tool` — Capability invoked by agents or CLI (publisher, db, demo)
- `utility` — Platform plumbing (status, test, update)

## AI Agent Policy

Do not modify `contracts.py` or `discovery.py` without understanding the
full extension lifecycle. New extensions go in `builtins/` if domain-agnostic,
or in an external repo if domain-specific. Every extension MUST have an
`axiom-extension.toml` manifest conforming to AEOS 0.1
(`spec-aeos-0.1.md` in the axiom-os repo).
