# `spikes/` — Active Experiments

Time-boxed prototypes and proof-of-concept work. M-O (the resource steward
agent) manages the lifecycle of items here.

## What belongs here

- Experimental prototypes exploring new approaches
- Proof-of-concept code that may graduate to an extension
- Research implementations with uncertain outcomes

## What does NOT belong here

- **Production code** → `src/neutron_os/extensions/builtins/{name}/`
- **Retired experiments** → `archive/`
- **Documentation research** → `docs/research/`

## AI Agent Policy

Spikes are throwaway by design. Do not import from `spikes/` in production
code. When a spike proves successful, extract the learnings into a proper
extension — do not promote the spike directory directly. Each spike should
have its own README explaining the hypothesis and outcome.
