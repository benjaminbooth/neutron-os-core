"""'The Silent Contributor' — 9-act guided demo scenario.

Walks a new user (Jay) through the full NeutronOS pipeline:
  sensing -> review -> publish -> publisher agent -> extensions

Acts 1-7 cover the core sense/review/push pipeline.
Acts 8-9 introduce the publisher agent using Jay's real work on the
Triga DT documentation website — showing how Neut proactively
discovers that a GitLab wiki is out of date and proposes an update.

Each act alternates between raw CLI and chat-assisted mode to prove
seamless context preservation across mode transitions.
"""

from __future__ import annotations

from pathlib import Path

from ..runner import Act, Scenario

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
WEEKLY_SUMMARY = str(FIXTURES_DIR / "weekly_summary_demo.md")


def _fixture_exists(name: str) -> bool:
    return (FIXTURES_DIR / name).exists()


def _check_sense_status() -> bool:
    """Validate that sense pipeline has some data."""
    try:
        from neutron_os.extensions.builtins.sense_agent.cli import INBOX_RAW, DRAFTS_DIR

        has_inbox = INBOX_RAW.exists() and any(INBOX_RAW.rglob("*"))
        has_drafts = DRAFTS_DIR.exists() and any(DRAFTS_DIR.glob("*.md"))
        return has_inbox or has_drafts
    except Exception:
        return False


def _check_doc_status() -> bool:
    """Validate publisher is accessible."""
    try:
        from neutron_os.extensions.builtins.publisher.engine import PublisherEngine

        PublisherEngine()
        return True
    except Exception:
        return False


def _check_extension_exists() -> bool:
    """Validate an extension was scaffolded."""
    try:
        from neutron_os.extensions.discovery import discover_extensions

        exts = discover_extensions()
        return len(exts) > 0
    except Exception:
        return False


def _setup() -> None:
    """Ensure demo fixtures are in place."""
    # Fixtures are static files shipped with the repo — no setup needed.
    # If sense inbox is empty, the demo will use fixture fallback.
    pass


def _teardown() -> None:
    """Clean up demo state (if any)."""
    pass


