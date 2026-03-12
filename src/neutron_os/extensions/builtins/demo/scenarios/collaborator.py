"""'The Silent Contributor' — 6-act guided demo scenario.

Walks a new user (Jay) through the full NeutronOS pipeline:
  sensing -> review -> publish -> email -> extensions

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
    """Validate docflow is accessible."""
    try:
        from neutron_os.extensions.builtins.docflow.engine import DocFlowEngine

        DocFlowEngine()
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
                    "What does the pipeline know? Check sense and docflow status "
                    "to understand the current state of your program."
                ),
                mode="cli",
                commands=[
                    "neut sense status",
                    "neut doc status",
                ],
                hints=[
                    "sense status shows inbox/processed/draft counts.",
                    "doc status shows tracked documents and their publish state.",
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
                    f"neut doc review {WEEKLY_SUMMARY}",
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
                    f"neut doc review --chat {WEEKLY_SUMMARY}",
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
                title="Publish",
                description=(
                    "Generate a .docx artifact from the approved draft and track it "
                    "in the docflow pipeline. This proves the full document lifecycle: "
                    "source (markdown) -> artifact (docx) -> state tracking."
                ),
                mode="cli",
                commands=[
                    f"neut doc generate {WEEKLY_SUMMARY}",
                    "neut doc status",
                ],
                hints=[
                    "DocFlow uses the Factory/Provider pattern — swap pandoc for LaTeX, pptx, etc.",
                    "The link registry (.doc-registry.json) maps docs to published URLs.",
                    "Next: we'll draft an email from chat mode.",
                ],
                validator=_check_doc_status,
            ),
            Act(
                number=7,
                title="Make It Yours",
                description=(
                    "Scaffold a personal extension with a reactor log query tool, "
                    "a weekly-slides SKILL.md, and a .pptx docflow provider stub. "
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
                    "Extension not detected. Run 'neut ext init triga-tools' to create it."
                ),
            ),
        ],
    )
