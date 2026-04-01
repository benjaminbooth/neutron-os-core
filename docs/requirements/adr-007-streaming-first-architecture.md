# ADR-007: Streaming-First Architecture with Batch Fallbacks — Neutron OS Nuclear Context

> This architecture decision is made at the Axiom platform level. This document captures nuclear-specific context only.

**Upstream:** [Axiom adr-007-streaming-first-architecture.md](https://github.com/…/axiom/docs/requirements/adr-007-streaming-first-architecture.md)

---

## Nuclear Context

### Why Streaming Matters for Nuclear

- **Reactor telemetry** is safety-critical and benefits significantly from real-time updates
- **NRC** is moving toward continuous monitoring; batch reports will not satisfy future regulatory expectations
- Today's research reactors generate megabytes per day; tomorrow's commercial fleet generates **petabytes**
- This architecture handles one research reactor today and fifty commercial units tomorrow without rewrites

### Nuclear-Specific Streaming Capabilities

| Capability | Why Streaming Is Required |
|------------|---------------------------|
| **Fleet-wide anomaly correlation** | Detect patterns across 50 units in real-time; batch delays miss transients |
| **Instant safety limit propagation** | Updated operating envelope flows to all systems in <1 second |
| **Coordinated load-following** | Grid demand response requires sub-second coordination across units |
| **Predictive maintenance at scale** | ML models need live sensor feeds to detect degradation before failure |
| **Regulatory real-time audit** | NRC moving toward continuous monitoring; batch reports won't satisfy |

### Deployment Note

NeutronOS targets cloud-agnostic deployment across TACC, AWS, GCP, and on-premises environments. Self-hosted Redpanda (or Apache Kafka KRaft per the Axiom ADR amendment) is required for air-gapped DOE facility deployments.

### Nuclear UI Example

```
Reactor Power: 950 kW
Live (streaming)
```

When streaming degrades, staleness warnings are critical in a reactor operations context where operators must know data freshness to make safe decisions.

### NeutronOS API Conventions

WebSocket subscriptions use nuclear-domain topics:

```javascript
ws.subscribe('reactor.status', { facility: 'netl-triga' }, (event) => {
  updateDisplay(event.data);
});
```

REST fallback:
```
GET /api/v1/reactor/status?facility=netl-triga
```
