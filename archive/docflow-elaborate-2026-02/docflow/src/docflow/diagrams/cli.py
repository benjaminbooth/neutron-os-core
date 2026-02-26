"""CLI commands for diagram generation."""

import typer
from pathlib import Path
import asyncio
import logging

app = typer.Typer(help="Diagram Intelligence System - generate beautiful diagrams automatically")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.command()
def generate(
    doc_path: Path = typer.Argument(..., help="Path to markdown document"),
    output_dir: Path = typer.Option(
        None,
        help="Directory for generated diagrams (default: .diagrams)"
    ),
    config_path: Path = typer.Option(
        None,
        help="Path to design system config (YAML)"
    ),
):
    """Generate diagrams from markdown specifications.
    
    Finds [DIAGRAM]...[/DIAGRAM] blocks in markdown, generates beautiful diagrams,
    evaluates quality with AI, and iteratively improves until reaching 8.0+ quality score.
    
    Example:
        docflow diagram generate docs/architecture.md --output-dir docs/diagrams
    """
    from . import DiagramIntelligence
    from ..providers.factory import get_provider
    from .design_system import DesignSystem
    
    # Set defaults
    if output_dir is None:
        output_dir = doc_path.parent / ".diagrams"
    
    # Load design system
    design_system = DesignSystem.default()
    if config_path and config_path.exists():
        design_system = DesignSystem.from_yaml(config_path)
    
    # Get LLM provider
    try:
        llm_provider = get_provider("llm", "anthropic")
    except Exception as e:
        typer.echo(f"Error: Failed to initialize LLM provider: {e}", err=True)
        raise typer.Exit(1)
    
    # Read markdown
    try:
        with open(doc_path, 'r') as f:
            markdown = f.read()
    except FileNotFoundError:
        typer.echo(f"Error: File not found: {doc_path}", err=True)
        raise typer.Exit(1)
    
    # Process diagrams
    intelligence = DiagramIntelligence(llm_provider, design_system)
    
    try:
        updated_markdown, generated_files = asyncio.run(
            intelligence.process_document(markdown, output_dir)
        )
        
        # Save updated markdown
        updated_path = doc_path.with_stem(doc_path.stem + ".generated")
        with open(updated_path, 'w') as f:
            f.write(updated_markdown)
        
        typer.echo(f"✓ Generated {len(generated_files)} diagrams", fg=typer.colors.GREEN)
        typer.echo(f"✓ Updated markdown: {updated_path}")
        
        for file in generated_files:
            typer.echo(f"  - {file.name}")
    
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        logger.exception("Failed to generate diagrams")
        raise typer.Exit(1)


@app.command()
def evaluate(
    diagram_path: Path = typer.Argument(..., help="Path to diagram file (SVG/PNG)"),
    spec_path: Path = typer.Option(
        None,
        help="Path to diagram spec JSON"
    ),
):
    """Evaluate quality of an existing diagram.
    
    Example:
        docflow diagram evaluate diagrams/architecture.svg --spec-path specs/arch.json
    """
    from . import DiagramEvaluator
    from ..providers.factory import get_provider
    import json
    
    # Get LLM provider
    try:
        llm_provider = get_provider("llm", "anthropic")
    except Exception as e:
        typer.echo(f"Error: Failed to initialize LLM provider: {e}", err=True)
        raise typer.Exit(1)
    
    # Load spec
    spec = {}
    if spec_path and spec_path.exists():
        with open(spec_path, 'r') as f:
            spec = json.load(f)
    
    # Evaluate
    evaluator = DiagramEvaluator(llm_provider)
    evaluation = asyncio.run(evaluator.evaluate(str(diagram_path), spec, {}))
    
    # Display results
    typer.echo(f"\nDiagram Quality Evaluation")
    typer.echo("=" * 40)
    typer.echo(f"Overall Score: {evaluation.overall_score:.1f}/10 ", end="")
    
    if evaluation.passed:
        typer.echo("✓", fg=typer.colors.GREEN)
    else:
        typer.echo("⚠", fg=typer.colors.YELLOW)
    
    typer.echo(f"  Readability:   {evaluation.readability:.1f}/10")
    typer.echo(f"  Consistency:   {evaluation.consistency:.1f}/10")
    typer.echo(f"  Intuitiveness: {evaluation.intuitiveness:.1f}/10")
    typer.echo(f"  Correctness:   {evaluation.correctness:.1f}/10")
    
    if evaluation.feedback:
        typer.echo(f"\nFeedback:")
        typer.echo(evaluation.feedback)


@app.command()
def design_system(
    output_path: Path = typer.Option(
        Path(".docflow/design-system.yaml"),
        help="Where to save design system template"
    ),
):
    """Export design system template.
    
    Creates a YAML template for customizing diagram styling.
    
    Example:
        docflow diagram design-system --output-path config/design-system.yaml
    """
    from .design_system import DesignSystem
    import yaml
    
    ds = DesignSystem.default()
    
    output_data = {
        'colors': {
            'primary': ds.colors.primary,
            'secondary': ds.colors.secondary,
            'accent': ds.colors.accent,
            'danger': ds.colors.danger,
            'neutral_light': ds.colors.neutral_light,
            'neutral_dark': ds.colors.neutral_dark,
        },
        'typography': {
            'fonts_approved': ds.typography.fonts_approved,
            'sizes': ds.typography.sizes,
            'line_height': ds.typography.line_height,
        },
        'spacing': {
            'horizontal_padding': ds.spacing.horizontal_padding,
            'vertical_padding': ds.spacing.vertical_padding,
            'element_spacing': ds.spacing.element_spacing,
        },
        'icon_library': ds.icon_library,
        'approved_icons': ds.approved_icons[:5],  # Show sample
    }
    
    # Create directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write file
    with open(output_path, 'w') as f:
        yaml.dump(output_data, f, default_flow_style=False)
    
    typer.echo(f"✓ Design system template saved: {output_path}")


if __name__ == "__main__":
    app()
