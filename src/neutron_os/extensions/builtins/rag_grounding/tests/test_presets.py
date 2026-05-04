# Copyright (c) 2026 The University of Texas at Austin
# SPDX-License-Identifier: Apache-2.0

"""Pin the two `[[connect.preset]]` blocks shipped in the manifest.

The presets distinguish two architecturally-different rascal services
that today both hide behind "rascal" in user-facing config:

  rascal-qwen-ec       — bare Qwen on :41883  (EC-safe, no RAG)
  rascal-neutronos-rag — gateway on :8766     (RAG-grounded, NOT EC-safe)

When the in-flight `axi connect` framework lands, these blocks are
discovered automatically. Until then, the tests load them directly so
we know the manifest stays well-formed.
"""

from __future__ import annotations

from pathlib import Path


def _manifest_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent / "axiom-extension.toml"
    )


def _load_presets() -> dict[str, dict]:
    try:
        import tomllib  # py3.11+
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]

    with _manifest_path().open("rb") as fh:
        data = tomllib.load(fh)

    blocks = data.get("connect", {}).get("preset", [])
    return {b["name"]: b for b in blocks}


class TestRascalQwenECPreset:
    def test_present(self):
        presets = _load_presets()
        assert "rascal-qwen-ec" in presets

    def test_endpoint_and_port(self):
        p = _load_presets()["rascal-qwen-ec"]
        providers = p["providers"]
        # One provider, kind=llm, on :41883.
        llm = [pr for pr in providers if pr["kind"] == "llm"]
        assert len(llm) == 1
        assert ":41883" in llm[0]["endpoint"]
        assert llm[0]["api_key_env"] == "QWEN_API_KEY"
        assert llm[0]["routing_tier"] == "any"
        # EC-safety is encoded in routing tags so trust gates can read it.
        assert "ec_safe" in llm[0]["routing_tags"]

    def test_description_distinguishes_from_rag_gateway(self):
        p = _load_presets()["rascal-qwen-ec"]
        desc = p["description"].lower()
        # Must mark itself as EC-safe and explicitly note "no RAG".
        assert "ec-safe" in desc
        assert "no rag" in desc


class TestRascalNeutronOSRagPreset:
    def test_present(self):
        presets = _load_presets()
        assert "rascal-neutronos-rag" in presets

    def test_endpoint_and_port(self):
        p = _load_presets()["rascal-neutronos-rag"]
        providers = p["providers"]
        llm = [pr for pr in providers if pr["kind"] == "llm"]
        rag = [pr for pr in providers if pr["kind"] == "rag"]
        assert len(llm) == 1
        assert len(rag) == 1
        assert ":8766" in llm[0]["endpoint"]
        assert ":8766" in rag[0]["endpoint"]
        # Currently unauthenticated — pinned so we notice when auth lands.
        assert llm[0]["api_key_env"] == ""

    def test_description_warns_not_ec_safe(self):
        p = _load_presets()["rascal-neutronos-rag"]
        desc = p["description"].lower()
        assert "not ec-safe" in desc or "not ec safe" in desc

    def test_routing_tags_flag_ec_state(self):
        p = _load_presets()["rascal-neutronos-rag"]
        llm = [pr for pr in p["providers"] if pr["kind"] == "llm"][0]
        # Trust-tier routing logic should be able to filter on this.
        assert "not_ec_safe" in llm["routing_tags"]
        assert "rag_grounded" in llm["routing_tags"]


class TestPresetDistinction:
    """The whole point of having two presets is that they are NOT
    interchangeable. Pin the architectural distinction."""

    def test_endpoints_are_different_services(self):
        presets = _load_presets()
        ec = [p for p in presets["rascal-qwen-ec"]["providers"] if p["kind"] == "llm"][0]
        rag = [p for p in presets["rascal-neutronos-rag"]["providers"] if p["kind"] == "llm"][0]
        # Different ports = different services.
        assert ec["endpoint"] != rag["endpoint"]

    def test_ec_safety_inverts_between_presets(self):
        presets = _load_presets()
        ec = [p for p in presets["rascal-qwen-ec"]["providers"] if p["kind"] == "llm"][0]
        rag = [p for p in presets["rascal-neutronos-rag"]["providers"] if p["kind"] == "llm"][0]
        assert "ec_safe" in ec["routing_tags"]
        assert "not_ec_safe" in rag["routing_tags"]
