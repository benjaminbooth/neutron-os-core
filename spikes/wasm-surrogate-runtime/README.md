# WASM Surrogate Runtime Spike

**Purpose:** Validate WebAssembly as an execution environment for nuclear surrogate models.

**Status:** 🚧 In Development

---

## Goals

1. ✅ Define WIT interface for surrogate models
2. ⬜ Implement Rust host using Wasmtime
3. ⬜ Compile C surrogate to WASM
4. ⬜ Benchmark latency vs native execution
5. ⬜ Verify deterministic cross-platform results
6. ⬜ Document findings for ADR-008

---

## Quick Start

### Prerequisites

```bash
# Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup target add wasm32-wasip1

# WASM tools
cargo install wasmtime-cli
cargo install wit-bindgen-cli

# C compiler with WASM target (via WASI SDK)
# Download from: https://github.com/WebAssembly/wasi-sdk/releases
export WASI_SDK_PATH=/opt/wasi-sdk
```

### Build & Run

```bash
# Build the Rust host
cd host
cargo build --release

# Build the C surrogate
cd ../surrogates/gp-surrogate
make

# Run benchmark
cd ../..
./target/release/neut-wasm-host --benchmark surrogates/gp-surrogate/gp_surrogate.wasm
```

---

## Directory Structure

```
wasm-surrogate-runtime/
├── README.md                 # This file
├── Cargo.toml                # Workspace manifest
├── wit/
│   └── surrogate.wit         # Interface definition
├── host/
│   ├── Cargo.toml
│   └── src/
│       └── main.rs           # Wasmtime host implementation
├── surrogates/
│   └── gp-surrogate/
│       ├── Makefile
│       ├── gp_surrogate.c    # Gaussian process implementation
│       └── gp_surrogate.h
├── benchmarks/
│   ├── run_benchmarks.py     # Benchmark orchestration
│   └── results/              # Benchmark output
└── tests/
    └── determinism/          # Cross-platform reproducibility tests
```

---

## WIT Interface

```wit
package neutron:surrogate@0.1.0;

interface model {
    // Predict output from input features
    predict: func(features: list<float64>) -> result<list<float64>, string>;
    
    // Validate model is ready
    validate: func() -> result<bool, string>;
    
    // Get model metadata
    get-metadata: func() -> metadata;
    
    record metadata {
        model-id: string,
        version: string,
        training-hash: string,
    }
}

world surrogate {
    export model;
}
```

---

## Key Design Decisions

### Determinism

- Disable relaxed SIMD: `--wasm-features=-relaxed-simd`
- Use canonical NaN representation
- No threading (single-threaded execution)
- Seed PRNG explicitly if needed

### Security

- No ambient filesystem access
- Explicit capability grants only
- Memory limits enforced
- Instruction fuel limits (timeout)

### Performance

- Pre-compile WASM to native (AOT)
- Keep modules hot in memory
- Batch predictions when possible

---

## Benchmark Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Cold start | <50ms | Module load + first call |
| Warm latency | <10ms | Single prediction |
| Throughput | >1000/s | Batch predictions |
| Overhead vs native | <20% | Acceptable for auditability benefit |

---

## References

- [Wasmtime Documentation](https://docs.wasmtime.dev/)
- [WASI SDK](https://github.com/WebAssembly/wasi-sdk)
- [WIT Specification](https://component-model.bytecodealliance.org/design/wit.html)
- [Deterministic WASM](https://github.com/aspect-build/rules_wasm#determinism)
