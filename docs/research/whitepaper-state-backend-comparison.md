# Agent State Management in Offline-First AI Platforms: Flat Files vs. PostgreSQL

**A Measurable Comparison for Nuclear Facility Digital Infrastructure**

---

| Property | Value |
|----------|-------|
| Version | 1.0 |
| Date | 2026-03-14 |
| Authors | Ben Booth, bbooth@utexas.edu |
| Context | NeutronOS — Modular digital platform for nuclear facilities |
| Code | `src/neutron_os/infra/state.py`, `src/neutron_os/infra/state_pg.py` |
| Benchmarks | `tests/infra/test_state_benchmark.py` |

---

## Abstract

Autonomous AI agents operating in nuclear facility environments accumulate state across dozens of filesystem locations — transcripts, corrections, session history, configuration, and document registries. When multiple agents operate concurrently on the same machine or across a team, state corruption becomes inevitable without proper coordination. This paper presents a measurable comparison of two state management approaches implemented in NeutronOS: advisory file locking (`fcntl.flock` with atomic writes) and PostgreSQL with ACID transactions. We provide benchmark data for throughput, latency, correctness under concurrency, and analyze implications for LLM token efficiency in agent-database interaction patterns.

---

## 1. Problem Statement

NeutronOS agents accumulate state in 17+ filesystem locations. Six shared JSON files are accessed by multiple agents:

| File | Concurrent Writers | Corruption Mode |
|------|-------------------|----------------|
| `.publisher-registry.json` | Publisher, Sense | Lost document mappings |
| `.publisher-state.json` | Publisher, Sense | Corrupt lifecycle state |
| `briefing_state.json` | Sense, Chat | Lost briefing progress |
| `user_glossary.json` | Sense, Review | Lost learned corrections |
| `propagation_queue.json` | Sense, Review | Duplicate/lost propagations |
| `sessions/*.json` | Chat, Sense | Corrupt session history |

The naive approach — `json.loads(path.read_text())` / `path.write_text(json.dumps(...))` — provides no protection against concurrent access. Two processes reading the same file, modifying it independently, and writing back will silently lose one set of changes (lost update anomaly).

### 1.1 Why This Matters for Nuclear Facilities

Nuclear regulatory environments (NRC, DOE) require:
- **Data integrity** — no silent corruption of operational records
- **Audit trails** — verifiable history of all state changes
- **Compliance** — demonstrable retention policy enforcement
- **Availability** — offline-first operation during network outages

---

## 2. Approach A: Advisory File Locking (Flat Files)

### 2.1 Design

`LockedJsonFile` uses Unix `fcntl.flock` advisory locks with atomic writes:

```python
with LockedJsonFile(path, exclusive=True) as f:
    data = f.read()           # Shared or exclusive lock acquired
    data["counter"] += 1
    f.write(data)             # Write to tempfile, os.replace() atomically
# Lock released on exit
```

**Key mechanisms:**
- **Lock sidecar files** (`.json.lock`) — locking a separate file avoids interference with `os.replace()` which creates a new inode
- **Shared locks for reads** — multiple readers can proceed concurrently
- **Exclusive locks for writes** — writers serialize
- **Atomic writes** — `tempfile.mkstemp()` → write → `fsync` → `os.replace()` prevents partial writes on crash

### 2.2 Measured Performance (macOS, Apple M-series, APFS)

| Metric | Value |
|--------|-------|
| **Write throughput** | 3,039 ops/sec |
| **Write avg latency** | 0.329 ms |
| **Write p95 latency** | 0.494 ms |
| **Read throughput** | 24,502 ops/sec |
| **Read avg latency** | 0.041 ms |
| **Read p95 latency** | 0.044 ms |
| **Concurrent correctness** | 200/200 (4 processes × 50 increments) |
| **Concurrent total time** | 0.48s (200 ops) |
| **Concurrent avg per-op** | 3.6 ms |

### 2.3 Strengths

1. **Zero dependencies** — uses only Python stdlib (`fcntl`, `os`, `json`, `tempfile`)
2. **Offline-first** — works without network, database, or any service
3. **Fast reads** — 24K ops/sec for local filesystem reads
4. **Simple deployment** — no database provisioning, migration, or connection management
5. **Low token cost** — agent reads a file path, not a SQL query

### 2.4 Weaknesses

