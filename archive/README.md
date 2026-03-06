# `archive/` — Retired Code and Documents

Code and documents that are no longer active but preserved for reference.
M-O (the resource steward agent) manages the lifecycle of items here.

## What belongs here

- Retired implementations superseded by new approaches
- Historical spikes that informed current design
- Old documents moved here during cleanup

## What does NOT belong here

- **Active code** → `src/neutron_os/`
- **Active experiments** → `spikes/`
- **Active documentation** → `docs/`

## AI Agent Policy

Do not import from or depend on anything in `archive/`. Code here is dead.
When archiving, move the entire directory and note the reason in the commit
message. Do not delete archived code — it serves as historical reference.
