"""Unit tests for diagram intelligence system."""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from docflow.diagrams import (
    DiagramSpec, DiagramSpecParser, DesignSystem, ColorPalette,
    GraphvizGenerator, PlantUMLGenerator, VegaGenerator,
    DiagramEvaluator, DiagramEvaluation, DiagramIntelligence
)


class TestDiagramSpecParser:
    """Test diagram specification parsing."""
    
    def test_extract_single_diagram(self):
        """Test extracting a single diagram from markdown."""
        markdown = """
# Document

[DIAGRAM]
type: flowchart
title: Test Flow
elements:
  - Start
  - End
flow:
  - Start → End
[/DIAGRAM]

Some text.
"""
        specs = DiagramSpecParser.extract_diagrams(markdown)
        
        assert len(specs) == 1
        assert specs[0].type == "flowchart"
        assert specs[0].title == "Test Flow"
        assert specs[0].elements == ["Start", "End"]
        assert specs[0].flow == [("Start", "End")]
    
    def test_extract_multiple_diagrams(self):
        """Test extracting multiple diagrams."""
        markdown = """
[DIAGRAM]
type: flowchart
title: Flow 1
elements:
  - A
[/DIAGRAM]

[DIAGRAM]
type: sequence
title: Flow 2
elements:
  - B
[/DIAGRAM]
"""
        specs = DiagramSpecParser.extract_diagrams(markdown)
        
        assert len(specs) == 2
        assert specs[0].title == "Flow 1"
        assert specs[1].title == "Flow 2"
    
    def test_parse_flow_formats(self):
        """Test parsing different flow formats."""
        markdown = """
[DIAGRAM]
type: flowchart
title: Test
flow:
  - A → B
  - B -> C
[/DIAGRAM]
"""
        specs = DiagramSpecParser.extract_diagrams(markdown)
        
        assert len(specs[0].flow) == 2
        assert specs[0].flow[0] == ("A", "B")
        assert specs[0].flow[1] == ("B", "C")
    
    def test_replace_diagram_in_markdown(self):
        """Test replacing diagram spec with image reference."""
        markdown = """
[DIAGRAM]
type: flowchart
title: Test
[/DIAGRAM]
"""
        spec = DiagramSpec(type="flowchart", title="Test")
        
        result = DiagramSpecParser.replace_diagram_in_markdown(
            markdown, spec, "diagrams/test.svg"
        )
        
        assert "![Test](diagrams/test.svg)" in result
        assert "[DIAGRAM]" not in result


class TestDesignSystem:
    """Test design system configuration."""
    
    def test_default_design_system(self):
        """Test default design system values."""
        ds = DesignSystem.default()
        
        assert ds.colors.primary == "#2563EB"
        assert ds.colors.secondary == "#10B981"
        assert ds.typography.sizes["title"] == 18
        assert ds.spacing.horizontal_padding == 20
    
    def test_custom_color_palette(self):
        """Test custom color palette."""
        palette = ColorPalette(
            primary="#FF0000",
            secondary="#00FF00",
        )
        
        assert palette.primary == "#FF0000"
        assert palette.get("primary") == "#FF0000"
        assert palette.get("invalid", "#000") == "#000"
    
    def test_design_system_to_graphviz(self):
        """Test converting design system to Graphviz attributes."""
        ds = DesignSystem.default()
        attrs = ds.to_graphviz_attrs()
        
        assert "bgcolor" in attrs
        assert "fontname" in attrs
        assert "fontsize" in attrs
    
    def test_design_system_to_css(self):
        """Test generating CSS from design system."""
        ds = DesignSystem.default()
        css = ds.to_css()
        
        assert "--color-primary" in css
        assert "#2563EB" in css
        assert "font-family" in css