1. **Advisory only** — any code that doesn't use `LockedJsonFile` can still corrupt files. Non-participating processes are not prevented from writing.
2. **Single-machine** — `fcntl.flock` does not work across NFS or network filesystems. Multi-machine deployments require a different solution.
3. **No transaction isolation** — no rollback capability. If business logic fails after read but before write, no automatic recovery.
4. **No conflict detection** — last-write-wins. Two agents modifying different fields of the same document will silently overwrite each other's changes.
5. **No built-in audit trail** — requires separate JSONL append log (implemented, but not transactional with the state change).
6. **Lock file accumulation** — `.lock` sidecar files accumulate on disk (negligible space, but messy).
7. **Windows degradation** — `fcntl` unavailable on Windows; falls back to no-op (no locking).

---

## 3. Approach B: PostgreSQL with ACID Transactions

### 3.1 Design

`PgStateStore` stores JSON state in a `JSONB` column with row-level locking:

```python
store = PgStateStore("postgresql://localhost/neutron_os")
with store.open("my/state.json", exclusive=True) as handle:
    data = handle.read()       # SELECT ... FOR UPDATE (row lock)
    data["counter"] += 1
    handle.write(data)         # UPDATE with version check
# Transaction committed on exit, rolled back on exception
```

**Key mechanisms:**
- **Row-level locking** via `SELECT ... FOR UPDATE` (exclusive) or `SELECT ... FOR SHARE` (shared)
- **Optimistic concurrency** — version column incremented on write; concurrent modification detected
- **ACID transactions** — automatic rollback on exception
- **Built-in audit log** — every state change recorded in `state_audit_log` table within the same transaction

### 3.2 Measured Performance (K3D PostgreSQL 16.13, pgvector 0.8.2, port-forwarded)

| Metric | Value |
|--------|-------|
| **Write throughput** | 165 ops/sec |
| **Write avg latency** | 6.07 ms |
| **Write p95 latency** | 8.65 ms |
| **Read throughput** | 211 ops/sec |
| **Read avg latency** | 4.74 ms |
| **Read p95 latency** | 5.07 ms |
| **Concurrent correctness** | 200/200 (4 processes × 50 increments, 0 errors, 0 retries) |
| **Concurrent total time** | 1.10s (200 ops) |
| **Concurrent avg per-op** | 15.9 ms |

*Note: These numbers include port-forward overhead (~2-3ms per hop). A Unix
socket or localhost connection would be faster. Production deployment on the
same host would see roughly 2x improvement.*

### 3.3 Strengths

1. **Mandatory isolation** — ACID transactions enforced by the database engine, not by voluntary participation
2. **Multi-machine safe** — works across any number of processes on any number of machines
3. **Conflict detection** — optimistic concurrency with version column; `ConcurrentModificationError` raised on conflict
4. **Built-in audit trail** — `state_audit_log` table with timestamps, actors, version history, all within the same transaction as the state change
5. **Rollback** — if business logic fails, the entire transaction rolls back automatically
6. **Query capability** — `JSONB` supports indexing, partial updates, and path queries
7. **Crash recovery** — WAL (Write-Ahead Log) ensures durability even on power loss

### 3.4 Weaknesses

1. **Requires running PostgreSQL** — service must be provisioned, monitored, and maintained
2. **Not offline-first** — if the database is unreachable, all state operations fail
3. **Higher latency** — connection overhead adds ~0.5ms per operation vs. local file I/O
4. **Migration complexity** — schema changes require migration tooling (Alembic, etc.)
5. **Connection management** — pooling, timeout handling, reconnection logic needed for production
6. **Deployment weight** — PostgreSQL is a significant operational dependency for what might be a single-developer tool

---

## 4. Token Efficiency Analysis

In LLM-powered agent architectures, every state access pattern has implications for token consumption. This matters because:
- Agents read state to build context for LLM calls
- Larger state payloads = more input tokens = higher cost and slower inference
- State structure affects how efficiently agents can extract relevant information

### 4.1 Flat-File Token Implications

**Pattern:** Agent reads entire JSON file into context, processes it, writes back.

```python
# Agent reads entire file — all of it becomes context
with LockedJsonFile("briefing_state.json") as f:
    state = f.read()  # Full file content → LLM context
```

| Aspect | Impact |
|--------|--------|
| **Read granularity** | All-or-nothing. Agent gets entire file even if it needs one field. |
| **Token cost per read** | Proportional to file size. A 50KB JSON file ≈ 12,500 tokens. |
| **Context pollution** | Irrelevant fields consume context window budget. |
| **Structured extraction** | Agent must parse JSON in-context to find relevant data. |

**Mitigation:** Keep files small and focused. NeutronOS state files are typically <10KB each (≈2,500 tokens), which is manageable.

### 4.2 PostgreSQL Token Implications

**Pattern:** Agent issues targeted queries, receives only relevant data.

```python
# Agent can query specific fields — minimal context
cur.execute(
    "SELECT data->'counter' FROM agent_state WHERE path = %s",
    ("briefing_state.json",),
)
```

