# Gaussian Process Surrogate - WASM Build
#
# Builds a simple GP surrogate model to WASM using WASI SDK
#
# Prerequisites:
#   - WASI SDK installed (https://github.com/WebAssembly/wasi-sdk)
#   - Set WASI_SDK_PATH environment variable

WASI_SDK_PATH ?= /opt/wasi-sdk

CC = $(WASI_SDK_PATH)/bin/clang
CFLAGS = -O3 -Wall -Wextra
LDFLAGS = -Wl,--export-all -Wl,--no-entry

TARGET = gp_surrogate.wasm
SOURCES = gp_surrogate.c
HEADERS = gp_surrogate.h

.PHONY: all clean test

all: $(TARGET)

$(TARGET): $(SOURCES) $(HEADERS)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SOURCES)
	@echo "Built $@ ($(shell wc -c < $@ | tr -d ' ') bytes)"

# Build native version for comparison benchmarks
gp_surrogate_native: $(SOURCES) $(HEADERS)
	clang $(CFLAGS) -o $@ $(SOURCES) -lm
	@echo "Built native binary for comparison"

clean:
	rm -f $(TARGET) gp_surrogate_native

test: $(TARGET)
	@echo "Testing WASM module..."
	wasmtime --invoke validate $(TARGET)

# Show module exports
inspect: $(TARGET)
	wasm-tools print --skeleton $(TARGET)

# Optimize the WASM binary
optimize: $(TARGET)
	wasm-opt -O3 $(TARGET) -o $(TARGET).opt
	mv $(TARGET).opt $(TARGET)
	@echo "Optimized $@ ($(shell wc -c < $@ | tr -d ' ') bytes)"
