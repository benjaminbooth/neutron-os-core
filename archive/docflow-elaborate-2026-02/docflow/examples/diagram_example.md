# DocFlow Diagram Examples

This document demonstrates the Diagram Intelligence System with real examples.

## Example 1: Document Publishing Pipeline

[DIAGRAM]
type: flowchart
title: Document Publishing Pipeline
description: How documents flow through the DocFlow system from commit to publication
elements:
  - Git Commit
  - Parse Markdown
  - Generate DOCX
  - Upload to OneDrive
  - Request Review
  - Review Approved
  - Publish
  - Archive Old
flow:
  - Git Commit → Parse Markdown
  - Parse Markdown → Generate DOCX
  - Generate DOCX → Upload to OneDrive
  - Upload to OneDrive → Request Review
  - Request Review → Review Approved
  - Review Approved → Publish
  - Publish → Archive Old
[/DIAGRAM]

This diagram shows the main workflow. Documents start with a git commit, get converted to DOCX, uploaded to OneDrive for review, and finally published.

## Example 2: System Architecture

[DIAGRAM]
type: architecture
title: DocFlow System Architecture
description: Components and their relationships in the DocFlow system
elements:
  - CLI Interface
  - Document Processor
  - Storage Provider
  - LLM Provider
  - Notification Service
  - Git Integration
flow:
  - CLI Interface → Document Processor
  - Document Processor → Storage Provider
  - Document Processor → LLM Provider
  - LLM Provider → Notification Service
  - Document Processor → Git Integration
[/DIAGRAM]

The architecture shows how the CLI connects to core processors, which orchestrate providers and external services.

## Example 3: Review State Machine

[DIAGRAM]
type: state_machine
title: Document Review States
description: State transitions during document review cycle
elements:
  - Draft
  - Review Requested
  - Changes Requested
  - Approved
  - Published
flow:
  - Draft → Review Requested
  - Review Requested → Changes Requested
  - Changes Requested → Draft
  - Review Requested → Approved
  - Approved → Published
[/DIAGRAM]

Documents transition through states as reviewers provide feedback. They can cycle back to Draft if changes are requested.

## Example 4: User Interaction Sequence

[DIAGRAM]
type: sequence
title: Publishing Workflow Interactions
description: Message sequence between user, system, and OneDrive
elements:
  - User
  - DocFlow CLI
  - Storage
  - OneDrive
flow:
  - User → DocFlow CLI
  - DocFlow CLI → Storage
  - Storage → OneDrive
  - OneDrive → Storage
  - Storage → DocFlow CLI
  - DocFlow CLI → User
[/DIAGRAM]

The sequence shows how user commands flow through the system to storage providers and back.

## Example 5: Entity Relationships

[DIAGRAM]
type: erd
title: DocFlow Data Model
description: Core entities and their relationships
elements:
  - Document
  - Review
  - Reviewer
  - Comment
  - Version
flow:
  - Document → Version
  - Document → Review
  - Review → Reviewer
  - Review → Comment
  - Comment → Reviewer
[/DIAGRAM]

The entity-relationship diagram shows the core data model relationships.

## Example 6: Timeline Example

[DIAGRAM]
type: timeline
title: Document Timeline
description: Document lifecycle stages over time
elements:
  - Drafted
  - In Review
  - Revisions
  - Approved
  - Published
  - Archived
[/DIAGRAM]

The timeline shows the progression of a document through different lifecycle stages.

## Usage

To generate all diagrams in this document:

```bash
docflow diagram generate examples/diagram_example.md --output-dir examples/diagrams
```

This will:
1. Parse all `[DIAGRAM]...[/DIAGRAM]` blocks
2. Generate SVG diagrams for each
3. Evaluate quality with Claude AI
4. Iterate up to 3 times if needed
5. Create `examples/diagram_example.generated.md` with SVG references

Generated diagrams will be in `examples/diagrams/diagram_01.svg`, `diagram_02.svg`, etc.

## Customization

To use a custom design system:

```bash
docflow diagram design-system --output-path design-system.yaml
# Edit design-system.yaml with your colors, fonts, spacing
docflow diagram generate examples/diagram_example.md \
  --output-dir examples/diagrams \
  --config-path design-system.yaml
```

## Quality Evaluation

To evaluate the quality of any generated diagram:

```bash
docflow diagram evaluate examples/diagrams/diagram_01.svg
```

Output:
```
Diagram Quality Evaluation
========================================
Overall Score: 8.5/10 ✓
  Readability:   9.0/10
  Consistency:   8.5/10
  Intuitiveness: 8.5/10
  Correctness:   8.0/10
```

---

## Implementation Details

The Diagram Intelligence System automatically:

1. **Chooses the right backend**:
   - Flowchart, state_machine, erd → Graphviz (fast, deterministic)
   - Architecture, sequence → PlantUML (good for complex diagrams)
   - Timeline, comparison → Vega (data-driven visualizations)

2. **Enforces design system**:
   - Colors: Primary blue (#2563EB), secondary green, accent amber
   - Typography: Inter font, proper sizing for readability
   - Spacing: Consistent padding and element spacing
   - Icons: Feather icon library by default

3. **Evaluates quality on four dimensions**:
   - **Readability**: Can humans quickly understand?
   - **Consistency**: Follows design system?
   - **Intuitiveness**: Is layout logical?
   - **Correctness**: Matches specification?

4. **Iterates until quality threshold**:
   - Score must be ≥ 8.0/10
   - Max 3 iterations (configurable)
   - Suggests improvements based on feedback
   - Falls back gracefully if threshold not reached

---

See [DIAGRAM_STRATEGY.md](../DIAGRAM_STRATEGY.md) for architecture and design details.
See [DIAGRAM_IMPLEMENTATION.md](../DIAGRAM_IMPLEMENTATION.md) for implementation guide.
