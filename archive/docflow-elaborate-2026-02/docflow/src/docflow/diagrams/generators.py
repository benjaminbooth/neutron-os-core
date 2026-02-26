"""Diagram generators for multiple output formats."""

from abc import ABC, abstractmethod
from typing import Optional
import subprocess
import tempfile
from pathlib import Path

from .parser import DiagramSpec
from .design_system import DesignSystem


class DiagramGenerator(ABC):
    """Abstract base class for diagram generators."""
    
    def __init__(self, design_system: Optional[DesignSystem] = None):
        """Initialize generator.
        
        Args:
            design_system: Design system for styling (uses default if None)
        """
        self.design_system = design_system or DesignSystem.default()
    
    @abstractmethod
    def generate(self, spec: DiagramSpec) -> str:
        """Generate diagram in format-specific code.
        
        Args:
            spec: Diagram specification
        
        Returns:
            Format-specific diagram code
        """
        pass
    
    @abstractmethod
    def render(self, diagram_code: str, output_path: Path) -> bool:
        """Render diagram code to file.
        
        Args:
            diagram_code: Format-specific code
            output_path: Where to save rendered diagram
        
        Returns:
            True if successful
        """
        pass


class GraphvizGenerator(DiagramGenerator):
    """Generate diagrams using Graphviz (DOT format)."""
    
    def generate(self, spec: DiagramSpec) -> str:
        """Generate Graphviz DOT code.
        
        Args:
            spec: Diagram specification
        
        Returns:
            DOT language code
        """
        if spec.type == "flowchart":
            return self._generate_flowchart(spec)
        elif spec.type == "erd":
            return self._generate_erd(spec)
        elif spec.type == "state_machine":
            return self._generate_state_machine(spec)
        else:
            return self._generate_generic(spec)
    
    def _generate_flowchart(self, spec: DiagramSpec) -> str:
        """Generate a flowchart."""
        lines = [
            "digraph {",
            '  rankdir=TB;',
            f'  label="{spec.title}";',
            '  node [shape=box, style=filled, fillcolor=white, '
            f'color="{self.design_system.colors.primary}", '
            f'fontname="Inter"];',
            f'  edge [color="{self.design_system.colors.neutral_dark}"];',
        ]
        
        # Add elements as nodes
        for element in spec.elements:
            lines.append(f'  "{element}" [label="{element}"];')
        
        # Add flow as edges
        for from_node, to_node in spec.flow:
            lines.append(f'  "{from_node}" -> "{to_node}";')
        
        lines.append("}")
        return "\n".join(lines)
    
    def _generate_erd(self, spec: DiagramSpec) -> str:
        """Generate an entity-relationship diagram."""
        lines = [
            "digraph {",
            '  rankdir=LR;',
            f'  label="{spec.title}";',
            '  node [shape=box, style=filled, fillcolor=white, '
            f'color="{self.design_system.colors.secondary}"];',
        ]
        
        for element in spec.elements:
            lines.append(f'  "{element}";')
        
        for from_node, to_node in spec.flow:
            lines.append(f'  "{from_node}" -> "{to_node}" '
                        '[arrowhead=crow, arrowtail=crow];')
        
        lines.append("}")
        return "\n".join(lines)
    
    def _generate_state_machine(self, spec: DiagramSpec) -> str:
        """Generate a state machine diagram."""
        lines = [
            "digraph {",
            '  rankdir=LR;',
            f'  label="{spec.title}";',
            '  node [shape=circle, style=filled, fillcolor=white, '
            f'color="{self.design_system.colors.accent}"];',
        ]
        
        for element in spec.elements:
            lines.append(f'  "{element}";')
        
        for from_node, to_node in spec.flow:
            lines.append(f'  "{from_node}" -> "{to_node}";')
        
        lines.append("}")
        return "\n".join(lines)
    
    def _generate_generic(self, spec: DiagramSpec) -> str:
        """Generate a generic diagram."""
        lines = [
            "digraph {",
            f'  label="{spec.title}";',
        ]
        
        for element in spec.elements:
            lines.append(f'  "{element}";')
        
        for from_node, to_node in spec.flow:
            lines.append(f'  "{from_node}" -> "{to_node}";')
        
        lines.append("}")
        return "\n".join(lines)
    
    def render(self, diagram_code: str, output_path: Path) -> bool:
        """Render DOT code to SVG using Graphviz.
        
        Args:
            diagram_code: DOT language code
            output_path: Output file path
        
        Returns:
            True if successful
        """
        try:
            # Create temporary file for dot code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as f:
                f.write(diagram_code)
                temp_path = f.name
            
            # Render using dot command
            subprocess.run(
                ['dot', '-Tsvg', temp_path, '-o', str(output_path)],
                check=True,
                capture_output=True,
            )
            
            # Clean up temp file
            Path(temp_path).unlink()
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"Graphviz render failed: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            print("Graphviz 'dot' command not found. Install graphviz package.")
            return False


