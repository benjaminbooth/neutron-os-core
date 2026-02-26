#!/usr/bin/env python3
"""
Example: Using Diagram Intelligence System programmatically.

This demonstrates how to use the diagram system from Python code
instead of the CLI.
"""

import asyncio
from pathlib import Path
import logging

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_1_basic_generation():
    """Example 1: Generate diagrams from markdown file."""
    from docflow.diagrams import DiagramIntelligence
    from docflow.providers.factory import get_provider
    from docflow.diagrams.design_system import DesignSystem
    
    print("\n" + "="*60)
    print("Example 1: Basic Diagram Generation from Markdown")
    print("="*60)
    
    # Read markdown document
    markdown = """
# Architecture

[DIAGRAM]
type: flowchart
title: Example Flow
description: A simple example flow
elements:
  - Start
  - Process
  - End
flow:
  - Start → Process
  - Process → End
[/DIAGRAM]

This is our flow diagram.
"""
    
    # Get LLM provider and design system
    llm_provider = get_provider("llm", "anthropic")
    design_system = DesignSystem.default()
    
    # Create intelligence system
    intelligence = DiagramIntelligence(llm_provider, design_system)
    
    # Process diagrams
    output_dir = Path("./output/diagrams")
    updated_markdown, generated_files = await intelligence.process_document(
        markdown, output_dir
    )
    
    print(f"✓ Generated {len(generated_files)} diagrams")
    for file in generated_files:
        print(f"  - {file.name}")
    
    # Save updated markdown
    output_md = Path("./output/result.md")
    output_md.write_text(updated_markdown)
    print(f"✓ Saved updated markdown to {output_md}")


async def example_2_custom_design_system():
    """Example 2: Use custom design system colors."""
    from docflow.diagrams import DiagramIntelligence, DesignSystem, ColorPalette
    from docflow.providers.factory import get_provider
    
    print("\n" + "="*60)
    print("Example 2: Custom Design System")
    print("="*60)
    
    markdown = """
[DIAGRAM]
type: flowchart
title: Custom Colors
elements:
  - Step 1
  - Step 2
flow:
  - Step 1 → Step 2
[/DIAGRAM]
"""
    
    # Create custom design system
    custom_palette = ColorPalette(
        primary="#FF6B6B",      # Red
        secondary="#4ECDC4",    # Teal
        accent="#FFE66D",       # Yellow
    )
    
    design_system = DesignSystem()
    design_system.colors = custom_palette
    
    # Generate with custom colors
    llm_provider = get_provider("llm", "anthropic")
    intelligence = DiagramIntelligence(llm_provider, design_system)
    
    output_dir = Path("./output/custom_colors")
    updated_md, files = await intelligence.process_document(markdown, output_dir)
    
    print(f"✓ Generated diagram with custom colors")
    print(f"  Primary: {custom_palette.primary}")
    print(f"  Secondary: {custom_palette.secondary}")
    print(f"  Accent: {custom_palette.accent}")


async def example_3_evaluate_diagram():
    """Example 3: Evaluate an existing diagram."""
    from docflow.diagrams import DiagramEvaluator
    from docflow.providers.factory import get_provider
    
    print("\n" + "="*60)
    print("Example 3: Evaluate Diagram Quality")
    print("="*60)
    
    llm_provider = get_provider("llm", "anthropic")
    evaluator = DiagramEvaluator(llm_provider)
    
    # Evaluate a diagram
    diagram_path = "./output/diagrams/diagram_01.svg"
    spec = {
        "type": "flowchart",
        "title": "Example Flow",
        "elements": ["Start", "Process", "End"],
    }
    
    try:
        evaluation = await evaluator.evaluate(diagram_path, spec, {})
        
        print(f"Overall Score: {evaluation.overall_score:.1f}/10")
        print(f"  Readability:   {evaluation.readability:.1f}")
        print(f"  Consistency:   {evaluation.consistency:.1f}")
        print(f"  Intuitiveness: {evaluation.intuitiveness:.1f}")
        print(f"  Correctness:   {evaluation.correctness:.1f}")
        
        if evaluation.feedback:
            print(f"\nFeedback: {evaluation.feedback}")
    
    except FileNotFoundError:
        print(f"Note: {diagram_path} not found (run example 1 first)")


async def example_4_multiple_diagrams():
    """Example 4: Document with multiple diagrams."""
    from docflow.diagrams import DiagramIntelligence
    from docflow.providers.factory import get_provider
    from docflow.diagrams.design_system import DesignSystem
    
    print("\n" + "="*60)
    print("Example 4: Multiple Diagrams in One Document")
    print("="*60)
    
    markdown = """
# Multi-Diagram Document

## Flow 1
[DIAGRAM]
type: flowchart
title: Flow 1
elements:
  - A
  - B
flow:
  - A → B
[/DIAGRAM]

## Flow 2
[DIAGRAM]
type: flowchart
title: Flow 2
elements:
  - X
  - Y
  - Z
flow:
  - X → Y
  - Y → Z
[/DIAGRAM]

## States
[DIAGRAM]
type: state_machine
title: State Machine
elements:
  - Idle
  - Running
  - Done
flow:
  - Idle → Running
  - Running → Done
[/DIAGRAM]
"""
    
    llm_provider = get_provider("llm", "anthropic")
    design_system = DesignSystem.default()
    intelligence = DiagramIntelligence(llm_provider, design_system)
    
    output_dir = Path("./output/multi_diagram")
    updated_md, files = await intelligence.process_document(markdown, output_dir)
    
    print(f"✓ Generated {len(files)} diagrams from one document")
    for i, file in enumerate(files, 1):
        print(f"  {i}. {file.name}")


async def example_5_parse_and_inspect():
    """Example 5: Parse diagrams without generating."""
    from docflow.diagrams import DiagramSpecParser
    
    print("\n" + "="*60)
    print("Example 5: Parse Diagram Specifications")
    print("="*60)
    
    markdown = """
[DIAGRAM]
type: flowchart
title: My Flow
description: Shows the flow of data
elements:
  - Input
  - Process
  - Output
flow:
  - Input → Process
  - Process → Output
[/DIAGRAM]
"""
    
    # Parse without rendering
    diagrams = DiagramSpecParser.extract_diagrams(markdown)
    
    for i, diagram in enumerate(diagrams, 1):
        print(f"\nDiagram {i}:")
        print(f"  Type: {diagram.type}")
        print(f"  Title: {diagram.title}")
        print(f"  Description: {diagram.description}")
        print(f"  Elements: {diagram.elements}")
        print(f"  Flow: {diagram.flow}")


async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Diagram Intelligence System - Python Examples")
    print("="*60)
    
    # Example 1: Basic generation
    try:
        await example_1_basic_generation()
    except Exception as e:
        logger.error(f"Example 1 failed: {e}")
    
    # Example 2: Custom design system
    try:
        await example_2_custom_design_system()
    except Exception as e:
        logger.error(f"Example 2 failed: {e}")
    
    # Example 3: Evaluate diagram
    try:
        await example_3_evaluate_diagram()
    except Exception as e:
        logger.error(f"Example 3 failed: {e}")
    
    # Example 4: Multiple diagrams
    try:
        await example_4_multiple_diagrams()
    except Exception as e:
        logger.error(f"Example 4 failed: {e}")
    
    # Example 5: Parse diagrams
    try:
        await example_5_parse_and_inspect()
    except Exception as e:
        logger.error(f"Example 5 failed: {e}")
    
    print("\n" + "="*60)
    print("Examples Complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
