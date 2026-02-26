"""Quality evaluation of generated diagrams using AI."""

from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class DiagramEvaluation:
    """Evaluation result for a diagram."""
    
    readability: float  # 0-10, how easy to read
    consistency: float  # 0-10, design system adherence
    intuitiveness: float  # 0-10, how intuitive layout is
    correctness: float  # 0-10, accurate representation
    overall_score: float  # Average of above
    feedback: str  # Specific improvement suggestions
    passed: bool = False  # True if score >= threshold


class DiagramEvaluator:
    """Evaluate diagram quality using Claude AI.
    
    This agent evaluates:
    - Readability: Can humans quickly understand this?
    - Consistency: Does it follow design system?
    - Intuitiveness: Is the layout logical?
    - Correctness: Does it accurately show the spec?
    """
    
    QUALITY_THRESHOLD = 8.0  # Out of 10
    
    def __init__(self, llm_provider):
        """Initialize evaluator.
        
        Args:
            llm_provider: LLM provider (e.g., AnthropicProvider)
        """
        self.llm_provider = llm_provider
    
    async def evaluate(self, diagram_path: str, diagram_spec: dict,
                      design_system: dict) -> DiagramEvaluation:
        """Evaluate a generated diagram.
        
        Args:
            diagram_path: Path to rendered diagram image/SVG
            diagram_spec: Original specification dict
            design_system: Design system configuration
        
        Returns:
            DiagramEvaluation with scores and feedback
        """
        
        # Read diagram file
        try:
            with open(diagram_path, 'rb') as f:
                diagram_bytes = f.read()
        except FileNotFoundError:
            return DiagramEvaluation(
                readability=0, consistency=0, intuitiveness=0,
                correctness=0, overall_score=0, feedback="Diagram file not found"
            )
        
        # Prepare evaluation prompt
        prompt = self._build_evaluation_prompt(diagram_spec, design_system)
        
        # Get Claude evaluation
        try:
            response = await self.llm_provider.invoke(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                system=self._evaluation_system_prompt(),
            )
            
            # Parse response
            evaluation = self._parse_evaluation_response(response)
            evaluation.passed = evaluation.overall_score >= self.QUALITY_THRESHOLD
            
            return evaluation
        
        except Exception as e:
            return DiagramEvaluation(
                readability=0, consistency=0, intuitiveness=0,
                correctness=0, overall_score=0,
                feedback=f"Evaluation failed: {str(e)}"
            )
    
    def _evaluation_system_prompt(self) -> str:
        """System prompt for evaluation agent."""
        return """You are an expert UX/UI designer and information architect evaluating 
diagram quality. Your role is to assess diagrams objectively on four dimensions:

1. **Readability** (0-10): How easy is it to read and understand the diagram at a glance?
   - Clear labeling, appropriate text size, good contrast
   - No overlapping elements, proper spacing
   - Visual hierarchy is clear

2. **Consistency** (0-10): Does the diagram follow the design system?
   - Colors match the approved palette
   - Typography is correct and readable
   - Spacing and alignment follow guidelines
   - Icon usage is appropriate

3. **Intuitiveness** (0-10): Is the layout logical and easy to follow?
   - Flow direction makes sense (usually top-to-bottom or left-to-right)
   - Connections are clear and unambiguous
   - Related elements are grouped appropriately
   - No confusing or misleading layouts

4. **Correctness** (0-10): Does the diagram accurately represent the specification?
   - All required elements are present
   - Relationships and flows are accurate
   - No information is missing or contradictory
   - Title and description are relevant

Provide your evaluation as JSON with this structure:
{
    "readability": <0-10>,
    "consistency": <0-10>,
    "intuitiveness": <0-10>,
    "correctness": <0-10>,
    "overall_score": <average of above>,
    "feedback": "<specific suggestions for improvement>",
    "improvements_needed": [
        "<specific improvement 1>",
        "<specific improvement 2>"
    ]
}

Be strict but fair. An 8.0 score is good. Below 8.0 needs improvement."""
    
    def _build_evaluation_prompt(self, diagram_spec: dict, design_system: dict) -> str:
        """Build evaluation prompt for a specific diagram."""
        return f"""Please evaluate this diagram against the specification and design system:

**Diagram Specification:**
{json.dumps(diagram_spec, indent=2)}

**Design System:**
{json.dumps(design_system, indent=2)}

Evaluate the rendered diagram on the four dimensions and provide improvement suggestions
if the overall score is below 8.0.

Respond with only the JSON evaluation result."""
    
    def _parse_evaluation_response(self, response: str) -> DiagramEvaluation:
        """Parse Claude's JSON evaluation response."""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]
            
            data = json.loads(json_str)
            
            return DiagramEvaluation(
                readability=data.get('readability', 0),
                consistency=data.get('consistency', 0),
                intuitiveness=data.get('intuitiveness', 0),
                correctness=data.get('correctness', 0),
                overall_score=data.get('overall_score', 0),
                feedback=data.get('feedback', ''),
            )
        
        except (json.JSONDecodeError, ValueError) as e:
            return DiagramEvaluation(
                readability=0, consistency=0, intuitiveness=0,
                correctness=0, overall_score=0,
                feedback=f"Failed to parse evaluation: {str(e)}"
            )
