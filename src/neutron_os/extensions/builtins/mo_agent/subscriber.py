"""EventBus subscriber registration and handlers for M-O.

Follows the Doctor subscriber pattern (extensions/builtins/doctor_agent/subscriber.py):
- register(bus) wires all handlers
- Circuit breakers: max 3 LLM diagnosis calls per hour, 5-minute cooldown
  per signal fingerprint
"""

from __future__ import annotations

import time
from typing import Any

# --- Circuit breaker constants ---

MAX_DIAGNOSES_PER_HOUR = 3
COOLDOWN_SECONDS = 300  # 5 min between attempts on same signal

# Module-level state
_bus = None
_recent_signals: dict[str, float] = {}  # fingerprint -> timestamp
_hourly_calls: list[float] = []


def register(bus: Any) -> None:
    """Register all M-O handlers on the bus."""
    global _bus
    _bus = bus
    bus.subscribe("mo.pressure_critical", handle_pressure)
    bus.subscribe("mo.leak_detected", handle_leak)
    bus.subscribe("mo.sweep_failed", handle_sweep_failure)


def handle_pressure(topic: str, data: dict[str, Any]) -> None:
    """Handle critical pressure events — trigger LLM diagnosis."""
    fingerprint = f"pressure_{data.get('level', 'unknown')}"
    if not _should_process(fingerprint):
        return

    agent = _get_agent()
    if agent is None:
        return

    signal = {"type": "pressure_critical", **data}
    verdict = agent.diagnose(signal)

    if _bus and verdict.level == "escalated":
        _bus.publish("mo.escalation", verdict.to_dict(), source="mo.subscriber")


def handle_leak(topic: str, data: dict[str, Any]) -> None:
    """Handle leak detection events — trigger LLM diagnosis."""
    owner = data.get("owner", "unknown")
    fingerprint = f"leak_{owner}"
    if not _should_process(fingerprint):
        return

    agent = _get_agent()
    if agent is None:
        return

    signal = {"type": "leak_detected", **data}
    verdict = agent.diagnose(signal)

    if _bus:
        _bus.publish("mo.advisory", {
            "source": "leak_handler",
            **verdict.to_dict(),
        }, source="mo.subscriber")


def handle_sweep_failure(topic: str, data: dict[str, Any]) -> None:
    """Handle sweep failure events — diagnose why cleanup failed."""
    fingerprint = f"sweep_{data.get('error', 'unknown')}"
    if not _should_process(fingerprint):
        return

    agent = _get_agent()
    if agent is None:
        return

    signal = {"type": "sweep_failed", **data}
    agent.diagnose(signal)


# --- Circuit breakers ---

def _should_process(fingerprint: str) -> bool:
    """Check cooldown and rate limit. Returns True if we should proceed."""
    now = time.time()

    # Cooldown per fingerprint
    last_time = _recent_signals.get(fingerprint, 0)
    if now - last_time < COOLDOWN_SECONDS:
        return False

    # Hourly rate limit
    _hourly_calls[:] = [t for t in _hourly_calls if now - t < 3600]
    if len(_hourly_calls) >= MAX_DIAGNOSES_PER_HOUR:
        return False

    # Record this attempt
    _recent_signals[fingerprint] = now
    _hourly_calls.append(now)
    return True


def _get_agent():
    """Lazy-load the MoAgent with gateway. Returns None if unavailable."""
    try:
        from neutron_os.platform.gateway import Gateway
        gateway = Gateway()
        if not gateway.available:
            return None

        from .agent import MoAgent
        from . import manager

        agent = MoAgent(gateway=gateway, bus=_bus)
        mgr = manager()

        # Try to set up monitor
        try:
            from .vitals import VitalsMonitor
            from .network import NetworkLedger
            monitor = VitalsMonitor(mgr, NetworkLedger.shared(), _bus)
            agent.set_manager(mgr, monitor)
        except Exception:
            agent.set_manager(mgr)

        return agent
    except Exception:
        return None
