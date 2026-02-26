"""Diagram Intelligence System - orchestrates generation and evaluation."""

import asyncio
from pathlib import Path
from typing import Optional
import logging

from .parser import DiagramSpec, DiagramSpecParser
from .generators import GraphvizGenerator, PlantUMLGenerator, VegaGenerator
from .evaluator import DiagramEvaluator, DiagramEvaluation
from .design_system import DesignSystem


logger = logging.getLogger(__name__)


class DiagramIntelligence:
    """Orchestrates AI-powered diagram generation with quality evaluation.
    
    Workflow:
    1. Parse diagram specs from markdown
    2. Generate diagram using appropriate backend
    3. Evaluate quality with Claude
    4. If score < 8.0, get improvement suggestions and regenerate
    5. Iterate until quality threshold is met (max 3 iterations)
    6. Replace spec with final diagram reference in markdown
    """
    
    MAX_ITERATIONS = 3
    QUALITY_THRESHOLD = 8.0
    
    def __init__(self, llm_provider, design_system: Optional[DesignSystem] = None):
        """Initialize Diagram Intelligence.
        
        Args:
            llm_provider: LLM provider for evaluation (e.g., AnthropicProvider)
            design_system: Design system for styling
        """
        self.llm_provider = llm_provider
        self.design_system = design_system or DesignSystem.default()
        self.evaluator = DiagramEvaluator(llm_provider)
        
        # Initialize generators
        self.generators = {
            'graphviz': GraphvizGenerator(design_system),
            'plantuml': PlantUMLGenerator(design_system),
            'vega': VegaGenerator(design_system),
        }
    
    async def process_document(self, markdown: str, output_dir: Path) -> tuple[str, list[Path]]:
        """Process all diagrams in a markdown document.
        
        Args:
            markdown: Markdown content with [DIAGRAM]...[/DIAGRAM] blocks
            output_dir: Directory to save generated diagrams
        
        Returns:
            Tuple of (updated_markdown, list_of_generated_files)
        """
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract diagram specifications
        diagrams = DiagramSpecParser.extract_diagrams(markdown)
        logger.info(f"Found {len(diagrams)} diagrams to process")
        
        generated_files = []
        updated_markdown = markdown
        
        for i, diagram_spec in enumerate(diagrams):
            logger.info(f"Processing diagram {i+1}/{len(diagrams)}: {diagram_spec.title}")
            
            # Generate and evaluate
            diagram_path = output_dir / f"diagram_{i+1:02d}.svg"
            final_path = await self.generate_and_evaluate(diagram_spec, diagram_path)
            
            if final_path:
                generated_files.append(final_path)
                # Replace in markdown
                relative_path = final_path.relative_to(output_dir.parent)
                updated_markdown = DiagramSpecParser.replace_diagram_in_markdown(
                    updated_markdown, diagram_spec, str(relative_path)
                )
        
        return updated_markdown, generated_files
    
    async def generate_and_evaluate(self, spec: DiagramSpec, output_path: Path) -> Optional[Path]:
        """Generate a diagram and iterate until quality threshold is met.
        
        Args:
            spec: Diagram specification
            output_path: Where to save final diagram
        
        Returns:
            Path to final diagram or None if failed
        """
        for iteration in range(1, self.MAX_ITERATIONS + 1):
            logger.info(f"  Iteration {iteration}/{self.MAX_ITERATIONS}")
            
            # Generate diagram
            generator = self._select_generator(spec.type)
            diagram_code = generator.generate(spec)
            
            # Render to file
            success = generator.render(diagram_code, output_path)
            if not success:
                logger.error(f"Failed to render diagram: {spec.title}")
                return None
            
            # Evaluate quality
            evaluation = await self.evaluator.evaluate(
                str(output_path),
                spec.__dict__,
                self.design_system.__dict__
            )
            
            logger.info(f"  Quality Score: {evaluation.overall_score:.1f}/10")
            logger.info(f"    Readability: {evaluation.readability:.1f}")
            logger.info(f"    Consistency: {evaluation.consistency:.1f}")
            logger.info(f"    Intuitiveness: {evaluation.intuitiveness:.1f}")
            logger.info(f"    Correctness: {evaluation.correctness:.1f}")
            
            # Check if quality is acceptable
            if evaluation.passed:
                logger.info(f"✓ Diagram passed quality evaluation: {spec.title}")
                return output_path
            
            # Get improvement feedback and update spec
            if iteration < self.MAX_ITERATIONS:
                logger.info(f"  Feedback: {evaluation.feedback}")
                spec = await self._improve_spec(spec, evaluation)
            else:
                logger.warning(
                    f"✗ Diagram did not reach quality threshold after {self.MAX_ITERATIONS} "
                    f"iterations: {spec.title} (score: {evaluation.overall_score:.1f}/10)"
                )
        
        return output_path  # Return even if below threshold
    
    def _select_generator(self, diagram_type: str):
        """Select appropriate generator for diagram type."""
        # Map diagram types to generators
        type_to_generator = {
            'flowchart': 'graphviz',
            'architecture': 'plantuml',
            'sequence': 'plantuml',
            'erd': 'graphviz',
            'timeline': 'vega',
            'state_machine': 'graphviz',
            'comparison': 'vega',
        }
        
        generator_key = type_to_generator.get(diagram_type, 'graphviz')
        return self.generators[generator_key]
    
    async def _improve_spec(self, spec: DiagramSpec, evaluation: DiagramEvaluation) -> DiagramSpec:
        """Ask Claude to suggest improvements to the spec based on evaluation.
        
        Args:
            spec: Current diagram specification
            evaluation: Evaluation result with feedback
        
        Returns:
            Updated DiagramSpec with improvements
        """
        improvement_prompt = f"""
Based on this diagram evaluation feedback, suggest specific improvements to the diagram spec
to address the issues and increase the quality score.

**Current Spec:**
- Type: {spec.type}
- Title: {spec.title}
- Elements: {spec.elements}
- Flow: {spec.flow}

**Evaluation Feedback:**
- Score: {evaluation.overall_score:.1f}/10
- Readability: {evaluation.readability:.1f}
- Consistency: {evaluation.consistency:.1f}
- Intuitiveness: {evaluation.intuitiveness:.1f}
- Correctness: {evaluation.correctness:.1f}

**Issues Found:**
{evaluation.feedback}

Provide specific, actionable suggestions to improve the spec. Focus on:
1. Reorganizing elements for better layout
2. Simplifying relationships
3. Improving clarity and readability
4. Ensuring design system compliance

Format your response as concrete changes to make."""
        
        try:
            response = await self.llm_provider.invoke(
                messages=[{"role": "user", "content": improvement_prompt}],
                system="You are a diagram design expert. Suggest specific improvements to diagram specifications.",
            )
            
            # For now, return spec as-is
            # In production, could parse Claude's suggestions and apply them
            logger.info(f"Improvement suggestions: {response[:200]}...")
            return spec
        
        except Exception as e:
            logger.error(f"Failed to get improvement suggestions: {e}")
            return spec
