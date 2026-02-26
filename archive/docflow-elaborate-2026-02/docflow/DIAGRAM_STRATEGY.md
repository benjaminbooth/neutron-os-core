# DocFlow Diagram Intelligence System

**Problem:** Manual diagram creation is the bottleneck in documentation  
**Solution:** AI-powered diagram generation with automatic quality evaluation  
**Impact:** Beautiful, consistent, readable diagrams with zero manual SVG editing

---

## The Problem

Current state:
- ❌ ASCII art renders as gibberish in Word
- ❌ Mermaid is limited and inconsistently styled
- ❌ Manual Figma/Lucidchart work takes 20% of documentation time
- ❌ No design consistency across diagrams
- ❌ Hard to maintain as requirements change

**Result:** Beautiful diagrams are a "nice to have" → they get skipped → docs become hard to understand

---

## Proposed Solution: Diagram Intelligence Agent

```
[Markdown with diagram markup]
           ↓
[Diagram Specification Extractor]
           ↓
[Generate Diagram Candidates] ← Multiple backends (Graphviz, PlantUML, Vega, SVG)
           ↓
[Quality Evaluation Agent] ← Claude + design system rules
           ↓
[Score candidates] (readability, style, intuitiveness)
           ↓
[Iterate] (if score < threshold)
           ↓
[GORGEOUS Diagram] ← Embedded in .docx
```

---

## Architecture

### 1. Diagram Markup in Markdown

Define diagrams with structured markup (not ASCII):

```markdown
## System Architecture

[DIAGRAM]
type: flowchart
title: Document Processing Pipeline
description: |
  Shows how documents flow through DocFlow:
  - Git push triggers publish
  - Converts markdown to docx
  - Uploads to OneDrive
  - Extracts feedback
elements:
  - Git Commit → input
  - Markdown File → input
  - Convert to DOCX → process
  - Upload to OneDrive → output
  - Extract Comments → process
  - Incorporate Feedback → process
flow:
  - Git Commit → Convert to DOCX
  - Markdown File → Convert to DOCX
  - Convert to DOCX → Upload to OneDrive
  - Upload to OneDrive → Extract Comments
  - Extract Comments → Incorporate Feedback
[/DIAGRAM]
```

### 2. Diagram Types Supported

```yaml
diagram_types:
  
  # Process/Flow Diagrams
  flowchart:
    backend: graphviz
    use_cases: 
      - Document processing pipeline
      - Review workflow
      - CI/CD pipeline
    style_elements:
      - Start/end (ovals)
      - Processes (rectangles)
      - Decisions (diamonds)
      - Flow arrows
  
  # Architecture Diagrams
  architecture:
    backend: custom_svg
    use_cases:
      - System component relationships
      - Data flow between services
      - Network topology
    style_elements:
      - Boxes for components
      - Arrows for connections
      - Layered layout
  
  # Sequence Diagrams
  sequence:
    backend: plantuml
    use_cases:
      - User interactions
      - API calls
      - Review approval workflow
    style_elements:
      - Actors (stick figures or boxes)
      - Messages (arrows)
      - Lifelines
  
  # Data Diagrams
  entity_relationship:
    backend: graphviz
    use_cases:
      - Database schema
      - Document state model
      - Configuration structure
    style_elements:
      - Entities (boxes)
      - Relationships (arrows)
      - Cardinality notation
  
  # Timeline/Gantt
  timeline:
    backend: vega
    use_cases:
      - Project roadmap
      - Review period schedule
      - Version releases
    style_elements:
      - Bars for durations
      - Milestones
      - Dependencies
  
  # State Machine
  state_machine:
    backend: graphviz
    use_cases:
      - Document lifecycle
      - Review states
      - Autonomy levels
    style_elements:
      - States (circles/boxes)
      - Transitions (arrows)
      - Labels on transitions
  
  # Table/Comparison
  comparison:
    backend: vega
    use_cases:
      - Feature comparison
      - Provider matrix
      - Configuration options
    style_elements:
      - Columns for categories
      - Rows for items
      - Color-coded cells
```