| Aspect | Impact |
|--------|--------|
| **Read granularity** | Surgical. JSONB path queries extract specific fields. |
| **Token cost per read** | Proportional to query result, not total state size. |
| **Context efficiency** | Only relevant data enters the LLM context window. |
| **Query generation** | Agent must generate SQL (or use a tool), adding ~50–100 tokens per query. |
| **Schema awareness** | Agent needs to know the schema, consuming context for tool descriptions. |

**Key insight:** For small state files (<10KB), the overhead of SQL query generation may exceed the savings from selective reads. For large state accumulations (>100KB total), PostgreSQL's selective queries become significantly more token-efficient.

### 4.3 Token Efficiency Crossover

```
Token cost per state access

    ^
    |  SQL overhead
    |  ─────────────── PostgreSQL total cost
    |  /
    | /
    |/_________________ File read cost
    |                   ─────────────── Flat file total cost
    |                                 /
    |                                /
    +────────────────────────────────────>
    0         10KB        50KB       100KB
              State size per access
```

**Crossover point:** ~20–30KB per state access. Below this, flat files are more token-efficient (no SQL overhead). Above this, PostgreSQL's selective queries save tokens.

### 4.4 Agent Tool Design Implications

For NeutronOS, where agents use function-calling (tool use) to interact with state:

**Flat-file tool definition (~50 tokens):**
```json
{"name": "read_state", "parameters": {"path": "string"}}
```

**PostgreSQL tool definition (~150 tokens):**
```json
{"name": "query_state", "parameters": {"path": "string", "fields": "string[]", "filter": "object"}}
```

The PostgreSQL tool is more expressive but costs ~100 more tokens per tool definition in the system prompt. Over a typical agent session with 10+ tool calls, this adds ~1,000 tokens of overhead that must be weighed against selective query savings.

**Recommendation:** Expose a unified `read_state` / `write_state` tool interface that abstracts the backend. The tool definition stays small (~50 tokens), and the backend (flat file vs. PostgreSQL) is a deployment configuration, not an agent concern.

---

## 5. Comparison Matrix

| Property | Flat File (fcntl) | PostgreSQL | Winner |
|----------|------------------|------------|--------|
| **Write throughput** | 3,039 ops/sec | 165 ops/sec | Flat file (18x) |
| **Read throughput** | 24,502 ops/sec | 211 ops/sec | Flat file (116x) |
| **Concurrent correctness** | ✅ (advisory) | ✅ (mandatory) | PostgreSQL |
| **Multi-machine** | ❌ | ✅ | PostgreSQL |
| **Conflict detection** | ❌ (last-write-wins) | ✅ (version check) | PostgreSQL |
| **Transaction rollback** | ❌ | ✅ | PostgreSQL |
| **Audit trail** | Separate JSONL file | Same transaction | PostgreSQL |
| **Crash recovery** | Atomic write only | Full WAL recovery | PostgreSQL |
| **Offline-first** | ✅ | ❌ | Flat file |
| **Dependencies** | None (stdlib) | PostgreSQL service | Flat file |
| **Deployment complexity** | Zero | Moderate | Flat file |
| **Token efficiency (<20KB)** | Better (no SQL overhead) | Worse | Flat file |
| **Token efficiency (>50KB)** | Worse (reads everything) | Better (selective) | PostgreSQL |
| **Windows support** | Degraded (no fcntl) | Full | PostgreSQL |

---

## 6. Failure Mode Analysis

### 6.1 Flat File Failure Modes

| Scenario | Outcome | Recovery |
|----------|---------|----------|
| Process crash during write | Atomic write prevents corruption; old data preserved | Automatic |
| Two processes write simultaneously | fcntl serializes; no data loss if both use LockedJsonFile | Automatic |
| Non-participating code writes directly | **Silent corruption** — no protection | Manual |
| Disk full during write | Temp file creation fails; original preserved | Manual |
| Power loss during os.replace() | Filesystem-dependent; APFS/ext4 journaling helps | Usually automatic |
| Lock file deleted while held | Lock silently released; corruption possible | Manual |

### 6.2 PostgreSQL Failure Modes

| Scenario | Outcome | Recovery |
|----------|---------|----------|
| Process crash during transaction | Transaction rolled back automatically | Automatic |
| Two processes write simultaneously | Row-level lock serializes OR version conflict raised | Automatic |
| Database connection lost | Operation fails with exception | Retry |
| Database crash | WAL replay recovers committed transactions | Automatic |
| Disk full | Transaction fails; no partial writes | Manual (free space) |
| Network partition (multi-machine) | Operations fail until reconnected | Automatic on reconnect |

