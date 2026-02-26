"""Design system definitions for consistent diagram styling."""

from dataclasses import dataclass, field
from typing import Optional
import yaml
from pathlib import Path


@dataclass
class ColorPalette:
    """Color palette for diagrams."""
    
    primary: str = "#2563EB"      # Blue
    secondary: str = "#10B981"    # Green
    accent: str = "#F59E0B"       # Amber
    danger: str = "#EF4444"       # Red
    warning: str = "#F59E0B"      # Orange
    success: str = "#10B981"      # Green
    neutral_light: str = "#F3F4F6"
    neutral_dark: str = "#1F2937"
    neutral_border: str = "#E5E7EB"
    
    def get(self, name: str, default: str = "#000000") -> str:
        """Get color by name."""
        return getattr(self, name, default)


@dataclass
class Typography:
    """Typography settings for diagrams."""
    
    fonts_approved: list[DictType[str, str]] = field(default_factory=lambda: [
        {"family": "Inter", "weights": ["400", "600", "700"]},
        {"family": "Courier New", "weights": ["400"]},
    ])
    
    sizes: DictType[str, int] = field(default_factory=lambda: {
        "title": 18,
        "label": 12,
        "legend": 10,
        "annotation": 10,
    })
    
    line_height: float = 1.5


@dataclass
class Spacing:
    """Spacing rules for diagrams."""
    
    horizontal_padding: int = 20
    vertical_padding: int = 15
    element_spacing: int = 30
    line_spacing: float = 1.5
    border_width: int = 2


@dataclass
class DesignSystem:
    """Complete design system for diagram generation."""
    
    colors: ColorPalette = field(default_factory=ColorPalette)
    typography: Typography = field(default_factory=Typography)
    spacing: Spacing = field(default_factory=Spacing)
    
    # Icon library
    icon_library: str = "feather"
    approved_icons: list[str] = field(default_factory=lambda: [
        "file-text", "upload", "check", "alert", "arrow-right",
        "arrow-left", "arrow-down", "arrow-up", "settings", "users",
        "database", "server", "cloud", "lock", "unlock", "eye", "edit",
    ])
    
    # Shape definitions
    shapes: DictType[str, str] = field(default_factory=lambda: {
        "process": "rectangle",
        "start_end": "rounded_rectangle",
        "decision": "diamond",
        "data": "cylinder",
        "connection": "arrow",
    })
    
    @classmethod
    def default(cls) -> "DesignSystem":
        """Get default design system."""
        return cls()
    
    @classmethod
    def from_yaml(cls, path: Path) -> "DesignSystem":
        """Load design system from YAML file."""
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            
            colors = ColorPalette(**data.get('colors', {}))
            typography = Typography(**data.get('typography', {}))
            spacing = Spacing(**data.get('spacing', {}))
            
            return cls(
                colors=colors,
                typography=typography,
                spacing=spacing,
                icon_library=data.get('icon_library', 'feather'),
                approved_icons=data.get('approved_icons', []),
                shapes=data.get('shapes', {}),
            )
        except Exception as e:
            print(f"Failed to load design system: {e}, using defaults")
            return cls.default()
    
    def to_graphviz_attrs(self) -> DictType[str, str]:
        """Convert design system to Graphviz attributes."""
        return {
            'bgcolor': self.colors.neutral_light,
            'fontname': 'Inter',
            'fontsize': str(self.typography.sizes['label']),
            'pad': str(self.spacing.horizontal_padding / 72),  # Convert pixels to points
        }
    
    def to_css(self) -> str:
        """Generate CSS for SVG diagrams."""
        return f"""
        :root {{
            --color-primary: {self.colors.primary};
            --color-secondary: {self.colors.secondary};
            --color-accent: {self.colors.accent};
            --color-danger: {self.colors.danger};
            --color-neutral-light: {self.colors.neutral_light};
            --color-neutral-dark: {self.colors.neutral_dark};
            --font-family: '{self.typography.fonts_approved[0]["family"]}';
            --font-size-title: {self.typography.sizes['title']}px;
            --font-size-label: {self.typography.sizes['label']}px;
            --spacing-h: {self.spacing.horizontal_padding}px;
            --spacing-v: {self.spacing.vertical_padding}px;
        }}
        
        .diagram-title {{
            font-size: var(--font-size-title);
            font-weight: 700;
            fill: var(--color-neutral-dark);
            font-family: var(--font-family);
        }}
        
        .diagram-label {{
            font-size: var(--font-size-label);
            fill: var(--color-neutral-dark);
            font-family: var(--font-family);
        }}
        
        .diagram-box {{
            fill: white;
            stroke: var(--color-primary);
            stroke-width: 2;
        }}
        
        .diagram-arrow {{
            stroke: var(--color-neutral-dark);
            stroke-width: 2;
            fill: none;
            marker-end: url(#arrow);
        }}
        """
