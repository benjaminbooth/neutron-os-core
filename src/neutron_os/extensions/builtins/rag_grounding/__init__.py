# Copyright (c) 2026 The University of Texas at Austin
# SPDX-License-Identifier: Apache-2.0

"""NeutronOS RAG grounding hardening.

Wires axiom's domain-agnostic ``axiom.rag.grounding.GroundingHooks`` into
NeutronOS RAG ask paths with NETL-tuned thresholds, low-confidence audit
events, and a startup corpus health check.

Public surface
--------------
- ``DEFAULT_NETL_THRESHOLD`` — tuned ``GroundingThreshold`` instance.
- ``LOW_CONFIDENCE_AUDIT_FLOOR`` — top-score floor below which audit
  events are emitted (independent of the gate threshold).
- ``make_grounding_hooks(...)`` — factory returning a configured
  ``GroundingHooks`` ready to drop into an ``AskPipeline``.
- ``emit_low_confidence_audit(...)`` — write a JSONL audit row when
  retrieval looks low-confidence. Fail-closed; never raises.
- ``corpus_health_check(...)`` — startup-time corpus inventory log.

Connect presets
---------------
This extension also ships two ``[[connect.preset]]`` blocks in its
``axiom-extension.toml`` distinguishing :41883 (bare Qwen, EC-safe)
from :8766 (NeutronOS RAG gateway, NOT EC-safe). They are picked up by
the ``axi connect`` framework once landed; tests pin the manifest shape
in the meantime.
"""

from neutron_os.extensions.builtins.rag_grounding.grounding import (
    DEFAULT_NETL_THRESHOLD,
    LOW_CONFIDENCE_AUDIT_FLOOR,
    emit_low_confidence_audit,
    make_grounding_hooks,
)
from neutron_os.extensions.builtins.rag_grounding.health import (
    corpus_health_check,
)

__all__ = [
    "DEFAULT_NETL_THRESHOLD",
    "LOW_CONFIDENCE_AUDIT_FLOOR",
    "corpus_health_check",
    "emit_low_confidence_audit",
    "make_grounding_hooks",
]
