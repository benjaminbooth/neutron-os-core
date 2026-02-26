"""Parse diagram specifications from markdown."""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class DiagramSpec:
    """Diagram specification extracted from markdown."""
    
    type: str  # flowchart, architecture, sequence, erd, timeline, state_machine
    title: str
    description: str = ""
    elements: list[str] = None
    flow: list[tuple[str, str]] = None  # (from, to) pairs
    config: dict = None
    
    def __post_init__(self):
        """Initialize defaults."""
        if self.elements is None:
            self.elements = []
        if self.flow is None:
            self.flow = []
        if self.config is None:
            self.config = {}


class DiagramSpecParser:
    """Extract and parse diagram specifications from markdown."""
    
    # Regex to find [DIAGRAM]...[/DIAGRAM] blocks
    DIAGRAM_BLOCK_PATTERN = r'\[DIAGRAM\](.*?)\[/DIAGRAM\]'
    
    # Regex to parse YAML-like format
    FIELD_PATTERN = r'^(\w+):\s*(.+)$'
    LIST_PATTERN = r'^\s*-\s+(.+)$'
    FLOW_PATTERN = r'^(\w+)\s*→\s*(\w+)$'
    
    @classmethod
    def extract_diagrams(cls, markdown: str) -> ListType[DiagramSpec]:
        """Extract all diagram specifications from markdown.
        
        Args:
            markdown: Markdown content
        
        Returns:
            List of DiagramSpec objects
        """
        specs = []
        
        for match in re.finditer(cls.DIAGRAM_BLOCK_PATTERN, markdown, re.DOTALL):
            block = match.group(1).strip()
            spec = cls.parse_block(block)
            if spec:
                specs.append(spec)
        
        return specs
    
    @classmethod
    def parse_block(cls, block: str) -> Optional[DiagramSpec]:
        """Parse a single diagram specification block.
        
        Args:
            block: Content between [DIAGRAM] tags
        
        Returns:
            DiagramSpec or None if invalid
        """
        lines = block.split('\n')
        spec_dict = {}
        current_list = None
        current_list_name = None
        
        for line in lines:
            line = line.rstrip()
            
            # Check for field assignment
            field_match = re.match(cls.FIELD_PATTERN, line)
            if field_match:
                current_list_name = field_match.group(1)
                value = field_match.group(2).strip()
                
                if current_list_name in ('elements', 'flow'):
                    # Start a list
                    current_list = []
                    spec_dict[current_list_name] = current_list
                    
                    # If value is on same line, add it
                    if value:
                        current_list.append(value)
                else:
                    # Single value field
                    spec_dict[current_list_name] = value
                    current_list = None
            
            # Check for list item
            elif current_list is not None and line.strip().startswith('-'):
                list_match = re.match(self.LIST_PATTERN, line)
                if list_match:
                    current_list.append(list_match.group(1))
        
        # Create DiagramSpec
        try:
            spec = DiagramSpec(
                type=spec_dict.get('type', 'flowchart'),
                title=spec_dict.get('title', 'Untitled Diagram'),
                description=spec_dict.get('description', ''),
                elements=spec_dict.get('elements', []),
                flow=cls._parse_flow(spec_dict.get('flow', [])),
                config=spec_dict.get('config', {}),
            )
            return spec
        except Exception as e:
            # Invalid spec
            return None
    
    @classmethod
    def _parse_flow(cls, flow_list: list) -> ListType[tuple[str, str]]:
        """Parse flow specification into (from, to) tuples.
        
        Args:
            flow_list: List of strings like "A → B"
        
        Returns:
            List of (from, to) tuples
        """
        flows = []
        for item in flow_list:
            # Handle "A → B" or "A->B" format
            if '→' in item:
                parts = item.split('→')
            elif '->' in item:
                parts = item.split('->')
            else:
                continue
            
            if len(parts) == 2:
                from_node = parts[0].strip()
                to_node = parts[1].strip()
                flows.append((from_node, to_node))
        
        return flows
    
    @classmethod
    def replace_diagram_in_markdown(cls, markdown: str, diagram_spec: DiagramSpec,
                                   diagram_path: str) -> str:
        """Replace diagram specification with markdown image reference.
        
        Args:
            markdown: Original markdown
            diagram_spec: The diagram specification
            diagram_path: Path to generated diagram (relative)
        
        Returns:
            Updated markdown with image reference
        """
        # Find the matching [DIAGRAM]...[/DIAGRAM] block
        pattern = (
            r'\[DIAGRAM\].*?type:\s*' + re.escape(diagram_spec.type) +
            r'.*?title:\s*' + re.escape(diagram_spec.title) +
            r'.*?\[/DIAGRAM\]'
        )
        
        replacement = f'![{diagram_spec.title}]({diagram_path})'
        
        return re.sub(pattern, replacement, markdown, flags=re.DOTALL)


# Example usage/testing
if __name__ == "__main__":
    test_markdown = """
# Architecture

[DIAGRAM]
type: flowchart
title: Document Pipeline
description: How documents flow through DocFlow
elements:
  - Git Commit
  - Convert to DOCX
  - Upload
  - Review
flow:
  - Git Commit → Convert to DOCX
  - Convert to DOCX → Upload
  - Upload → Review
[/DIAGRAM]

Some description text here.
"""
    
    diagrams = DiagramSpecParser.extract_diagrams(test_markdown)
    for diagram in diagrams:
        print(f"Found: {diagram.title} ({diagram.type})")
        print(f"  Elements: {diagram.elements}")
        print(f"  Flows: {diagram.flow}")
