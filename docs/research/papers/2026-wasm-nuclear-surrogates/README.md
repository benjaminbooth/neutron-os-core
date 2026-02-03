# WASM-Based Surrogate Model Runtime for Nuclear Digital Twins

**Working Title:** "Auditable AI: A WebAssembly Runtime for Deterministic Surrogate Model Execution in Nuclear Digital Twins"

**Target Venue:** Nuclear Engineering and Design, Annals of Nuclear Energy, or Nuclear Technology

**Status:** Drafting

---

## Abstract (Draft)

Digital twin platforms for nuclear facilities require real-time inference from surrogate models while maintaining the auditability and reproducibility demanded by regulatory frameworks. This paper presents a WebAssembly (WASM) runtime architecture that sandboxes surrogate model execution, enables multi-language model development, and provides deterministic replay for regulatory audit. We demonstrate the approach using Gaussian process surrogates trained on MCNP transport calculations and PINN-based thermal-hydraulic approximators. Benchmarks show <10ms inference latency with bit-exact reproducibility across platforms. The capability-based security model allows surrogates to access only explicitly granted resources, addressing concerns about ML model behavior in safety-critical contexts. We discuss implications for NRC regulatory acceptance and propose a standardized interface (WIT) for nuclear surrogate models.

---

## Paper Structure

### 1. Introduction
- Digital twin adoption in nuclear industry
- The "black box" problem with ML in regulated environments
- Contribution: WASM as auditable execution substrate

### 2. Background
- 2.1 Surrogate Models in Nuclear Engineering
  - Gaussian Process, PINN, ROM approaches
  - Dakota UQ integration patterns
- 2.2 WebAssembly and the Component Model
  - WASM security properties
  - WASI capability-based I/O
  - WIT interface definitions
- 2.3 Regulatory Context
  - 10 CFR 50.59 screening requirements
  - Audit trail expectations
  - Reproducibility requirements

### 3. Architecture
- 3.1 Runtime Design
  - Wasmtime host implementation (Rust)
  - Memory isolation model
  - Deterministic floating-point handling
- 3.2 Surrogate Model Interface (WIT)
  - `predict()` contract
  - `validate()` self-checks
  - Metadata and provenance
- 3.3 Security Model
  - Capability grants (filesystem, network, time)
  - Resource limits (memory, CPU)
  - No ambient authority

### 4. Implementation
- 4.1 Spike Implementation Details
  - Rust host code
  - C surrogate compilation to WASM
  - Python orchestration layer
- 4.2 Surrogate Model Examples
  - GP-based MCNP surrogate
  - PINN thermal-hydraulic approximator
- 4.3 Integration with Neutron OS

### 5. Evaluation
- 5.1 Latency Benchmarks
  - Native vs WASM execution
  - Startup overhead analysis
  - Batch inference performance
- 5.2 Determinism Verification
  - Cross-platform reproducibility tests
  - Bit-exact result comparison
- 5.3 Security Assessment
  - Sandbox escape analysis
  - Resource exhaustion testing

### 6. Discussion
- 6.1 Regulatory Implications
  - Path to NRC acceptance
  - Comparison to existing approaches
- 6.2 Multi-Language Support
  - C/C++, Rust, (future) Mojo
  - Language-specific considerations
- 6.3 Limitations
  - GPU acceleration constraints
  - Large model size challenges

### 7. Related Work
- ML in nuclear safety applications
- WASM in scientific computing
- Sandboxed execution environments

### 8. Conclusion
- Summary of contributions
- Future work: GPU WASM, model versioning, fleet deployment

---

## Key Figures

| Figure | Description | Status |
|--------|-------------|--------|
| Fig 1 | Architecture overview diagram | TODO |
| Fig 2 | WIT interface definition | TODO |
| Fig 3 | Latency benchmark results | Pending spike |
| Fig 4 | Determinism test methodology | TODO |
| Fig 5 | Security capability model | TODO |
| Fig 6 | Integration with Neutron OS data flow | TODO |

---

## Data Requirements

1. **Benchmark data:** Latency measurements from spike implementation
2. **Surrogate models:** At least 2 different model types (GP, PINN)
3. **Cross-platform tests:** macOS, Linux, (ideally Windows)
4. **Comparison baseline:** Native execution benchmarks

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| Spike implementation complete | 2026-02-15 |
| Benchmark data collected | 2026-02-28 |
| First draft complete | 2026-03-31 |
| Internal review | 2026-04-15 |
| Submission | 2026-05-01 |

---

## Authors

- Benjamin Booth (UT Austin)
- [Additional collaborators TBD]

---

## References (Partial)

1. Haario et al. "DRAM: Efficient adaptive MCMC" (2006)
2. Raissi et al. "Physics-informed neural networks" (2019)
3. Bytecode Alliance. "WebAssembly Component Model" (2024)
4. U.S. NRC. "10 CFR 50.59 - Changes, tests and experiments" 
5. Idaho National Laboratory. "Digital Twin for Advanced Reactors" (2023)