def build_scenario() -> Scenario:
    """Build the 'Silent Contributor' demo scenario."""
    return Scenario(
        name="The Silent Contributor",
        slug="collaborator",
        tagline=(
            "Jay has 55 commits but no voice in the weekly review. "
            "Let's fix that — using NeutronOS to amplify his work."
        ),
        setup_fn=_setup,
        teardown_fn=_teardown,
        next_steps=[
            "Complete full onboarding (GitLab, Teams, Linear): neut config",
            "Add your repositories as signal sources: neut sense pipeline sources --init",
            "Run your first real ingestion: neut sense pipeline ingest --source github",
        ],
        acts=[
            Act(
                number=1,
                title="Connect",
                description=(
                    "Two keys unlock the demo:\n\n"
                    "  1. An LLM API key (Anthropic or OpenAI) — powers chat and review\n"
                    "  2. A GitHub token (read:repo scope) — gives Neut visibility into your repos\n\n"
                    "We'll configure just these two now so the rest of the demo is live. "
                    "Full onboarding (GitLab, Microsoft 365, Linear) happens after the demo."
                ),
                mode="cli",
                commands=[
                    "neut config --set anthropic_api_key",
                    "neut config --set github_token",
                    "neut sense pipeline sources --check",
                ],
                hints=[
                    "Credentials are stored in runtime/config/ — gitignored, never committed.",
                    "Skip a key with Ctrl+C if you don't have it yet; Neut degrades gracefully.",
                    "Run 'neut doctor' at any time to check what's connected.",
                ],
                fallback_message=(
                    "No credentials configured — demo continues with fixture data. "
                    "AI-powered features (chat review, briefing) will show fallback output."
                ),
            ),
            Act(
                number=2,
                title="Ingest",
                description=(
                    "Process signals into structured data. If you have GitLab export "
                    "files in tools/exports/, they'll be processed. Otherwise, we'll "
                    "use the demo fixture — a pre-built weekly summary showing what "
                    "the pipeline produces."
                ),
                mode="cli",
                commands=[
                    "neut sense ingest --source gitlab",
                    "neut sense draft",
                ],
                hints=[
                    f"The demo fixture at {WEEKLY_SUMMARY} shows what a real draft looks like.",
                    "In production, 'neut sense serve' runs an HTTP server for continuous ingestion.",
                    "Voice memos, Teams transcripts, and freetext notes all flow through the same pipeline.",
                ],
                fallback_message=(
                    "No GitLab exports found — that's fine for the demo. "
                    "Check tools/demo/fixtures/weekly_summary_demo.md for a sample output."
                ),
            ),
            Act(
                number=3,
                title="Orient",
                description=(
                    "What does the pipeline know? Check sense and publisher status "
                    "to understand the current state of your program."
                ),
                mode="cli",
                commands=[
                    "neut sense status",
                    "neut pub status",
                ],
                hints=[
                    "sense status shows inbox/processed/draft counts.",
                    "neut pub overview shows all tracked documents and their push state.",
                    "Transition: next we'll review the weekly draft — first in CLI, then in chat.",
                ],
                validator=_check_doc_status,
            ),
            Act(
                number=4,
                title="Review (CLI)",
                description=(
                    "Review the weekly draft section-by-section in the terminal. "
                    "Notice the Reactor Log Digitization section is thin — just '55 commits. "
                    "Repos discovered.' This is where Jay's voice needs to be heard.\n\n"
                    "Press Q mid-review to test resume — re-running picks up where you left off."
                ),
                mode="cli",
                commands=[
                    f"neut pub review {WEEKLY_SUMMARY}",
                ],
                hints=[
                    "The review framework supports quick (one-shot) and detailed (item-by-item) modes.",
                    "Review state persists — you can quit and resume later.",
                    "Next: we'll do the same review conversationally in chat mode.",
                ],
            ),
            Act(
                number=5,
                title="Review (Chat)",
                description=(
                    "Same draft, now conversational. Chat mode lets you give "
                    "stream-of-consciousness feedback. Try typing natural language "
                    "comments about what Jay is actually building.\n\n"
                    "Mid-chat, type /status to check review progress without leaving chat."
                ),
                mode="chat",
                commands=[
                    f"neut pub review --chat {WEEKLY_SUMMARY}",
                ],
                hints=[
                    "Falls back gracefully if no LLM is configured.",
                    "/status works inside chat — it runs neut sense status inline.",
                    "/complete finalizes the review session.",
                    "The same review state is shared between CLI and chat modes.",
                ],
            ),
            Act(
                number=6,
                title="Push",
                description=(
                    "Generate a .docx artifact from the approved draft and push it "
                    "through the Publisher pipeline. This proves the full document lifecycle: "
                    "source (markdown) → artifact (docx) → state tracking → destination.\n\n"
                    "Notice that 'push' mirrors git semantics: you're sending to a remote endpoint, "
                    "not making a final proclamation. A draft push and a production push use the "
                    "same command — the --draft flag controls watermarking and endpoint routing."
                ),
                mode="cli",
                commands=[
                    f"neut pub generate {WEEKLY_SUMMARY}",
                    "neut pub push --draft",
                    "neut pub status",
                ],
                hints=[
                    "Publisher uses the Factory/Provider pattern — swap pandoc for LaTeX, pptx, etc.",
                    "neut pub endpoints shows all 19 built-in destinations with format support.",
                    "The link registry (.publisher-registry.json) maps doc_ids to pushed URLs.",
                    "Next: Jay has a Triga DT wiki that's gotten out of date. Let's fix it.",
                ],
                validator=_check_doc_status,
            ),
            Act(
                number=7,
                title="Make It Yours",
                description=(
                    "Scaffold a personal extension with a reactor log query tool, "
                    "a weekly-slides SKILL.md, and a .pptx publisher provider stub. "
                    "Then verify it appears in chat immediately — no restart needed."
                ),
                mode="cli",
                commands=[
                    "neut ext init reactor-tools",
                    "neut ext",
                    "neut ext check reactor-tools",
                ],
                hints=[
                    "The scaffold includes a SKILL.md compatible with Claude Code, Codex, and Copilot.",
                    "The .pptx provider stub connects to Jay's existing Gemini slide workflow.",
                    "Run 'neut ext docs' to generate EXTENSION_CONTRACTS.md for your AI assistant.",
                    "Extensions are pure Python files — no pip install, no compilation needed.",
                ],
                validator=_check_extension_exists,
                fallback_message=(
                    "Extension not detected. Run 'neut ext init reactor-tools' to create it."
                ),
            ),
            Act(
                number=8,
                title="Triga DT — Wiki Drift",
                description=(
                    "Jay maintains the Triga Digital Twin documentation on a GitLab wiki. "
                    "He hasn't updated it in months. Neut's publisher agent is about to "
                    "notice that for him.\n\n"
                    "We'll pull the wiki source, declare that the repo is authoritative, "
                    "then let the agent scan for drift between what the wiki says and "
                    "what the codebase actually does today."
                ),
                mode="cli",
                commands=[
                    # Pull the Triga DT wiki page into a local mirror
                    "neut pub pull-source gitlab-wiki --doc triga-dt-overview",
                    # Declare the authoritative source path
                    "# > Authoritative source: src/neutron_os/extensions/ (Enter to confirm)",
                    # Scan for drift
                    "neut pub agent scan --endpoint gitlab-wiki",
                ],
                hints=[
                    "pull-source asks: 'what is the authoritative source for this document?'",
                    "Once declared, the agent enforces that relationship on every future scan.",
                    "The agent uses RAG-indexed repo content to find current truth — not guesswork.",
                    "Drift is surfaced as structured DriftFindings with confidence scores.",
                ],
                fallback_message=(
                    "GitLab wiki not configured — demo shows fixture drift report. "
                    "Set gitlab_token in neut config to use a real wiki."
                ),
            ),
            Act(
                number=9,
                title="Triga DT — Approve & Push",
                description=(
                    "The agent found drift: the Triga DT overview page still references "
                    "the old 'neut doc publish' command and an outdated sensor polling interval. "
                    "It has generated a targeted update proposal — not a full rewrite, just "
                    "the two specific corrections needed.\n\n"
                    "Jay reviews the diff, approves, and the agent pushes the update "
                    "to the GitLab wiki. Jay didn't have to find the problem, write the fix, "
                    "or remember the wiki existed."
                ),
                mode="chat",
                commands=[
                    "neut pub agent propose triga-dt-overview",
                    "# /review → Jay approves",
                    "neut pub push --provider gitlab-wiki",
                ],
                hints=[
                    "The proposal shows exactly what changed: wiki claim vs. current reality.",
                    "Jay can approve as-is, edit the proposed markdown, or reject.",
                    "The push uses the standard Publisher engine — same pipeline as any other document.",
                    "After push, .publisher-state.json records the new wiki state for future drift detection.",
                    "This is the 'pleasantly surprised' experience: the system found and fixed the problem.",
                ],
                fallback_message=(
                    "No live wiki — demo shows the approval UX with fixture proposal. "
                    "The push step is skipped in fixture mode."
                ),
            ),
        ],
    )
