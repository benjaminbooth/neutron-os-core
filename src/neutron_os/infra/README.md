# `infra/` — Shared Platform Infrastructure

Shared infrastructure that extensions depend on but do not own. This is NOT
an extension — it's the foundation layer.

## Contents

- `gateway.py` — Model-agnostic LLM routing (OpenAI-compatible endpoints)
- `orchestrator/` — Event bus, actions, approval workflow, session management
- `subscribers/` — Platform-level event subscribers
- `self_heal.py` — Self-healing and recovery logic
- `auth/` — Authentication/authorization (placeholder)

## What belongs here

- LLM gateway and model routing
- Event bus and action orchestration
- Cross-extension infrastructure (auth, logging, metrics)
- Anything that multiple extensions need but no single extension owns

## What does NOT belong here

- **Extension code** → `extensions/builtins/{name}/`
- **CLI commands** → extensions register their own CLI nouns
- **Runtime data** → `runtime/`
- **Business logic** — if it serves one domain, it's an extension

## AI Agent Policy

This directory should change rarely. Adding code here means every extension
potentially depends on it. Prefer putting new functionality in an extension
unless it genuinely serves as shared infrastructure. Never add LLM prompts,
domain logic, or feature-specific code here.
