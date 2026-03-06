"""
Neutron OS Mermaid Diagram Standards
====================================

These standards ensure consistency, readability, and proper rendering across all
mermaid diagrams used in Neutron OS documentation. All diagrams must follow these
rules before being merged into documentation.

Version: 1.0
Last Updated: 2026-01-22
Applicable To: All .md files under docs/ directory
"""

MERMAID_STANDARDS = {
    "node_text_color": {
        "rule": "CRITICAL - Every styled node MUST have explicit text color",
        "light_fills": {
            "colors": ["#e1f5fe", "#e3f2fd", "#e8f5e9", "#fce4ec", "#f3e5f5", 
                      "#fff3e0", "#e0f2f1", "#f5f5f5", "#c8e6c9", "#ffecb3", 
                      "#fff9c4", "#f1f8e9", "#ede7f6"],
            "text_color": "#000000",
            "example": "style NodeName fill:#e3f2fd,color:#000000"
        },
        "dark_fills": {
            "colors": ["#1976d2", "#388e3c", "#f57c00", "#7b1fa2", "#c2185b",
                      "#0d47a1", "#1b5e20", "#e65100", "#4a148c", "#880e4f",
                      "#263238", "#1565c0", "#00897b", "#424242", "#bf360c",
                      "#455a64"],
            "text_color": "#ffffff",
            "example": "style NodeName fill:#1565c0,color:#ffffff"
        }
    },
    
    "arrow_colors": {
        "rule": "All diagrams MUST have arrow styling for visibility",
        "standard": "linkStyle default stroke:#777777,stroke-width:3px",
        "rationale": "Grey (#777777) with 3px width visible on both light and dark backgrounds"
    },
    
    "subgraph_titles": {
        "rule": "CRITICAL - Subgraph titles must be SHORT and single-line",
        "max_length": 35,
        "constraints": [
            "Keep titles under 35 characters",
            "Never wrap titles across multiple lines",
            "Never use <br/> in subgraph labels",
            "Avoid parenthetical details in titles",
            "Emoji OK if it fits under 35 chars"
        ],
        "bad_examples": [
            'subgraph Storage["Lakehouse (Iceberg + DuckDB)"]  # Too long, will wrap',
            'subgraph Server["NEUTRON OS MCP SERVER<br/>(Python + mcp SDK)"]  # <br/> ignored',
            'subgraph Critical["⚠️ Critical Items (Require Immediate Action)"]  # Too long'
        ],
        "good_examples": [
            'subgraph Storage["Lakehouse"]',
            'subgraph Server["NEUTRON OS MCP Server"]',
            'subgraph Critical["Critical Items"]'
        ],
        "problem": "When titles wrap, the bottom line of text gets obscured by child/nested boxes"
    },
    
    "ascii_art": {
        "rule": "NO ASCII art boxes - use proper mermaid diagrams instead",
        "bad": "┌─────┐\n│ Box │\n└─────┘",
        "good": "Use flowchart nodes, subgraphs, or markdown tables"
    },
    
    "testing_checklist": [
        "All nodes with fill colors have explicit color property",
        "All diagrams have linkStyle with proper grey arrows",
        "All subgraph titles are <= 35 characters",
        "No <br/> tags in subgraph labels",
        "Preview in VS Code light and dark themes",
        "No ASCII art boxes anywhere"
    ]
}

# List of files that are known to have been fixed
KNOWN_COMPLIANT_FILES = {
    "prd/experiment-manager-prd.md": "2026-01-22",
    "prd/scheduling-system-prd.md": "2026-01-22",
    "prd/compliance-tracking-prd.md": "2026-01-22",
    "prd/data-platform-prd.md": "2026-01-22",
    "prd/reactor-ops-log-prd.md": "2026-01-22",
    "prd/analytics-dashboards-prd.md": "2026-01-22",
    "prd/neutron-os-executive-prd.md": "2026-01-22",
    "prd/medical-isotope-prd.md": "2026-01-22",
    "specs/current-system-mermaid.md": "2026-01-22",
    "adr/006-mcp-server-agentic-access.md": "2026-01-22",
    "specs/neutron-os-master-tech-spec.md": "2026-01-22",
}