class PlantUMLGenerator(DiagramGenerator):
    """Generate diagrams using PlantUML."""
    
    def generate(self, spec: DiagramSpec) -> str:
        """Generate PlantUML code.
        
        Args:
            spec: Diagram specification
        
        Returns:
            PlantUML code
        """
        if spec.type == "sequence":
            return self._generate_sequence(spec)
        elif spec.type == "flowchart":
            return self._generate_flowchart(spec)
        elif spec.type == "architecture":
            return self._generate_architecture(spec)
        else:
            return self._generate_generic(spec)
    
    def _generate_flowchart(self, spec: DiagramSpec) -> str:
        """Generate a PlantUML flowchart."""
        lines = ["@startuml"]
        lines.append(f"title {spec.title}")
        
        if spec.description:
            lines.append(f"note top : {spec.description}")
        
        for element in spec.elements:
            lines.append(f":{element};")
        
        for from_node, to_node in spec.flow:
            lines.append(f"--> {to_node} : ;")
        
        lines.append("@enduml")
        return "\n".join(lines)
    
    def _generate_sequence(self, spec: DiagramSpec) -> str:
        """Generate a sequence diagram."""
        lines = ["@startuml"]
        lines.append(f"title {spec.title}")
        
        # Elements are actors/participants
        for element in spec.elements:
            lines.append(f"actor {element}")
        
        # Flow is interaction
        for from_node, to_node in spec.flow:
            lines.append(f"{from_node} -> {to_node} : message")
        
        lines.append("@enduml")
        return "\n".join(lines)
    
    def _generate_architecture(self, spec: DiagramSpec) -> str:
        """Generate architecture diagram (as component diagram)."""
        lines = ["@startuml"]
        lines.append(f"title {spec.title}")
        
        for element in spec.elements:
            lines.append(f"component [{element}]")
        
        for from_node, to_node in spec.flow:
            lines.append(f"[{from_node}] --> [{to_node}]")
        
        lines.append("@enduml")
        return "\n".join(lines)
    
    def _generate_generic(self, spec: DiagramSpec) -> str:
        """Generate generic PlantUML."""
        lines = ["@startuml"]
        lines.append(f"title {spec.title}")
        lines.append("@enduml")
        return "\n".join(lines)
    
    def render(self, diagram_code: str, output_path: Path) -> bool:
        """Render PlantUML to SVG.
        
        Args:
            diagram_code: PlantUML code
            output_path: Output file path
        
        Returns:
            True if successful
        """
        try:
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.puml', delete=False) as f:
                f.write(diagram_code)
                temp_path = f.name
            
            # Call plantuml
            subprocess.run(
                ['plantuml', '-tsvg', '-o', str(output_path.parent), temp_path],
                check=True,
                capture_output=True,
            )
            
            # Clean up
            Path(temp_path).unlink()
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"PlantUML render failed: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            print("PlantUML not found. Install plantuml package.")
            return False


class VegaGenerator(DiagramGenerator):
    """Generate data visualizations using Vega-Lite."""
    
    def generate(self, spec: DiagramSpec) -> str:
        """Generate Vega-Lite JSON.
        
        Args:
            spec: Diagram specification
        
        Returns:
            Vega-Lite JSON code
        """
        import json
        
        base = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": spec.title,
            "description": spec.description,
        }
        
        if spec.type == "timeline":
            base.update(self._generate_timeline(spec))
        elif spec.type == "comparison":
            base.update(self._generate_comparison(spec))
        else:
            base.update({"mark": "point", "data": {"values": []}})
        
        return json.dumps(base, indent=2)
    
    def _generate_timeline(self, spec: DiagramSpec) -> dict:
        """Generate timeline visualization."""
        return {
            "mark": "bar",
            "data": {
                "values": [
                    {"name": elem, "start": i*100, "duration": 80}
                    for i, elem in enumerate(spec.elements)
                ]
            },
            "encoding": {
                "x": {"field": "start", "type": "quantitative"},
                "x2": {"field": "duration"},
                "y": {"field": "name", "type": "nominal"},
            }
        }
    
    def _generate_comparison(self, spec: DiagramSpec) -> dict:
        """Generate comparison visualization."""
        return {
            "mark": "bar",
            "data": {
                "values": [
                    {"name": elem, "value": idx}
                    for idx, elem in enumerate(spec.elements)
                ]
            },
            "encoding": {
                "x": {"field": "name", "type": "nominal"},
                "y": {"field": "value", "type": "quantitative"},
                "color": {"field": "name", "type": "nominal"},
            }
        }
    
    def render(self, diagram_code: str, output_path: Path) -> bool:
        """Render Vega-Lite to SVG (requires vega-cli).
        
        Args:
            diagram_code: Vega-Lite JSON
            output_path: Output file path
        
        Returns:
            True if successful
        """
        try:
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.vg.json', delete=False) as f:
                f.write(diagram_code)
                temp_path = f.name
            
            # Call vega render
            subprocess.run(
                ['vg2svg', temp_path, str(output_path)],
                check=True,
                capture_output=True,
            )
            
            # Clean up
            Path(temp_path).unlink()
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"Vega render failed: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            print("Vega command-line tools not found. Install vega-cli package.")
            return False
