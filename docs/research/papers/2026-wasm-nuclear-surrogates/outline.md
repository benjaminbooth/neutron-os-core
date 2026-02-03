# Paper Outline: Detailed Section Notes

## 1. Introduction (1.5 pages)

### Hook
The nuclear industry faces a paradox: the same AI/ML techniques revolutionizing other sectors remain largely excluded from safety-critical nuclear applications—not due to technical limitations, but regulatory uncertainty about auditability.

### Problem Statement
- Surrogate models enable real-time digital twin inference
- But: "How do you audit a neural network?"
- Existing approaches: freeze model weights, document training, hope for the best
- Missing: runtime execution guarantees

### Our Contribution
WebAssembly provides:
1. **Sandboxed execution** - Model cannot escape its container
2. **Deterministic replay** - Same inputs → same outputs, always
3. **Capability-based security** - Explicit permission grants
4. **Multi-language support** - Use the right tool for the job

### Paper Organization
Brief roadmap of remaining sections.

---

## 2. Background (3 pages)

### 2.1 Surrogate Models in Nuclear Engineering

**What they replace:**
- MCNP: Monte Carlo N-Particle transport (hours per run)
- RELAP/TRACE: System thermal-hydraulics (minutes per run)
- SCALE: Criticality and depletion (minutes to hours)

**What they enable:**
- Real-time inference (<10ms)
- Uncertainty quantification at scale
- Optimization loops previously infeasible

**Types we care about:**
| Type | Strengths | Limitations |
|------|-----------|-------------|
| Gaussian Process | UQ native, small data | O(n³) scaling |
| PINN | Physics constraints | Training complexity |
| ROM (POD/DMD) | Linear speedup | Linearity assumption |
| Neural Network | Flexible | "Black box" |

**Dakota integration:**
- Existing workflow: Dakota orchestrates UQ, calls surrogates
- Challenge: surrogates are just Python/C++ code, no isolation

### 2.2 WebAssembly Primer

**What is WASM?**
- Binary instruction format
- Originally for browsers, now server-side
- Compilation target from C, C++, Rust, etc.

**Key properties for our use case:**
1. **Memory safety** - Linear memory, bounds-checked
2. **Deterministic** - No undefined behavior (with caveats)
3. **Portable** - Same binary runs on any platform
4. **Fast** - Near-native performance (typically 0.8-1.2x)

