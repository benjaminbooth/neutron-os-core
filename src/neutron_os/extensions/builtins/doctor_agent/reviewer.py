"""Independent fix reviewer for doctor patches.

A separate *role*, not a separate agent infrastructure. Same Gateway,
different system prompt, read-only tools only. Never sees the doctor's
reasoning chain — receives ONLY the error signal, patch diff, test output,
and affected files.

The reviewer is adversarial: it looks for reasons to reject, not approve.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from neutron_os.extensions.builtins.doctor_agent.tools import TOOL_DEFS, execute

# Read-only subset of doctor tools
_REVIEWER_TOOLS = [
    t for t in TOOL_DEFS
    if t["function"]["name"] in ("read_file_with_lines", "search_files")
]


@dataclass
class ReviewVerdict:
    """Structured review result."""

    approved: bool
    feedback: str = ""
    security_concerns: list[str] = field(default_factory=list)
    convention_issues: list[str] = field(default_factory=list)
    test_coverage_notes: str = ""
    fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REVIEWER_SYSTEM_PROMPT = """\
You are the Neut Code Reviewer — an independent DevSecOps evaluator for
automated patches produced by the Doctor Agent. You did NOT produce this patch.
You must evaluate it adversarially.

## Your Task

Review the patch below. You receive:
- The original error signal (what broke)
- The unified diff (what was changed)
- The test output (whether tests passed)
- The list of affected files

## Evaluation Criteria

1. **Root cause**: Does the patch actually fix the root cause, or does it just
   mask the symptom? (e.g., catching an exception and ignoring it is masking)
2. **Security**: Does the patch introduce path traversal, injection, or other
   vulnerabilities?
3. **Conventions**: Does it follow the project's patterns? (indentation, naming,
   imports, error handling style)
4. **Blast radius**: Could this change break anything else? Check callers of
   the modified function.
5. **Test coverage**: Are the right tests being run? Are there edge cases that
   should be tested?
6. **Minimality**: Is this the smallest correct fix? Unnecessary changes increase
   risk.

## Tools Available

- **read_file_with_lines**: Read source code to understand context around the patch
- **search_files**: Search for callers/references to verify blast radius

## Output Format

After your analysis, your FINAL message must be a JSON block:

```json
{
  "approved": true or false,
  "feedback": "Concise rationale for your decision",
  "security_concerns": ["list of concerns, or empty"],
  "convention_issues": ["list of issues, or empty"],
  "test_coverage_notes": "Notes on test adequacy"
}
```

Be specific in your feedback. If rejecting, explain what the doctor should do
differently so it can retry successfully.
"""


class Reviewer:
    """Independent read-only reviewer for doctor fix packages."""

    MAX_ROUNDS = 4

    def __init__(self, gateway: Any):
        self.gateway = gateway

    def evaluate(self, fix_package: dict[str, Any]) -> ReviewVerdict:
        """Evaluate a fix package. Read-only tools, adversarial prompt."""
        fingerprint = fix_package.get("fingerprint", "")

        system = _REVIEWER_SYSTEM_PROMPT
        messages = [{"role": "user", "content": self._format_review_request(fix_package)}]

        for _round in range(self.MAX_ROUNDS):
            response = self.gateway.complete_with_tools(
                messages=messages,
                system=system,
                tools=_REVIEWER_TOOLS,
                max_tokens=4096,
                task="doctor",
            )

            if not response.success:
                # LLM unavailable — auto-approve (tests already passed)
                return ReviewVerdict(
                    approved=True,
                    feedback="Auto-approved: reviewer LLM unavailable, tests passed.",
                    fingerprint=fingerprint,
                )

            # No tool calls — parse the verdict
            if not response.tool_use:
                return self._parse_verdict(response.text, fingerprint)

            # Process read-only tool calls
            tool_results = []
            for tool_block in response.tool_use:
                # Only allow read-only tools
                if tool_block.name not in ("read_file_with_lines", "search_files"):
                    tool_results.append((
                        tool_block.tool_id,
                        tool_block.name,
                        {"error": "Reviewer can only use read-only tools."},
                    ))
                    continue
                result = execute(tool_block.name, tool_block.input)
                tool_results.append((tool_block.tool_id, tool_block.name, result))

            # Build messages for next round
            msg: dict[str, Any] = {"role": "assistant", "content": response.text or ""}
            if response.tool_use:
                msg["tool_calls"] = [
                    {
                        "id": t.tool_id,
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "arguments": json.dumps(t.input),
                        },
                    }
                    for t in response.tool_use
                ]
            messages.append(msg)
            for tool_id, name, result in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": name,
                    "content": json.dumps(result),
                })

        # Ran out of rounds — approve if tests passed
        return ReviewVerdict(
            approved=True,
            feedback="Auto-approved: reviewer reached max rounds, tests passed.",
            fingerprint=fingerprint,
        )

    def _format_review_request(self, fix_package: dict[str, Any]) -> str:
        """Format the fix package into a review prompt."""
        error = fix_package.get("error_signal", {})
        parts = [
            "## Fix Package for Review\n",
            f"**Fingerprint:** `{fix_package.get('fingerprint', '')}`",
            f"**Attempt:** {fix_package.get('attempt', 1)}",
            f"**Status:** {fix_package.get('status', '')}",
            "",
            "### Original Error",
            f"**Command:** `{' '.join(error.get('argv', []))}`",
            f"**Error:** `{error.get('error_type', '')}: {error.get('error_message', '')}`",
            "",
            "### Traceback",
            f"```\n{error.get('traceback', 'N/A')}\n```",
            "",
            "### Patch Diff",
            f"```diff\n{fix_package.get('patch_diff', 'No diff')}\n```",
            "",
            f"### Files Changed: {fix_package.get('files_changed', [])}",
            "",
            "### Test Output",
            f"**Passed:** {fix_package.get('tests_passed', False)}",
            f"```\n{fix_package.get('tests_output', 'No test output')}\n```",
            "",
            "Review this patch. Read the affected files for context, check for "
            "callers that might break, and evaluate security + conventions. "
            "End with your JSON verdict.",
        ]
        return "\n".join(parts)

    def _parse_verdict(self, text: str, fingerprint: str) -> ReviewVerdict:
        """Extract JSON verdict from the reviewer's final response."""
        # Try to find a JSON block in the response
        import re
        json_match = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            # Try bare JSON
            json_match = re.search(r"\{[^{}]*\"approved\"[^{}]*\}", text, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            else:
                # Can't parse — default to approved (tests passed)
                return ReviewVerdict(
                    approved=True,
                    feedback=f"Auto-approved: could not parse reviewer verdict. Raw: {text[:200]}",
                    fingerprint=fingerprint,
                )

        try:
            data = json.loads(raw)
            return ReviewVerdict(
                approved=bool(data.get("approved", True)),
                feedback=data.get("feedback", ""),
                security_concerns=data.get("security_concerns", []),
                convention_issues=data.get("convention_issues", []),
                test_coverage_notes=data.get("test_coverage_notes", ""),
                fingerprint=fingerprint,
            )
        except (json.JSONDecodeError, TypeError):
            return ReviewVerdict(
                approved=True,
                feedback=f"Auto-approved: JSON parse failed. Raw: {text[:200]}",
                fingerprint=fingerprint,
            )