### 3. Quality Evaluation Framework

**Readability Scoring:**
```
- Font size: ≥10pt readable
- Contrast: WCAG AA compliant
- Text density: <30 words per diagram
- Element size: No crowding
- Arrow clarity: Clear flow direction
Score: 0-10
```

**Consistency Scoring:**
```
- Colors match palette
- Fonts from approved set
- Spacing consistent
- Border widths uniform
- Icon style matches
Score: 0-10
```

**Intuitiveness Scoring:**
```
- Labels are clear and descriptive
- Visual hierarchy matches logical hierarchy
- Metaphors are consistent
- No unexpected element placement
- Flow direction (left→right or top→bottom)
Score: 0-10
```

**Correctness Scoring:**
```
- All specified elements present
- Flow matches specification
- No missing connections
- Cardinality correct (for ERD)
Score: 0-10
```

**Combined Score = (Readability + Consistency + Intuitiveness + Correctness) / 4**  
**Threshold = 8.0/10 for approval**

### 4. Diagram Backends

#### Option A: Graphviz (Flowcharts, ERD, State Machines)
```python
class GraphvizDiagramGenerator:
    """Generate high-quality diagrams using Graphviz."""
    
    def generate_flowchart(self, elements: list, flow: list, **style) -> bytes:
        """Generate flowchart, return SVG/PDF bytes."""
        pass
    
    def generate_state_machine(self, states: list, transitions: list) -> bytes:
        """Generate state diagram."""
        pass
```

**Pros:**
- Excellent for technical diagrams
- Consistent output
- SVG/PDF export
- Highly customizable styling

**Cons:**
- Requires Graphviz installed
- DSL syntax

#### Option B: PlantUML (Sequence, Use Cases, Component)
```python
class PlantUMLGenerator:
    """Generate diagrams using PlantUML."""
    
    def generate_sequence(self, interactions: list) -> bytes:
        """Generate sequence diagram."""
        pass
    
    def generate_component(self, components: list, relationships: list) -> bytes:
        """Generate component diagram."""
        pass
```

**Pros:**
- Great for UML diagrams
- Simple syntax
- Easy to version in Git
- SVG output

**Cons:**
- Limited styling control
- Layout sometimes awkward

#### Option C: Vega (Data Visualization)
```python
class VegaGenerator:
    """Generate data visualizations using Vega."""
    
    def generate_timeline(self, events: list) -> bytes:
        """Generate timeline."""
        pass
    
    def generate_comparison_table(self, data: list) -> bytes:
        """Generate comparison visualization."""
        pass
```

**Pros:**
- Beautiful data viz
- Interactive (in HTML)
- Responsive design
- Theme support

**Cons:**
- JSON spec is verbose
- Less ideal for flowcharts

#### Option D: Custom SVG Generation
```python
class CustomSVGGenerator:
    """Generate SVG directly for custom diagram types."""
    
    def generate_architecture(self, components: list, layout: str) -> bytes:
        """Generate custom architecture diagram."""
        pass
```

**Pros:**
- Total control
- Perfect styling
- Embeddable in DOCX

**Cons:**
- More code
- More complex

### 5. Diagram Evaluation Agent

**Workflow:**

```python
class DiagramEvaluator:
    """Evaluate diagrams using Claude for quality feedback."""
    
    def evaluate(self, diagram_svg: bytes, spec: dict, design_system: dict) -> dict:
        """
        Evaluate diagram quality.
        
        Returns:
        {
            'readability_score': 8.5,
            'consistency_score': 9.0,
            'intuitiveness_score': 7.5,
            'correctness_score': 10.0,
            'overall_score': 8.75,
            'issues': [
                'Font size in legend is too small (8pt, should be ≥10pt)',
                'Arrow labels missing on feedback loop',
                'Color #FF0000 doesn't match approved palette'
            ],
            'suggestions': [
                'Add legend for colors',
                'Clarify "Publish" step - is this automatic or manual?',
                'Consider grouping "Review" steps together'
            ],
            'passes_quality_gate': True
        }
        """
        pass
    
    def suggest_improvements(self, diagram_svg: bytes, issues: list) -> str:
        """
        Use Claude to suggest specific improvements.
        
        Returns: Updated SVG or modified spec for regeneration.
        """
        pass
```