class TestGraphvizGenerator:
    """Test Graphviz diagram generation."""
    
    def test_generate_flowchart(self):
        """Test generating a flowchart."""
        gen = GraphvizGenerator()
        spec = DiagramSpec(
            type="flowchart",
            title="Test Flow",
            elements=["A", "B", "C"],
            flow=[("A", "B"), ("B", "C")],
        )
        
        dot_code = gen.generate(spec)
        
        assert "digraph" in dot_code
        assert '"Test Flow"' in dot_code
        assert '"A"' in dot_code
        assert '"A" -> "B"' in dot_code
    
    def test_generate_erd(self):
        """Test generating an entity-relationship diagram."""
        gen = GraphvizGenerator()
        spec = DiagramSpec(
            type="erd",
            title="Database",
            elements=["User", "Post"],
            flow=[("User", "Post")],
        )
        
        dot_code = gen.generate(spec)
        
        assert "digraph" in dot_code
        assert "rankdir=LR" in dot_code
        assert '"User" -> "Post"' in dot_code
    
    def test_generate_state_machine(self):
        """Test generating a state machine diagram."""
        gen = GraphvizGenerator()
        spec = DiagramSpec(
            type="state_machine",
            title="States",
            elements=["Idle", "Running"],
            flow=[("Idle", "Running")],
        )
        
        dot_code = gen.generate(spec)
        
        assert "shape=circle" in dot_code
        assert '"Idle" -> "Running"' in dot_code
    
    @patch('subprocess.run')
    def test_render_success(self, mock_run):
        """Test successful rendering."""
        mock_run.return_value.returncode = 0
        
        gen = GraphvizGenerator()
        result = gen.render("digraph {}", Path("/tmp/test.svg"))
        
        assert result is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_render_failure(self, mock_run):
        """Test failed rendering."""
        mock_run.side_effect = FileNotFoundError()
        
        gen = GraphvizGenerator()
        result = gen.render("digraph {}", Path("/tmp/test.svg"))
        
        assert result is False


class TestPlantUMLGenerator:
    """Test PlantUML diagram generation."""
    
    def test_generate_sequence(self):
        """Test generating a sequence diagram."""
        gen = PlantUMLGenerator()
        spec = DiagramSpec(
            type="sequence",
            title="API Call",
            elements=["Client", "Server"],
            flow=[("Client", "Server")],
        )
        
        puml_code = gen.generate(spec)
        
        assert "@startuml" in puml_code
        assert "@enduml" in puml_code
        assert "actor Client" in puml_code
        assert "Client -> Server" in puml_code
    
    def test_generate_architecture(self):
        """Test generating architecture diagram."""
        gen = PlantUMLGenerator()
        spec = DiagramSpec(
            type="architecture",
            title="System",
            elements=["Frontend", "Backend"],
            flow=[("Frontend", "Backend")],
        )
        
        puml_code = gen.generate(spec)
        
        assert "component [Frontend]" in puml_code
        assert "[Frontend] --> [Backend]" in puml_code


class TestVegaGenerator:
    """Test Vega diagram generation."""
    
    def test_generate_timeline(self):
        """Test generating a timeline."""
        gen = VegaGenerator()
        spec = DiagramSpec(
            type="timeline",
            title="Project Timeline",
            elements=["Phase 1", "Phase 2"],
        )
        
        vega_json = gen.generate(spec)
        
        assert '"title": "Project Timeline"' in vega_json
        assert '"mark": "bar"' in vega_json
    
    def test_generate_comparison(self):
        """Test generating a comparison chart."""
        gen = VegaGenerator()
        spec = DiagramSpec(
            type="comparison",
            title="Metrics",
            elements=["A", "B", "C"],
        )
        
        vega_json = gen.generate(spec)
        
        assert '"title": "Metrics"' in vega_json
        assert '"mark": "bar"' in vega_json


