# Neutron OS Brand Identity

*Last updated: 2026-01-27*

## Positioning

### The Core Tension

| Audience | They Think About | They Don't Say |
|----------|------------------|----------------|
| Reactor Operator | Situational awareness, shift turnover, compliance burden | "Digital twin" |
| Plant Manager | Capacity factor, NRC findings, workforce pipeline | "Machine learning" |
| NRC Inspector | 10 CFR 50.59 screens, audit trails, traceability | "AI agents" |
| Researcher | Novel methods, publications, funding | "Operations" |

### Market Evolution

```
Today (2026)           Near-term (2028)        Target (2030+)
─────────────────────────────────────────────────────────────
Research Platform  →   Pilot Deployments   →   Commercial Fleet
Universities           National Labs           Utilities
DOE/NEUP funding       GAIN vouchers           Subscription/SaaS
```

**Current reality:** Research platform proving concepts with TRIGA, MSR experiments, bubble loop instrumentation.

**North star:** The operating system for commercial reactor operations—invisible infrastructure that makes operators smarter without asking them to become data scientists.

---

## Tagline Exploration

### Rejected

| Tagline | Why Not |
|---------|---------|
| "The auditable digital twin platform" | Tech speak; operators don't think in "twins" |
| "AI for nuclear" | Vague; everyone claims this |
| "Nuclear digital transformation" | Consultant buzzwords |

### Candidates

| Tagline | Positioning | Audience |
|---------|-------------|----------|
| "Reactor intelligence, always auditable" | Outcome + differentiator | Commercial |
| "From sensor to decision—trusted" | Data flow + trust | Operations |
| "The nuclear operations platform" | Simple, direct | Universal |
| "Intelligence infrastructure for nuclear" | Platform play | Enterprise |
| "Decisions at the speed of neutrons" | Evocative, memorable | Marketing |
| **"The intelligence platform for nuclear power reactors"** | **Adopted** | **Universal** |

### Working Tagline

> **"The intelligence platform for nuclear power reactors"**

Rationale:
- "Intelligence" signals decision support, not just data collection
- "Platform" conveys ecosystem/infrastructure, not point solution
- "Nuclear power reactors" is specific to our target market (commercial fleet)
- Implies AI/ML capabilities without using buzzwords
- Works for both research and commercial contexts

---

## CLI Identity

### Command: `neut`

```bash
# Short, memorable, unique
$ neut

# Not neutr (incomplete), neutron (too long), ntn (unpronounceable)
```

### Mascot: The Newt 🦎

A newt (salamander) provides:
- **Visual pun:** neut → newt
- **Personality:** Curious, adaptable, regenerative
- **Symbolism:** Salamanders historically associated with fire/transformation
- **Design flexibility:** Can show neutrons emanating from the newt

#### Mascot Variants

| Variant | Use Case |
|---------|----------|
| Newt with neutron orbits | Primary logo |
| Newt silhouette | Favicon, CLI spinner |
| Newt with hardhat | Operations/safety contexts |
| Newt with graduation cap | Learning/research contexts |
| Sleeping newt | Idle/waiting states |
| Alert newt | Notifications/warnings |

### Command Structure

```bash
neut <domain> <action> [target] [flags]

# Examples
neut sim run scenario.yaml          # Run simulation
neut log query --last 1h            # Query ops log
neut model list --type surrogate    # List ML models
neut audit export --format nrc      # Export audit trail
neut twin sync facility-001         # Sync digital twin state
neut teach neutronics               # Learning mode (ben-learning tie-in)
```

### Reserved Subcommands

| Command | Purpose |
|---------|---------|
| `neut sim` | Simulation orchestration |
| `neut model` | Surrogate/ML model management |
| `neut log` | Ops log queries |
| `neut audit` | Audit trail and compliance |
| `neut twin` | Digital twin state management |
| `neut data` | Data platform operations |
| `neut infra` | Infrastructure management |
| `neut teach` | Learning/education mode |
| `neut agent` | AI agent interactions |
| `neut ext` | Extension management (WASM plugins) |

---

## Naming Conventions

### Services

| Pattern | Example | Notes |
|---------|---------|-------|
| `neutron-<function>` | `neutron-gateway`, `neutron-log` | Public-facing services |
| `neut-<internal>` | `neut-scheduler`, `neut-cache` | Internal components |

### Data Assets

| Pattern | Example |
|---------|---------|
| `neos_<domain>_<entity>` | `neos_ops_log_entries` |
| `neos_<domain>_<entity>_<version>` | `neos_ml_surrogates_v2` |

### Code Packages

| Language | Pattern |
|----------|---------|
| Python | `neutron_<module>` |
| Rust | `neutron-<crate>` |
| TypeScript | `@neutron/<package>` |

---

## Voice & Tone

### Principles

1. **Trustworthy over clever** - Nuclear industry demands credibility
2. **Clear over comprehensive** - Operators are busy, respect their time
3. **Confident over hedging** - "Neutron OS provides X" not "Neutron OS can help with X"
4. **Technical over marketing** - Our audience detects BS immediately

### Examples

| ❌ Avoid | ✅ Prefer |
|----------|----------|
| "Leverage AI to optimize reactor performance" | "Surrogate models predict state 1000x faster than full simulation" |
| "Seamless integration" | "REST API. gRPC. OpenTelemetry. Pick your protocol." |
| "Enterprise-grade security" | "WASM sandboxing. Capability-based permissions. Deterministic replay." |
| "Digital transformation journey" | "Here's the API. Here's the audit trail. Ship it." |

---

## Visual Identity

### Color Palette (Proposed)

| Name | Hex | Use |
|------|-----|-----|
| Neutron Blue | `#1E3A5F` | Primary brand |
| Reactor Cyan | `#00A9CE` | Accents, links |
| Caution Amber | `#F5A623` | Warnings |
| Critical Red | `#D0021B` | Errors, alerts |
| Success Green | `#7ED321` | Confirmations |
| Slate Gray | `#4A4A4A` | Body text |
| Paper White | `#FAFAFA` | Backgrounds |

### Typography

| Use | Font | Fallback |
|-----|------|----------|
| Headings | Inter | system-ui |
| Body | Inter | system-ui |
| Code | JetBrains Mono | monospace |

### Logo Concepts

```
┌─────────────────────────────────────┐
│                                     │
│     ○                               │
│    ╱│╲    ←── neutron orbits        │
│   ○─●─○                             │
│    ╲│╱                              │
│     ○                               │
│                                     │
│   🦎  ←── newt silhouette           │
│                                     │
│   N E U T R O N   O S               │
│                                     │
└─────────────────────────────────────┘
```

---

## Appendix: Name Origin

**Neutron OS** — The neutron is:
- The particle that sustains fission (the chain reaction)
- Electrically neutral (impartial, trustworthy)
- The messenger between nuclei (like our platform between systems)
- What operators actually care about (neutron flux, reactivity)

The name works because it's technically meaningful to the domain while being accessible to broader audiences.
