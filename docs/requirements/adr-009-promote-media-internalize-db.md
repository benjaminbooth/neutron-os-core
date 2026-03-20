# ADR-009: Promote Media to Top-Level Noun, Internalize Database Management

**Status:** Accepted
**Date:** 2026-02-26
**Decision Makers:** Ben

## Context

The `neut signal` module accumulated two responsibilities that don't belong to it:

1. **`neut signal db`** — Exposes database migration, clustering, and schema
   management commands directly to end users. The target personas (reactor
   operators, nuclear engineering researchers, compliance officers) have no use
   for `neut signal db migrate` or `neut signal db stats`. This is a leaky
   abstraction: implementation plumbing surfaced as a user-facing command.

2. **`neut signal media`** — A media library (recordings, images, documents with
   metadata, vector search, access control) that is useful far beyond signal
   extraction. The Experiment Manager needs photos of samples. Reactor Ops Log
   needs inspection recordings. Compliance needs evidence artifacts. Training
   needs instructional media. Trapping media under sense forces every other
   module to import from sense's internals, creating tight coupling.

**Root cause:** Successive agentic coding sessions indexed deeply on the sense
pipeline and conflated it with the broader platform vision described across the
full set of PRDs. Features that belong at the platform level were implemented
in whatever module happened to be in context.

## Decision

### 1. Promote `media` to a first-class CLI noun

```
neut media ingest <file>       # Add media to the library
neut media search <query>      # Semantic + metadata search
neut media list                # Browse the library
neut media tag <id> <tags>     # Add metadata tags
neut media link <id> <entity>  # Associate with experiment, log entry, etc.
neut media export <id>         # Export for compliance or sharing
```

Media becomes a platform service consumed by Neut Signal, Experiment Manager, Ops Log,
Compliance, and any future module. Neut Signal becomes a *consumer* of
media (indexing recordings for signal extraction), not the *owner* of the media
library.

### 2. Internalize `db` under setup/infra

Database lifecycle commands move out of the user-facing CLI:

- **`neut config`** handles initial database provisioning as part of first-run
  setup (already has a wizard flow)
- **`neut infra`** handles migration, schema verification, and health checks
  for administrators
- Direct `neut signal db` commands are removed from the default `--help` output

## Alternatives Considered

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Promote media, internalize db** | Clean separation of concerns, media reusable across modules | Requires refactoring sense imports | Selected |
| **Keep media under sense, add re-exports** | No refactoring needed | Perpetuates coupling, confusing for contributors | Rejected |
| **Create a `neut data` noun for both** | Groups storage concerns | Conflates media (user-facing) with db (admin plumbing) | Rejected |
| **Do nothing** | Zero effort | New modules will depend on sense internals | Rejected |

## Consequences

### Positive

- Media library is discoverable and usable by all modules without importing sense
- Database management is hidden from non-admin users, reducing CLI noise
- Clear ownership boundaries: sense owns intelligence, media owns storage
- New contributors aren't confused by DBA commands in a signal extraction tool
- Aligns with the reactor-agnostic plugin architecture (media is generic, sense
  signal types are facility-specific)

### Negative

- Existing code in `tools/pipelines/sense/pgvector_store.py` and
  `tools/pipelines/sense/media_library.py` needs to move to `tools/media/`
- Tests referencing `sense.media` and `sense.db` need updated imports
- Two-phase migration: old paths work during transition, removed later

### Mitigations

- Use Python re-exports during transition (`from tools.media import X` works,
  old `from tools.pipelines.sense.media_library import X` emits deprecation warning)
- Create a migration checklist in the media PRD
- Single PR for the move, with mechanical import updates

## Implementation

```
tools/
  media/                         # NEW — promoted from sense
    __init__.py
    cli.py                       # neut media subcommands
    library.py                   # Media library (from sense/media_library.py)
    store.py                     # Vector store (from sense/pgvector_store.py)
    models.py                    # MediaItem, MediaCollection dataclasses
  agents/
    sense/
      media_library.py           # DEPRECATED — re-exports from tools.media
      pgvector_store.py          # DEPRECATED — re-exports from tools.media
      cli.py                     # Remove 'db' and 'media' subcommands
  db/
    cli.py                       # Existing — absorbs sense db commands
```

## References

- [Media Module PRD](../prd/media-library-prd.md)
- [Executive PRD — Product Modules](../prd/neutron-os-executive-prd.md)
- [CLI Design PRD](../prd/neut-cli-prd.md)
- [Agent Architecture Spec](../tech-specs/spec-agent-architecture.md)
