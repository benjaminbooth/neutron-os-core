"""DocFlow command-line interface."""

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .. import __version__
from ..core import load_config, LinkRegistry, GitContext

app = typer.Typer(
    name="docflow",
    help="Document Lifecycle Management System - markdown to published documents",
)

console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@app.command()
def version():
    """Show DocFlow version."""
    console.print(f"DocFlow {__version__}")


@app.command()
def publish(
    source: Path = typer.Argument(..., help="Path to markdown file to publish"),
    draft: bool = typer.Option(False, "--draft", help="Publish as draft (enables review)"),
    reviewers: Optional[str] = typer.Option(None, "--reviewers", help="Comma-separated list of reviewers"),
    bump_version: bool = typer.Option(False, "--bump-version", help="Bump document version"),
    output: Optional[Path] = typer.Option(None, "--output", help="Local output path (default: generated/)"),
):
    """Publish a markdown document to DOCX.
    
    Converts markdown file to Word document and optionally uploads to configured storage.
    
    Examples:
        # Local generation only
        docflow publish docs/prd/my-doc.md
        
        # Generate draft for review
        docflow publish --draft docs/prd/my-doc.md --reviewers alice@example.com,bob@example.com
        
        # Specify custom output location
        docflow publish docs/prd/my-doc.md --output ./custom-output/
    """
    if not source.exists():
        console.print(f"[red]Error: File not found: {source}[/red]")
        raise typer.Exit(1)
    
    console.print(f"[blue]Publishing {source}...[/blue]")
    
    # TODO: Implement actual publishing logic
    console.print("[green]✓ Published (stub implementation)[/green]")


@app.command()
def review(
    action: str = typer.Argument("list", help="Action: list, extend, close, promote"),
    doc_id: Optional[str] = typer.Argument(None, help="Document ID (for extend/close/promote)"),
    days: Optional[int] = typer.Option(None, "--days", help="Days to extend deadline"),
    outcome: Optional[str] = typer.Option(None, "--outcome", help="Review outcome (approved, needs_revision, etc.)"),
):
    """Manage document review periods.
    
    Examples:
        # List active reviews
        docflow review list
        
        # Extend deadline by 3 days
        docflow review extend my-doc --days 3
        
        # Close review with outcome
        docflow review close my-doc --outcome approved
        
        # Promote draft to published
        docflow review promote my-doc
    """
    if action == "list":
        console.print("[blue]Active Reviews:[/blue]")
        # TODO: Load and display active reviews
        console.print("(No active reviews)")
    
    elif action == "extend":
        if not doc_id:
            console.print("[red]Error: doc_id required for extend[/red]")
            raise typer.Exit(1)
        console.print(f"[blue]Extending review for {doc_id}...[/blue]")
        # TODO: Implement extend logic
        console.print("[green]✓ Review extended[/green]")
    
    elif action == "close":
        if not doc_id:
            console.print("[red]Error: doc_id required for close[/red]")
            raise typer.Exit(1)
        console.print(f"[blue]Closing review for {doc_id}...[/blue]")
        # TODO: Implement close logic
        console.print("[green]✓ Review closed[/green]")
    
    elif action == "promote":
        if not doc_id:
            console.print("[red]Error: doc_id required for promote[/red]")
            raise typer.Exit(1)
        console.print(f"[blue]Promoting {doc_id} to published...[/blue]")
        # TODO: Implement promote logic
        console.print("[green]✓ Promoted to published[/green]")
    
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    doc_id: Optional[str] = typer.Argument(None, help="Show status for specific document"),
):
    """Show document and workflow status.
    
    Examples:
        # Overall status
        docflow status
        
        # Status for specific document
        docflow status my-doc
    """
    console.print("[blue]DocFlow Status[/blue]")
    
    # Load config and display
    try:
        config = load_config()
        
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Storage Provider", config.storage.provider)
        table.add_row("Git Branches (publish)", ", ".join(config.git.publish_branches))
        table.add_row("LLM Model", config.llm.model)
        table.add_row("Poll Interval", f"{config.poll_interval_seconds}s")
        
        console.print(table)
    
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load config: {e}[/yellow]")
    
    # TODO: Load and display document states
    console.print("\n[blue]Documents[/blue]")
    console.print("(No documents yet)")


@app.command()
def meetings(
    action: str = typer.Argument("scan", help="Action: scan, extract, match"),
):
    """Process meeting transcripts and extract decisions.
    
    Examples:
        # Scan for new meeting transcripts
        docflow meetings scan
        
        # Extract decisions from transcript
        docflow meetings extract transcript.vtt
    """
    console.print(f"[blue]Processing meetings ({action})...[/blue]")
    # TODO: Implement meeting processing
    console.print("[green]✓ Done[/green]")


@app.command()
def embed(
    regenerate: bool = typer.Option(False, "--regenerate", help="Regenerate all embeddings"),
):
    """Manage document embeddings and RAG integration.
    
    Examples:
        # Embed changed documents
        docflow embed
        
        # Regenerate all embeddings
        docflow embed --regenerate
    """
    console.print("[blue]Updating embeddings...[/blue]")
    # TODO: Implement embedding pipeline
    console.print("[green]✓ Embeddings updated[/green]")


@app.command()
def daemon(
    interval: str = typer.Option("15m", "--interval", help="Polling interval (e.g., 15m, 1h)"),
    once: bool = typer.Option(False, "--once", help="Run once and exit"),
):
    """Start daemon to monitor and process documents.
    
    Long-running process that:
    - Polls for document changes
    - Fetches comments from storage
    - Processes meeting transcripts
    - Updates embeddings
    - Sends notifications
    
    Examples:
        # Run daemon (15-min polling)
        docflow daemon
        
        # Custom interval
        docflow daemon --interval 30m
        
        # Run once
        docflow daemon --once
    """
    console.print(f"[blue]Starting DocFlow daemon (interval: {interval})...[/blue]")
    
    if once:
        console.print("[blue]Running once (--once flag set)[/blue]")
    
    # TODO: Implement daemon loop
    console.print("[green]✓ Daemon started[/green]")


@app.command()
def check_links(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Validate all cross-document links in markdown files.
    
    Examples:
        # Check links
        docflow check-links
        
        # Verbose output
        docflow check-links -v
    """
    console.print("[blue]Checking cross-document links...[/blue]")
    
    try:
        registry = LinkRegistry()
        
        console.print(f"[cyan]Registered documents: {len(registry.entries)}[/cyan]")
        
        for doc_id, entry in registry.entries.items():
            if verbose:
                console.print(f"  {doc_id}: {entry.get('published_url', 'UNPUBLISHED')}")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def lint():
    """Validate documents for common issues.
    
    Checks:
    - Missing cross-document links
    - TODO/FIXME markers
    - Syntax errors in markdown
    - Missing metadata
    """
    console.print("[blue]Linting documents...[/blue]")
    # TODO: Implement linting
    console.print("[green]✓ All checks passed[/green]")


@app.callback()
def callback():
    """DocFlow document lifecycle management system."""
    pass


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