class TestDiagramEvaluator:
    """Test diagram quality evaluation."""
    
    @pytest.mark.asyncio
    async def test_evaluate_success(self):
        """Test successful evaluation."""
        mock_llm = Mock()
        mock_llm.invoke = AsyncMock(return_value="""
{
    "readability": 9.0,
    "consistency": 8.5,
    "intuitiveness": 8.0,
    "correctness": 9.0,
    "overall_score": 8.625,
    "feedback": "Good diagram"
}
""")
        
        evaluator = DiagramEvaluator(mock_llm)
        
        # Create a temp file to evaluate
        with patch('builtins.open', create=True):
            result = await evaluator.evaluate(
                "/tmp/test.svg",
                {"type": "flowchart"},
                {}
            )
        
        assert result.overall_score == 8.625
        assert result.passed is True
        assert result.feedback == "Good diagram"
    
    @pytest.mark.asyncio
    async def test_evaluate_failure(self):
        """Test evaluation below threshold."""
        mock_llm = Mock()
        mock_llm.invoke = AsyncMock(return_value="""
{
    "readability": 6.0,
    "consistency": 5.0,
    "intuitiveness": 6.0,
    "correctness": 7.0,
    "overall_score": 6.0,
    "feedback": "Needs improvement"
}
""")
        
        evaluator = DiagramEvaluator(mock_llm)
        
        with patch('builtins.open', create=True):
            result = await evaluator.evaluate(
                "/tmp/test.svg",
                {"type": "flowchart"},
                {}
            )
        
        assert result.overall_score == 6.0
        assert result.passed is False
    
    def test_parse_evaluation_response(self):
        """Test parsing evaluation response."""
        evaluator = DiagramEvaluator(Mock())
        
        response = """
Some text before
{
    "readability": 8.0,
    "consistency": 8.0,
    "intuitiveness": 8.0,
    "correctness": 8.0,
    "overall_score": 8.0,
    "feedback": "Good"
}
Some text after
"""
        
        result = evaluator._parse_evaluation_response(response)
        
        assert result.overall_score == 8.0
        assert result.feedback == "Good"


class TestDiagramIntelligence:
    """Test diagram intelligence orchestration."""
    
    @pytest.mark.asyncio
    async def test_process_document(self):
        """Test processing a document with diagrams."""
        mock_llm = Mock()
        mock_llm.invoke = AsyncMock(return_value="""
{
    "readability": 9.0,
    "consistency": 9.0,
    "intuitiveness": 9.0,
    "correctness": 9.0,
    "overall_score": 9.0,
    "feedback": "Excellent"
}
""")
        
        intelligence = DiagramIntelligence(mock_llm)
        
        markdown = """
[DIAGRAM]
type: flowchart
title: Test
elements:
  - A
  - B
flow:
  - A → B
[/DIAGRAM]
"""
        
        with patch.object(GraphvizGenerator, 'render', return_value=True):
            with patch('builtins.open', create=True):
                updated_md, files = await intelligence.process_document(
                    markdown,
                    Path("/tmp/diagrams")
                )
        
        assert "![Test]" in updated_md
        assert len(files) == 1
    
    @pytest.mark.asyncio
    async def test_generate_and_evaluate_iterations(self):
        """Test iterative improvement."""
        mock_llm = Mock()
        
        # First evaluation: low score
        # Second evaluation: high score
        mock_llm.invoke = AsyncMock(side_effect=[
            """{"overall_score": 6.0, "readability": 6.0, "consistency": 6.0, "intuitiveness": 6.0, "correctness": 6.0, "feedback": "Needs work"}""",
            "Improvement suggestions",
            """{"overall_score": 8.5, "readability": 8.5, "consistency": 8.5, "intuitiveness": 8.5, "correctness": 8.5, "feedback": "Much better"}""",
        ])
        
        intelligence = DiagramIntelligence(mock_llm)
        
        spec = DiagramSpec(
            type="flowchart",
            title="Test",
            elements=["A", "B"],
            flow=[("A", "B")],
        )
        
        with patch.object(GraphvizGenerator, 'render', return_value=True):
            with patch('builtins.open', create=True):
                result = await intelligence.generate_and_evaluate(
                    spec,
                    Path("/tmp/test.svg")
                )
        
        assert result == Path("/tmp/test.svg")
        # Should have called invoke 3 times (2 evaluations + 1 improvement)
        assert mock_llm.invoke.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])