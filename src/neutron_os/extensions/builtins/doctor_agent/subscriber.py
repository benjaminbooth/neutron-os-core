"""EventBus handlers for the Doctor Agent pipeline.

Handlers:
- doctor_handler:  cli.arg_error → diagnose + patch
- review_handler:  doctor.patch_ready → independent review
- commit_handler:  review.approved → git commit
- retry_handler:   review.rejected → doctor retries (once)
- aar_handler:     terminal events → After Action Report

Circuit breakers:
- Fingerprint cooldown (5 min)
- Global rate limit (3 patches/hour)
- Lockfile (prevent concurrent runs)
- Recursion detection (skip if traceback contains doctor/)
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neutron_os import REPO_ROOT as _REPO_ROOT

_RUNTIME_DIR = _REPO_ROOT / "runtime"
_DOCTOR_DIR = _RUNTIME_DIR / "doctor"
_LOG_PATH = _RUNTIME_DIR / "logs" / "cli_events.jsonl"
_LOCKFILE = _DOCTOR_DIR / ".lock"
_REPORTS_DIR = _DOCTOR_DIR / "reports"

# --- Circuit breaker constants ---

MAX_PATCHES_PER_HOUR = 3
COOLDOWN_SECONDS = 300  # 5 min between attempts on same fingerprint
LOCK_STALE_SECONDS = 600  # 10 min

# Module-level bus reference, set by register()
_bus = None


def register(bus: Any) -> None:
    """Register all doctor handlers on the bus."""
    global _bus
    _bus = bus
    bus.subscribe("cli.*", doctor_handler)
    bus.subscribe("doctor.patch_ready", review_handler)
    bus.subscribe("review.approved", commit_handler)
    bus.subscribe("review.rejected", retry_handler)
    # AAR on terminal events
    bus.subscribe("doctor.patch_complete", aar_handler)
    bus.subscribe("doctor.patch_failed", aar_handler)
    bus.subscribe("doctor.rate_limited", aar_handler)
    bus.subscribe("doctor.llm_unavailable", aar_handler)


# --- Circuit breakers ---

def _recently_processed(fingerprint: str, cooldown: int = COOLDOWN_SECONDS) -> bool:
    """Check if this fingerprint was processed by the doctor recently."""
    if not _LOG_PATH.exists():
        return False
    cutoff = time.time() - cooldown
    try:
        for line in _LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                topic = event.get("topic", "")
                if not topic.startswith("doctor."):
                    continue
                data = event.get("data", {})
                if data.get("fingerprint") != fingerprint:
                    continue
                ts = event.get("timestamp", "")
                if ts:
                    evt_time = datetime.fromisoformat(ts).timestamp()
                    if evt_time > cutoff:
                        return True
            except (json.JSONDecodeError, ValueError):
                continue
    except OSError:
        pass
    return False


def _hourly_patch_count() -> int:
    """Count doctor.patch_* events in the last hour."""
    if not _LOG_PATH.exists():
        return 0
    cutoff = time.time() - 3600
    count = 0
    try:
        for line in _LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                topic = event.get("topic", "")
                if not topic.startswith("doctor.patch_"):
                    continue
                ts = event.get("timestamp", "")
                if ts:
                    evt_time = datetime.fromisoformat(ts).timestamp()
                    if evt_time > cutoff:
                        count += 1
            except (json.JSONDecodeError, ValueError):
                continue
    except OSError:
        pass
    return count


def _acquire_lock() -> bool:
    """Try to acquire the doctor lockfile. Returns True if acquired."""
    _DOCTOR_DIR.mkdir(parents=True, exist_ok=True)
    if _LOCKFILE.exists():
        try:
            age = time.time() - _LOCKFILE.stat().st_mtime
            if age < LOCK_STALE_SECONDS:
                return False  # Active lock
            # Stale lock — remove it
            _LOCKFILE.unlink(missing_ok=True)
        except OSError:
            return False

    try:
        _LOCKFILE.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError:
        return False


def _release_lock() -> None:
    """Release the doctor lockfile."""
    _LOCKFILE.unlink(missing_ok=True)


def _rollback_from_backup(files_changed: list[str]) -> None:
    """Roll back edited files from backups."""
    from neutron_os.extensions.builtins.doctor_agent.tools import rollback_file
    for f in files_changed:
        rollback_file(f)


# --- Handlers ---

def doctor_handler(topic: str, data: dict[str, Any]) -> None:
    """Subscribes to 'cli.*' — diagnoses and patches unrecovered errors."""
    # Only handle arg errors
    if topic != "cli.arg_error":
        return

    # Skip recovered errors — recovery strategy already fixed it
    if data.get("recovered"):
        return

    fingerprint = data.get("fingerprint", "")
    if not fingerprint:
        return

    # Recursion guard: skip if the error came from doctor code
    tb = data.get("traceback", "")
    if "src/neutron_os/extensions/builtins/doctor_agent/" in tb:
        return

    # Cooldown: skip if recently processed
    if _recently_processed(fingerprint):
        return

    # Rate limit
    if _hourly_patch_count() >= MAX_PATCHES_PER_HOUR:
        if _bus:
            _bus.publish("doctor.rate_limited", {
                "fingerprint": fingerprint,
                "reason": f"Rate limit: {MAX_PATCHES_PER_HOUR} patches/hour exceeded",
                **data,
            }, source="doctor_agent")
        return

    # Lockfile
    if not _acquire_lock():
        return

    try:
        from neutron_os.platform.gateway import Gateway
        gateway = Gateway()
        if not gateway.available:
            if _bus:
                _bus.publish("doctor.llm_unavailable", {
                    "fingerprint": fingerprint,
                    **data,
                }, source="doctor_agent")
            return

        from neutron_os.extensions.builtins.doctor_agent.agent import DoctorAgent
        agent = DoctorAgent(gateway=gateway, bus=_bus)
        result = agent.diagnose_and_patch(data)

        if result.tests_passed and result.files_changed:
            # Package the fix for independent review
            if _bus:
                _bus.publish("doctor.patch_ready", {
                    **result.to_dict(),
                    "error_signal": data,
                    "attempt": 1,
                }, source="doctor_agent")
        elif result.status == "llm_unavailable":
            if _bus:
                _bus.publish("doctor.llm_unavailable", {
                    "fingerprint": fingerprint,
                    **result.to_dict(),
                }, source="doctor_agent")
        else:
            if _bus:
                _bus.publish("doctor.patch_failed", {
                    **result.to_dict(),
                    "error_signal": data,
                }, source="doctor_agent")
    finally:
        _release_lock()


def review_handler(topic: str, data: dict[str, Any]) -> None:
    """Subscribes to 'doctor.patch_ready' — independent review."""
    try:
        from neutron_os.platform.gateway import Gateway
        gateway = Gateway()
    except Exception:
        # No gateway — auto-approve (tests already passed)
        if _bus:
            _bus.publish("review.approved", data, source="reviewer")
        return

    if not gateway.available:
        # No LLM for review — auto-approve (tests already passed)
        if _bus:
            _bus.publish("review.approved", data, source="reviewer")
        return

    from neutron_os.extensions.builtins.doctor_agent.reviewer import Reviewer
    reviewer = Reviewer(gateway=gateway)
    verdict = reviewer.evaluate(data)

    if verdict.approved:
        if _bus:
            _bus.publish("review.approved", {
                **data,
                "review": verdict.to_dict(),
            }, source="reviewer")
    else:
        if _bus:
            _bus.publish("review.rejected", {
                **data,
                "review": verdict.to_dict(),
            }, source="reviewer")


def commit_handler(topic: str, data: dict[str, Any]) -> None:
    """Subscribes to 'review.approved' — commits the fix (if not already committed)."""
    # The DoctorAgent already attempted git commit in diagnose_and_patch.
    # If it succeeded, we just emit completion. If not, try again.
    commit_sha = data.get("commit_sha", "")
    if commit_sha:
        # Already committed during diagnosis
        if _bus:
            _bus.publish("doctor.patch_complete", data, source="doctor_agent")
        return

    # Try to commit now
    from neutron_os.extensions.builtins.doctor_agent.tools import execute as exec_tool
    files = data.get("files_changed", [])
    fingerprint = data.get("fingerprint", "")
    if not files or not fingerprint:
        if _bus:
            _bus.publish("doctor.patch_complete", data, source="doctor_agent")
        return

    error_signal = data.get("error_signal", {})
    result = exec_tool("git_commit_fix", {
        "fingerprint": fingerprint,
        "files": files,
        "message": (
            f"doctor: fix {error_signal.get('error_type', 'error')} "
            f"in {error_signal.get('command', 'unknown')} [{fingerprint}]"
        ),
    })

    if _bus:
        _bus.publish("doctor.patch_complete", {
            **data,
            **result,
        }, source="doctor_agent")


def retry_handler(topic: str, data: dict[str, Any]) -> None:
    """Subscribes to 'review.rejected' — doctor gets one more attempt."""
    attempt = data.get("attempt", 1)
    if attempt >= 2:
        # Already retried — give up
        if _bus:
            _bus.publish("doctor.patch_failed", data, source="doctor_agent")
        return

    # Roll back the previous edit
    _rollback_from_backup(data.get("files_changed", []))

    try:
        from neutron_os.platform.gateway import Gateway
        gateway = Gateway()
    except Exception:
        if _bus:
            _bus.publish("doctor.patch_failed", data, source="doctor_agent")
        return

    if not gateway.available:
        if _bus:
            _bus.publish("doctor.patch_failed", data, source="doctor_agent")
        return

    # Doctor retries with reviewer feedback
    from neutron_os.extensions.builtins.doctor_agent.agent import DoctorAgent
    feedback = data.get("review", {}).get("feedback", "")
    agent = DoctorAgent(gateway=gateway, bus=_bus)
    error_signal = data.get("error_signal", {})
    result = agent.retry_with_feedback(error_signal, feedback)

    if result.tests_passed and result.files_changed:
        if _bus:
            _bus.publish("doctor.patch_ready", {
                **result.to_dict(),
                "error_signal": error_signal,
                "attempt": 2,
            }, source="doctor_agent")
    else:
        if _bus:
            _bus.publish("doctor.patch_failed", {
                **result.to_dict(),
                "error_signal": error_signal,
            }, source="doctor_agent")


# --- After Action Report ---

def aar_handler(topic: str, data: dict[str, Any]) -> None:
    """Produces After Action Report for terminal doctor events."""
    outcome = _outcome_from_topic(topic)
    report = _build_aar(topic, data, outcome)
    fingerprint = data.get("fingerprint", "unknown")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    # Write markdown file
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _REPORTS_DIR / f"{fingerprint}_{ts}.md"
    try:
        report_path.write_text(report, encoding="utf-8")
    except OSError:
        pass

    summary = _one_line_summary(topic, data, outcome)

    # Emit to bus (logged to JSONL)
    if _bus:
        _bus.publish("doctor.aar", {
            "fingerprint": fingerprint,
            "outcome": outcome,
            "report_path": str(report_path),
            "summary": summary,
        }, source="doctor_agent")

    # Print summary if interactive
    if sys.stdout.isatty():
        print(f"\n  Doctor: {summary}", file=sys.stderr)
        print(f"  Report: {report_path}\n", file=sys.stderr)


def _outcome_from_topic(topic: str) -> str:
    mapping = {
        "doctor.patch_complete": "PATCHED",
        "doctor.patch_failed": "FAILED",
        "doctor.rate_limited": "RATE_LIMITED",
        "doctor.llm_unavailable": "LLM_UNAVAILABLE",
    }
    return mapping.get(topic, "UNKNOWN")


def _one_line_summary(topic: str, data: dict[str, Any], outcome: str) -> str:
    fingerprint = data.get("fingerprint", "?")
    files = data.get("files_changed", [])
    tests = "tests passed" if data.get("tests_passed") else "tests failed"

    if outcome == "PATCHED":
        return f"[{fingerprint}] PATCHED {len(files)} file(s), {tests}"
    elif outcome == "FAILED":
        diagnosis = data.get("diagnosis", "")[:80]
        return f"[{fingerprint}] FAILED — {diagnosis or 'no diagnosis'}"
    elif outcome == "RATE_LIMITED":
        return f"[{fingerprint}] SKIPPED (rate limit)"
    elif outcome == "LLM_UNAVAILABLE":
        return f"[{fingerprint}] SKIPPED (LLM unavailable)"
    return f"[{fingerprint}] {outcome}"


def _build_aar(topic: str, data: dict[str, Any], outcome: str) -> str:
    """Build a markdown After Action Report."""
    fingerprint = data.get("fingerprint", "unknown")
    ts = datetime.now(timezone.utc).isoformat()
    error_signal = data.get("error_signal", data)

    lines = [
        "# Doctor After Action Report",
        f"**Fingerprint:** `{fingerprint}`",
        f"**Timestamp:** {ts}",
        f"**Outcome:** {outcome}",
        "",
        "## Error Signal",
        f"- **Command:** `{' '.join(error_signal.get('argv', []))}`",
        f"- **Error:** {error_signal.get('error_type', '?')}: {error_signal.get('error_message', '?')}",
        f"- **Recovered by strategy:** {'Yes' if error_signal.get('recovered') else 'No'}",
    ]

    # Diagnosis
    diagnosis = data.get("diagnosis", "")
    if diagnosis:
        lines.extend(["", "## Diagnosis", "", diagnosis])

    # Changes
    files_changed = data.get("files_changed", [])
    patch_diff = data.get("patch_diff", "")
    if files_changed:
        lines.extend(["", "## Changes Made", ""])
        for f in files_changed:
            lines.append(f"- `{f}`")
        if patch_diff:
            lines.extend(["", "```diff", patch_diff, "```"])

    # Test results
    tests_passed = data.get("tests_passed")
    tests_output = data.get("tests_output", "")
    if tests_passed is not None:
        lines.extend([
            "", "## Test Results",
            f"- **Passed:** {'Yes' if tests_passed else 'No'}",
        ])
        if tests_output:
            output = tests_output[:2000]
            lines.extend(["", "```", output, "```"])

    # Review
    review = data.get("review", {})
    if review:
        lines.extend([
            "", "## Reviewer Verdict",
            f"- **Approved:** {'Yes' if review.get('approved') else 'No'}",
            f"- **Feedback:** {review.get('feedback', 'N/A')}",
        ])
        concerns = review.get("security_concerns", [])
        if concerns:
            lines.append(f"- **Security concerns:** {', '.join(concerns)}")
        issues = review.get("convention_issues", [])
        if issues:
            lines.append(f"- **Convention issues:** {', '.join(issues)}")

    # Git
    branch = data.get("branch_name", "") or data.get("branch", "")
    commit_sha = data.get("commit_sha", "")
    if branch or commit_sha:
        lines.extend([
            "", "## Git",
            f"- **Branch:** `{branch or 'N/A'}`",
            f"- **Commit:** `{commit_sha or 'N/A'}`",
        ])

    lines.extend(["", "---", "*Generated by Neut Doctor Agent*", ""])
    return "\n".join(lines)