### 6.3 Key Difference

**Flat files fail silently** when non-participating code bypasses locking. **PostgreSQL fails loudly** — there is no way to bypass ACID from within a transaction.

For a nuclear facility platform where silent data corruption is the worst outcome, PostgreSQL's mandatory isolation is the safer choice for any state that multiple agents access.

---

## 7. Recommendation

### Phase 0 (Current): Flat Files

`LockedJsonFile` is appropriate for:
- Single-developer, single-machine use
- Offline-first operation (no database required)
- Bootstrap and onboarding (before database is provisioned)
- State files <10KB that are only accessed by well-known NeutronOS code

### Phase 1.5 (Near-term): PostgreSQL for Shared State

Migrate to `PgStateStore` for:
- Any state accessed by multiple agents concurrently
- Any state that requires audit trails for compliance
- Multi-user deployments
- State files >20KB (token efficiency crossover)

### Phase 2 (Multi-user): PostgreSQL as Default

PostgreSQL becomes the default state backend. Flat files remain as:
- Fallback for offline operation
- Cache/scratch (M-O managed, already has its own lifecycle)
- Bootstrap state before database is available

### Hybrid Architecture

```
┌─────────────────────────────────────────────────────┐
│              Unified State Interface                 │
│         read_state() / write_state()                │
└──────────────┬──────────────────┬────────────────────┘
               │                  │
    ┌──────────▼──────────┐  ┌───▼────────────────────┐
    │   LockedJsonFile    │  │    PgStateStore         │
    │   (offline/boot)    │  │    (online/shared)      │
    │                     │  │                         │
    │  • fcntl.flock      │  │  • ACID transactions    │
    │  • atomic writes    │  │  • row-level locking    │
    │  • zero deps        │  │  • audit trail          │
    │  • 3K writes/sec    │  │  • conflict detection   │
    └─────────────────────┘  └─────────────────────────┘
```

The unified interface (`read_state`/`write_state`) abstracts the backend. Agents don't know or care which backend is active. Backend selection is a deployment configuration decision, not an agent design decision.

---

## 8. Side-by-Side Results (Read-Modify-Write, 100 iterations)

Measured on macOS Apple Silicon, K3D PostgreSQL 16.13 via port-forward:

| Metric | Flat File | PostgreSQL | Ratio |
|--------|-----------|------------|-------|
| **ops/sec** | 588 | 178 | 3.3x |
| **avg (ms)** | 1.70 | 5.64 | 3.3x |
| **p50 (ms)** | 1.39 | 5.52 | 4.0x |
| **p95 (ms)** | 3.63 | 6.24 | 1.7x |
| **p99 (ms)** | 4.88 | 9.13 | 1.9x |

Both backends produced correct final counts (100/100). The flat file backend
is 3-4x faster for single-process workloads. The gap narrows at the tail
(p95/p99) where filesystem fsync costs approach PostgreSQL commit costs.

For NeutronOS state files (typically <10KB, <50 ops/session), both backends
are effectively instantaneous from the user's perspective. The choice is
driven by safety guarantees and multi-user requirements, not raw throughput.

---

## 9. Reproducing the Benchmarks

```bash
# Flat-file benchmarks (no dependencies)
pytest tests/infra/test_state_benchmark.py -v -s -k "FlatFile"

# PostgreSQL benchmarks (requires running database)
export NEUTRON_TEST_DSN="postgresql://localhost/neutron_os_test"
createdb neutron_os_test  # if not exists
pytest tests/infra/test_state_benchmark.py -v -s -k "Pg"

# Side-by-side comparison
pytest tests/infra/test_state_benchmark.py -v -s -k "SideBySide"
```

---

## 9. Related Work

- **SQLite WAL mode** — single-file database with concurrent readers and serialized writers. Could be an intermediate option between flat files and PostgreSQL, but NeutronOS already requires PostgreSQL for the data platform, making it redundant.
- **Redis** — in-memory key-value store with persistence. Fast but adds another dependency; PostgreSQL JSONB provides similar functionality without a separate service.
- **etcd** — distributed key-value store. Overkill for single-facility deployment; relevant if NeutronOS expands to multi-facility coordination.

---

## References

1. NeutronOS Agent State Management PRD — `docs/requirements/prd-agent-state-management.md`
2. NeutronOS Agent State Management Spec — `docs/tech-specs/spec-agent-state-management.md`
3. NeutronOS Data Architecture Spec — `docs/tech-specs/spec-data-architecture.md`
4. PostgreSQL Advisory Locks documentation — https://www.postgresql.org/docs/current/explicit-locking.html
5. `fcntl.flock` POSIX specification — IEEE Std 1003.1