**Evaluation Process:**

1. **Screenshot Analysis** — Claude analyzes rendered diagram
   - Readability (can a human understand it in 10 seconds?)
   - Font sizes and contrast
   - Visual hierarchy
   - Clutter/whitespace balance

2. **Specification Validation** — Check against design system
   - Colors used match palette
   - Font families approved
   - Spacing consistent
   - Icons from approved set

3. **Correctness Check** — Verify against spec
   - All elements present
   - All connections made
   - No dangling nodes

4. **Intuitiveness Assessment** — LLM judges ease of understanding
   - Are labels clear?
   - Is flow direction obvious?
   - Would a newcomer understand this?
   - Are metaphors consistent?

### 6. Design System (Built-in)

```yaml
design_system:
  color_palette:
    primary: "#2563EB"      # Blue
    secondary: "#10B981"    # Green
    accent: "#F59E0B"       # Amber
    danger: "#EF4444"       # Red
    neutral_light: "#F3F4F6"
    neutral_dark: "#1F2937"
  
  typography:
    fonts_approved:
      - family: "Inter"
        weights: [400, 600, 700]
      - family: "Courier New"  # For code
    sizes:
      title: 18px
      label: 12px
      legend: 10px
      annotation: 10px
  
  spacing:
    horizontal_padding: 20px
    vertical_padding: 15px
    element_spacing: 30px
    line_spacing: 1.5
  
  icons:
    library: "feather"
    approved_icons:
      - file-text
      - upload
      - check
      - alert
      - arrow-right
  
  shapes:
    process: rectangle
    start_end: rounded_rectangle
    decision: diamond
    data: cylinder
    connection: arrow
```

### 7. Integration with DocFlow

```python
class DiagramIntelligence:
    """Diagram generation and evaluation subsystem."""
    
    def __init__(self, llm_provider: LLMProvider, design_system: dict):
        self.llm = llm_provider
        self.design_system = design_system
        self.graphviz_gen = GraphvizDiagramGenerator(design_system)
        self.plantuml_gen = PlantUMLGenerator(design_system)
        self.vega_gen = VegaGenerator(design_system)
        self.evaluator = DiagramEvaluator(llm_provider, design_system)
    
    def process_document(self, markdown: str) -> tuple[str, list[dict]]:
        """
        Extract diagrams from markdown, generate, evaluate, iterate.
        
        Returns:
            (updated_markdown, diagram_records)
        """
        diagrams = self.extract_diagram_specs(markdown)
        
        results = []
        for diagram_spec in diagrams:
            diagram = self.generate_and_evaluate(diagram_spec)
            results.append(diagram)
            
            # Replace placeholder with reference to generated diagram
            markdown = markdown.replace(
                f"[DIAGRAM]{diagram_spec}[/DIAGRAM]",
                f"![{diagram['title']}]({diagram['path']})"
            )
        
        return markdown, results
    
    def generate_and_evaluate(self, spec: dict) -> dict:
        """
        Generate diagram and evaluate quality, iterating until acceptable.
        
        Returns:
            {
                'title': '...',
                'path': 'diagrams/architecture.svg',
                'iterations': 2,
                'final_score': 8.9,
                'feedback': '...'
            }
        """
        backend = self.choose_backend(spec['type'])
        iterations = 0
        max_iterations = 3
        
        while iterations < max_iterations:
            # Generate candidate
            svg = backend.generate(**spec)
            iterations += 1
            
            # Evaluate
            evaluation = self.evaluator.evaluate(svg, spec, self.design_system)
            
            # Check if acceptable
            if evaluation['overall_score'] >= 8.0:
                return {
                    'title': spec.get('title', 'Diagram'),
                    'path': self.save_diagram(svg, spec),
                    'iterations': iterations,
                    'final_score': evaluation['overall_score'],
                    'feedback': evaluation['suggestions'],
                }
            
            # Not acceptable, improve and retry
            spec = self.apply_improvements(spec, evaluation['issues'])
        
        # Return best effort after max iterations
        return {
            'title': spec.get('title', 'Diagram'),
            'path': self.save_diagram(svg, spec),
            'iterations': iterations,
            'final_score': evaluation['overall_score'],
            'warning': f"Score {evaluation['overall_score']} below threshold 8.0",
        }
```