**WASI (WebAssembly System Interface):**
- Capability-based access to host resources
- No ambient authority (can't just open files)
- Must be explicitly granted: `--dir=/data:readonly`

**Component Model & WIT:**
- Higher-level abstraction over core WASM
- Interface definitions independent of language
- Composable components

### 2.3 Regulatory Context

**10 CFR 50.59 - The key regulation:**
- Changes to facility require screening
- If change affects safety analysis, NRC approval needed
- ML models: how do you screen a weight update?

**What regulators want:**
1. Reproducibility - Can we get the same answer again?
2. Traceability - Where did this prediction come from?
3. Bounds - What are the limits of validity?
4. Failure modes - How does it fail safely?

**Current state:**
- No standardized approach to ML in nuclear safety
- Case-by-case acceptance
- Burden on licensee to justify

---

## 3. Architecture (4 pages)

### 3.1 Runtime Design

```
┌─────────────────────────────────────────────┐
│           Neutron OS Host (Rust)            │
│  ┌─────────────────────────────────────┐    │
│  │         Wasmtime Runtime            │    │
│  │  ┌─────────────────────────────┐    │    │
│  │  │    Surrogate Module         │    │    │
│  │  │    (WASM binary)            │    │    │
│  │  │                             │    │    │
│  │  │  predict(input) → output    │    │    │
│  │  │  validate() → status        │    │    │
│  │  │  metadata() → info          │    │    │
│  │  └─────────────────────────────┘    │    │
│  │         ↑ capabilities granted       │    │
│  └─────────────────────────────────────┘    │
│                    ↑                         │
│            store/linker config              │
└─────────────────────────────────────────────┘
```

**Determinism considerations:**
- Floating-point: WASM specifies IEEE 754
- But: NaN bit patterns, rounding modes
- Our approach: `--wasm-features=-relaxed-simd`
- Verification: hash outputs across platforms

**Memory model:**
- Linear memory (contiguous byte array)
- Configurable limits (e.g., 256 MB max)
- No shared memory (determinism)

### 3.2 WIT Interface Definition

```wit
package neutron:surrogate@0.1.0;

interface model {
    record input {
        features: list<float64>,
        timestamp: option<u64>,
    }
    
    record output {
        prediction: list<float64>,
        uncertainty: option<list<float64>>,
        computation-time-us: u64,
    }
    
    record metadata {
        model-id: string,
        version: string,
        training-hash: string,
        valid-ranges: list<tuple<float64, float64>>,
    }
    
    predict: func(input: input) -> result<output, string>;
    validate: func() -> result<bool, string>;
    get-metadata: func() -> metadata;
}

world surrogate {
    export model;
}
```

### 3.3 Security Model

**Capability grants (explicit):**
- `wasi:filesystem` - Read training data, write logs
- `wasi:clocks` - Measure computation time
- `wasi:random` - PRNG for stochastic models

**Capability denials (default):**
- Network access
- Process spawning
- Environment variables
- Unrestricted filesystem

**Resource limits:**
- Memory: configurable max
- Fuel (instructions): timeout equivalent
- Stack depth: prevent recursion bombs

---

## 4. Implementation (3 pages)

### 4.1 Spike Implementation

**Host (Rust):**
```rust
// Key components to discuss:
// - Wasmtime Engine configuration
// - Store and Linker setup
// - Component instantiation
// - Call interface
```

**Surrogate (C → WASM):**
```c
// Key components:
// - wit-bindgen generated bindings
// - GP prediction logic
// - Memory management
```

**Orchestration (Python):**
```python
# Key components:
# - Subprocess management
# - Result parsing
# - Integration with existing Dakota workflow
```

### 4.2 Model Examples

**Gaussian Process Surrogate:**
- Trained on MCNP k-effective calculations
- Input: enrichment, moderator ratio, geometry params
- Output: k-eff ± uncertainty
- Training: 500 MCNP runs, Latin hypercube sampling

**PINN Thermal-Hydraulic:**
- Trained on RELAP5 transient data
- Input: power, flow rate, inlet temperature
- Output: temperature distribution
- Physics loss: energy conservation

### 4.3 Neutron OS Integration

- How surrogates are registered
- Model versioning and provenance
- Audit log integration
- Real-time dashboard updates

---

## 5. Evaluation (3 pages)

### 5.1 Latency Benchmarks

**Test setup:**
- Hardware: [TBD based on spike]
- Models: GP (small), PINN (medium)
- Iterations: 10,000 per configuration

**Metrics:**
- Cold start latency (module load + first call)
- Warm inference latency (subsequent calls)
- Batch throughput (predictions/second)

**Expected results:**
| Configuration | Cold Start | Warm Latency | Throughput |
|---------------|------------|--------------|------------|
| Native C | baseline | baseline | baseline |
| WASM (Wasmtime) | ~5ms | ~1.1x native | ~0.9x native |
| Python (sklearn) | ~50ms | ~10x native | ~0.1x native |

### 5.2 Determinism Verification

**Methodology:**
1. Run same model with same inputs on:
   - macOS (ARM64)
   - Linux (x86_64)
   - [Windows if available]
2. Compare output byte-for-byte
3. Hash entire output vector

**Expected result:** Bit-exact match across platforms

**Edge cases to test:**
- Denormalized floats
- NaN propagation
- Large accumulated sums

### 5.3 Security Assessment

**Sandbox escape attempts:**
- File system traversal
- Memory corruption
- Stack overflow
- Resource exhaustion

**Result:** Document any findings, mitigations

---

## 6. Discussion (2 pages)

### 6.1 Path to Regulatory Acceptance

**What this enables:**
- Deterministic audit replay
- Bounded execution environment
- Explicit capability grants
- Version-controlled model binaries

**What's still needed:**
- Regulatory guidance on ML in safety applications
- Standardized testing protocols
- Industry consensus on acceptable approaches

### 6.2 Multi-Language Ecosystem

**Currently supported:**
- C/C++ (clang → wasm32-wasi)
- Rust (native target)

**Coming soon:**
- Mojo (WASM target announced)
- Python (via componentize-py, with caveats)

### 6.3 Limitations

**GPU acceleration:**
- WASM has no GPU access
- Workaround: pre-compute on GPU, inference in WASM
- Future: WebGPU standardization

**Large models:**
- Transformer-scale models don't fit
- But: nuclear surrogates are typically small
- Typical size: <100MB

---

## 7. Related Work (1 page)

- Existing ML in nuclear: [citations]
- WASM in scientific computing: [citations]
- Sandboxed ML execution: [citations]
- Deterministic computing: [citations]

---

## 8. Conclusion (0.5 page)

**Summary:**
- WASM provides auditable execution for nuclear surrogates
- Demonstrated <10ms latency with deterministic results
- Capability-based security addresses regulatory concerns

**Future work:**
- GPU-accelerated WASM
- Standardized nuclear surrogate registry
- Fleet-wide model deployment

---

## Appendix Ideas

- A: Complete WIT specification
- B: Benchmark raw data
- C: Security test cases
