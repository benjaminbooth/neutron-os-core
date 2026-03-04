# PRD: TRIGA Reactor Log Digitization

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Author** | Jeongwon Seo |
| **Date** | 2026-03-04 |
| **Priority** | High |

## Problem Statement

TRIGA reactor operations are logged in paper binders and legacy spreadsheets.
This data is critical for digital twin calibration, regulatory compliance,
and operator training — but it's trapped in formats that resist analysis.

[TODO: Jay fills in — what specific pain points has he encountered?]

## Proposed Solution

Digitize reactor operation logs into a structured format that integrates with
the TRIGA Digital Twin pipeline and NeutronOS sensing system.

### Core Capabilities

1. **Log Parsing** — Extract structured data from scanned log pages and CSV exports
   [TODO: Jay fills in — what log formats exist? Handwritten? Typed? CSV?]

2. **Data Validation** — Cross-reference digitized entries against known reactor parameters
   [TODO: Jay fills in — what validation rules matter most?]

3. **Integration** — Feed validated data into the Digital Twin model and NeutronOS signals
   [TODO: Jay fills in — which DT models consume this data?]

## Success Criteria

- [ ] [TODO: What constitutes "done" for Phase 1?]
- [ ] [TODO: How many log entries need to be digitized?]
- [ ] [TODO: What accuracy threshold is acceptable?]

## Technical Approach

[TODO: Jay fills in — what tools/libraries is he using? Python scripts? OCR?
What's the current pipeline look like?]

### Architecture

[TODO: Mermaid diagram showing data flow from paper logs to DT model]

## Timeline

| Milestone | Target Date | Status |
|-----------|------------|--------|
| Phase 1: CSV log parsing | [TODO] | In Progress |
| Phase 2: Scanned page OCR | [TODO] | Not Started |
| Phase 3: DT integration | [TODO] | Not Started |

## Dependencies

- TRIGA Digital Twin codebase (TRIGA_DT, TRIGA_ModSim_Tools)
- NeutronOS sensing pipeline (for signal ingestion)
- [TODO: Other dependencies?]

## Open Questions

1. [TODO: Jay's biggest uncertainty right now?]
2. [TODO: What decisions need Ben's or advisor's input?]