---

## Implementation Plan

### Phase 1: MVP (Week 1)
- [ ] Create `diagrams/` module
- [ ] Implement Graphviz backend
- [ ] Basic quality evaluation (readability, correctness)
- [ ] Diagram spec parser from markdown
- [ ] Integration with document publishing

### Phase 2: Expansion (Week 2)
- [ ] Add PlantUML backend
- [ ] Add Vega backend
- [ ] Full design system enforcement
- [ ] Iterative improvement loop
- [ ] Caching (regenerate only if spec changes)

### Phase 3: Polish (Week 3)
- [ ] Built-in design system templates
- [ ] Example diagrams for each type
- [ ] Performance optimization
- [ ] Test suite
- [ ] Documentation

---

## Benefits

✅ **Zero manual diagram editing** — Automatic generation and improvement  
✅ **Beautiful output** — SVG/PDF quality, not ASCII  
✅ **Consistent styling** — All diagrams follow design system  
✅ **Readable by default** — Evaluated for readability before inclusion  
✅ **Maintainable** — Change spec, diagram regenerates  
✅ **Versionable** — Diagram specs in Git, not image files  
✅ **Scalable** — Generate 50+ diagrams automatically  

---

## Example: Before vs After

### Before (Manual/ASCII)

```
┌─────────────────────────────────────────────────────────┐
│                   GitHub Commit                         │
│                   (git push)                            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │  Convert Markdown → DOCX           │
        │  (python-docx)                     │
        └────────────────┬───────────────────┘
                         │
         ┌───────────────┴───────────────────┐
         │                                   │
         ▼                                   ▼
    ┌─────────┐  ┌──────────────────────────────┐
    │  Local  │  │ Upload to OneDrive/Storage   │
    │ Preview │  │ (Create share link)          │
    └─────────┘  └────────┬─────────────────────┘
                          │
                          ▼
                 ┌────────────────────┐
                 │ Send Reviews to    │
                 │ Stakeholders       │
                 └────────────────────┘
```

**Problems:** Ugly, hard to read, doesn't scale, can't embed styles

### After (Diagram Intelligence)

```
[DIAGRAM]
type: flowchart
title: Document Publishing Pipeline
elements:
  - Git Commit → "GitHub\nPush"
  - Markdown → "Source Files"
  - Convert → "Convert MD→DOCX\n(python-docx)"
  - Local → "Preview Locally"
  - Upload → "Upload to OneDrive\nCreate Share Link"
  - Notify → "Notify Reviewers"
flow:
  - Git Commit → Convert
  - Markdown → Convert
  - Convert → Local
  - Convert → Upload
  - Upload → Notify
[/DIAGRAM]
```

**Output:** Beautiful SVG, readable, styled, properly spaced, can be PDF'd

---

## Questions for Ben

1. **Priority**: Is this worth doing NOW before LangGraph? (It's a bigger blocker)
2. **Scope**: Should we support all 5 diagram types or start with flowcharts only?
3. **Design System**: Should it be customizable per repo or global?
4. **Automation**: Should diagrams regenerate on every doc publish or only if spec changes?

---

## References

- **Graphviz** — Best for flowcharts/ER/state: https://graphviz.org/
- **PlantUML** — Best for UML: https://plantuml.com/
- **Vega** — Best for data: https://vega.github.io/vega/
- **Claude for Evaluation** — Using vision + structured output for quality gates
- **Design Systems** — https://www.designsystems.com/

---

**This is the hidden lever that makes docs SHINE. Gorgeous diagrams are what make people actually READ your documentation.**
