# Publisher Merge Scenario: Sense + External Review Integration

**Document**: Complete guide for testing and implementing complex PRD merge workflows
**Date**: February 25, 2026
**Status**: Reference Implementation  
**Test File**: `tests/integration/test_docflow_merge_scenario.py`

## Overview

This document describes a sophisticated merging workflow that handles a realistic scenario:

> A published PRD enters review on SharePoint. Simultaneously, local synthesis of Sense signals produces draft revisions. Both streams create divergence that must be semantically merged using Neut's RAG context.

### The Scenario

**Initial State:**
- Advanced Analytics PRD published at **v2.0.0** on SharePoint (Feb 10, 2026)
- Document enters review cycle
- Status: "published" but actively being refined

**Concurrent Streams (Feb 18-21):**

**Stream 1: Local Sense Synthesis**
1. Meeting notes (Feb 18): Team discussion about missing data handling → Action item
2. GitLab issue discussion (Feb 20): Experimentalists request Bayesian methods → Decision signal
3. Voice memo (Feb 21): PI concerns about performance scaling → Blocker

**Stream 2: External SharePoint Review**
1. Dr. Kim comments: Missing effect size reporting requirement
2. Prof. Lee suggests: Add Vega backend for interactive dashboards
3. Dr. Chen refines: Performance metric clarification (< 3s with caveats)
4. Dr. Patel recommends: Move Bayesian methods to v2.1

**Merge Task:**
Combine both streams into coherent v2.1.0 that:
- Incorporates Sense-driven revisions (missing data, scalability concerns)
- Integrates external reviewer feedback (effect size, interactive viz, Bayesian)
- Resolves convergences (Bayesian mentioned in both streams → strong signal)
- Maintains document integrity and semantic consistency

---

## Architecture: 7-Stage Pipeline

```
┌─────────────────────┐
│  1. DIVERGENCE      │
│  DETECTION          │  ← Detect changes in external doc
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  2. SIGNAL          │
│  EXTRACTION         │  ← Neut Signal extracts from multiple sources
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  3. SYNTHESIS       │
│  (Synthesizer)      │  ← Combine signals into structured changelog
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  4. DRAFT           │
│  REVISIONS          │  ← Map changelog entries to PRD changes
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  5. CONCEPTUAL      │
│  MERGE              │  ← Neut RAG-assisted semantic merging
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  6. VERSION BUMP    │
│  & METADATA         │  ← Semantic versioning (v2.0.0 → v2.1.0)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  7. PUBLISH         │
│                     │  ← Final merged document ready for SharePoint
└─────────────────────┘
```

---

## Stage Details

### Stage 1: Divergence Detection

**Input**: Baseline published .md + Current external document (SharePoint)

**Process**:
```python
baseline_md_hash = sha256(baseline_content)
external_hash = sha256(external_content)

report = {
    "md_changed_since_sync": baseline_md_hash != last_sync_hash,
    "external_changed_since_sync": external_hash != last_sync_hash,
    "requires_merge": both_changed,
}
```

**Output**: `DivergenceReport` containing:
- Change type (COMMENT, TRACKED, CONTENT_DRIFT, STRUCTURAL)
- Section affected
- Author and timestamp
- Original vs. new text
- Confidence score (0.92-0.98 for external)

**Test Case**: `TestDivergenceDetection`
- ✓ Hashes correctly distinguish versions
- ✓ All 4 external changes extracted
- ✓ Change metadata preserved

---

### Stage 2: Signal Extraction

**Input**: Source files from various Sense extractors

**Extractors Used**:
- `transcript.py` → Meeting notes → Signal (action_item, 0.95 confidence)
- `gitlab_diff.py` → Issue discussion → Signal (decision, 0.90 confidence)
- `voice.py` → Voice memo transcription → Signal (blocker, 0.85 confidence)
- `docflow_review.py` → External doc comments → Change objects

**Process**:
```python
signals = [
    Signal(source="meeting_notes", signal_type="action_item", ...),
    Signal(source="gitlab_discussion", signal_type="decision", ...),
    Signal(source="voice_memo", signal_type="blocker", ...),
]
```

**Output**: `Extraction` with signals, confidence scores, and metadata

**Test Case**: `TestSignalSynthesis`
- ✓ All signals extracted with realistic confidence (0.85-0.95)
- ✓ Signal types diverse (action_item, decision, blocker)
- ✓ Provenance tracked (people involved, initiatives)

---

### Stage 3: Synthesis

**Input**: List of Signal objects from multiple extractors

**Process** (using actual `Synthesizer`):
```python
synthesizer = Synthesizer()
changelog = synthesizer.synthesize(
    signals=all_signals,
    date="2026-02-21",
    include_all=True,  # All signals, even previously reported
)
```

**Output**: `Changelog` with entries grouped by:
- Initiative (e.g., "advanced-analytics-prd")
- Signal type (action_item, decision, blocker)
- Confidence weighting

**Test Case**: `TestSenseWorkflowIntegration`
- ✓ Signals flow through actual Synthesizer
- ✓ Entries grouped by initiative
- ✓ Signal types reflected in changelog
- ✓ Mappable to draft revisions

**Key Insight**: This is where Sense workflow integrates with Publisher. The Synthesizer produces a structured changelog that becomes the input to merge decisions.

---

### Stage 4: Draft Revisions

**Input**: Changelog entries + baseline PRD

**Process**:
Human reviews changelog and creates PR/branch with suggested revisions:

```
Changelog Entry 1 (Action Item):
  "Team meeting: Add missing data imputation strategy to R2"
  → Draft Revision: Add R2.1 requirement for missing data handling

Changelog Entry 2 (Decision):
  "Issue #1523: Need Bayesian methods sooner"
  → Draft Revision: Update Open Questions - consider v2.1

Changelog Entry 3 (Blocker):
  "Voice memo: Performance concerns at scale"
  → Draft Revision: Add validation caveat for 500k+ datasets
```

**Status in System**: Draft branch with commits, not yet merged to main

**Test Case**: `TestSenseSignalsInMerge`
- ✓ Signal → Revision traceability
- ✓ Confidence affects revision weight
- ✓ Signal sources realistic (meeting_notes, voice_memo, gitlab_discussion)

---

### Stage 5: Conceptual Merge

**Input**:
- Baseline v2.0.0 PRD
- Draft revisions (from Sense synthesis)
- External changes (from SharePoint review)
- Divergence report

**Process** (Neut's LLM + RAG):

For each section:
1. Compare baseline vs. draft revision vs. external change
2. Check for conflicts
3. Apply merge strategy:
   - `accept_external` - Reviewer change is correct, use it
   - `accept_local` - Sense-derived change is better
   - `combine` - Both have merit, synthesize
   - `defer` - Can't resolve, escalate to human

**Example Decisions**:

| Section | Signal | External | Decision | Rationale |
|---------|--------|----------|----------|-----------|
| R1 | - | "Add effect size" | combine | Correct requirement, incorporate |
| R2 | "Missing data" | "Add Vega" | combine | Both add value, not conflicting |
| Q1 | "Bayesian v2.1" | "Bayesian v2.1" | combine | **Convergence** → high confidence |
| Metrics | "Validate at scale" | "< 3s bound" | combine | PI concern + refinement = better metric |

**Test Case**: `TestConceptualMerge`
- ✓ Decisions generated for all sections
- ✓ Both Sense and external incorporated
- ✓ Confidence scores respected
- ✓ Semantic coherence maintained

---

### Stage 6: Version Bump & Metadata

**Input**: Previous version v2.0.0 + Commit count since then

**Process** (Semantic Versioning):
```
Commits since v2.0.0:
1. "fix: reformat TOC" 
2. "merge: Sense synthesis"
3. "merge: external reviews"
4. "merge: semantic reconciliation"
5. "docs: merge audit trail"

Count = 5 commits
Rule: 2-5 commits → Minor bump
Result: v2.0.0 → v2.1.0
```

**Metadata Update**:
```json
{
  "doc_id": "advanced-analytics-prd",
  "status": "published",
  "published": {
    "version": "v2.1.0",
    "commit_sha": "new_merge_commit",
    "published_at": "2026-02-21T21:00:00Z",
    "generation_provider": "pandoc-docx",
    "storage_provider": "sharepoint"
  }
}
```

**Test Case**: `TestMergeOutput`
- ✓ Version bumped correctly (v2.0.0 → v2.1.0)
- ✓ Markdown structure preserved
- ✓ No syntax errors

---

### Stage 7: Publish

**Input**: Merged markdown + Metadata

**Process**:
1. Validate markdown syntax
2. Update cover page: `**[published] v2.1.0** | February 21, 2026`
3. Convert to .docx via Pandoc
4. Upload to SharePoint
5. Update registry with commit SHA
6. Log merge decisions in audit trail

**Output**: Published v2.1.0 document

**Test Case**: `TestFullMergeWorkflow` + `TestCompleteSenseToMergePipeline`
- ✓ All stages execute in sequence
- ✓ Audit trail generated
- ✓ Document ready for publication

---

## Key Integration: How Neut Signal Feeds the Merge

```
Neut Signal Pipeline:
├─ Extract (voice, notes, chat)
├─ Synthesize (Synthesizer)
├─ Output: Changelog with entries
└─ Human review: Entry → Draft revision

Merge Pipeline:
├─ Input: Draft revisions + External changes
├─ Detect: What changed where
├─ Merge: Semantically combine both sources
├─ Resolve: Conflicts + Convergences
└─ Output: v2.1.0 with audit trail
```

**Critical Insight**: Sense doesn't replace external review—it **enhances** it by:
- Capturing distributed feedback (voice memos, chat)
- Synthesizing into structured signals
- Highlighting convergence (when both sources agree)
- Identifying gaps (signal mentions something external doesn't)

---

## Test Structure: 28 Test Cases

### Group 1: Divergence Detection (3 tests)
✓ Detect divergence between .md and external
✓ Extract all external changes
✓ Preserve change metadata

### Group 2: Sense Workflow Integration (4 tests)
✓ Signals flow through Synthesizer
✓ Changelog groups by initiative
✓ Changelog reflects signal types
✓ Signals map to draft revisions

### Group 3: Signal Synthesis (5 tests)
✓ All signals extracted
✓ Signal types diverse
✓ Confidence realistic
✓ Provenance tracked
✓ Related signals grouped

### Group 4: Conceptual Merge (3 tests)
✓ Merge decisions generated
✓ Merge incorporates both sources
✓ Confidence levels respected

### Group 5: Merge Output (3 tests)
✓ Merged markdown valid
✓ Version bumped correctly
✓ Document integrity preserved

### Group 6: Sense Signals in Merge (3 tests)
✓ Sense signals inform decisions
✓ Signal confidence affects weight
✓ Signals from realistic sources

### Group 7: Full Workflow (5 tests)
✓ Workflow detects changes
✓ Workflow extracts signals
✓ Workflow merges semantically
✓ Workflow generates audit trail
✓ Workflow produces publishable output

### Group 8: Complete Pipeline (2 tests)
✓ Complete pipeline signal-to-merge
✓ Changelog-to-merge traceability

**Total**: 28 passing tests ✅

---

## Running the Tests

### All tests:
```bash
pytest tests/integration/test_docflow_merge_scenario.py -v
```

### Specific test group:
```bash
# Sense workflow integration only
pytest tests/integration/test_docflow_merge_scenario.py::TestSenseWorkflowIntegration -v

# Complete pipeline demonstration
pytest tests/integration/test_docflow_merge_scenario.py::TestCompleteSenseToMergePipeline -v
```

### With output details:
```bash
pytest tests/integration/test_docflow_merge_scenario.py -v -s
```

---

## Applying to Real PRDs

### For Experiment Manager PRD:

1. **Gather Sense Signals**:
   - Find recent meetings about Experiment Manager
   - Collect voice memos / transcripts
   - Mine GitLab issues and PRs
   - Extract Teams chat discussions

2. **Extract Current External Changes**:
   - Download SharePoint version
   - Extract comments and tracked changes
   - Document authors and timestamps

3. **Run Merge Scenario**:
   ```python
   from tests.integration.test_docflow_merge_scenario import MergeTestHelper
   
   # Load actual Experiment Manager PRD
   baseline = DocumentState.from_registry("experiment-manager-prd")
   
   # Extract real signals (not mocked)
   signals = actual_sense_extractor.run()
   
   # Get external changes
   external = SharePointProvider.fetch_changes(
       "experiment-manager-prd"
   )
   
   # Merge
   merged = semantic_merge(baseline, signals, external)
   ```

4. **Review Merge Decisions**:
   - Check audit trail
   - Verify convergences identified
   - Resolve any conflicts manually

5. **Publish**:
   - Commit to git
   - Run publish workflow
   - Version bumps automatically (v2.0.0 → v2.1.0)

---

## Key Concepts

### Convergence Signal
When multiple sources (Sense + external) mention the same issue, it's a **high-confidence signal**:
- Bayesian methods (mentioned in both GitLab issue AND Dr. Patel comment)
- Performance scaling (PI voice concern + Dr. Chen refinement)
- Missing data (Team meeting + implicit in feedback requests)

Merge should prioritize convergence items.

### Confidence Weighting
- External doc changes: 0.92-0.98 (user directly edited)
- Sense signals: 0.85-0.95 (extracted + interpreted)
- Synthesized signals: 0.90-0.95 (structured from extraction)

Lower confidence means "verify with human," not "ignore."

### Audit Trail
Every merge decision is recorded:
```json
{
  "merge_timestamp": "2026-02-21T21:00:00Z",
  "decision": {
    "section": "Open Questions - Q1",
    "resolution": "combine",
    "sources": ["signal:sig_gitlab_002", "external:ext_004"],
    "rationale": "Convergence: both Sense (GitLab) and external (Dr. Patel) recommend v2.1"
  },
  "version_bump": "v2.0.0 → v2.1.0"
}
```

---

## Next Steps

1. ✅ **Test Created**: `test_docflow_merge_scenario.py` (28 tests, all passing)
2. ⏳ **Real PRD Test**: Apply to Experiment Manager PRD
3. ⏳ **SharePoint Integration**: Live external change extraction
4. ⏳ **Automated Scheduling**: Detect changes on schedule (daily, on-demand, auto)
5. ⏳ **Manual Review UI**: Dashboard for reviewing merge decisions before publish

---

## References

- **Neut Signal Pipeline**: `tools/pipelines/signal/` (extractors, synthesizer, models)
- **Publisher Review Extractor**: `tools/pipelines/signal/extractors/docflow_review.py`
- **Semantic Versioning**: `tools/docflow/scripts/publish.py` (version logic)
- **State Management**: `tools/docflow/state.py` (DocumentState, PublicationRecord)

---

## Questions & Answers

**Q: What if Sense signals conflict with external changes?**
A: Merge marks as `resolution: "conflict"` and requires human review. No auto-decision.

**Q: Can we merge if only external doc changed?**
A: Yes, `merge_strategy: "external_wins"` when only SharePoint has changes.

**Q: How do we prevent accidentally overwriting good feedback?**
A: Complete audit trail + mandatory human review of merge decisions before publish.

**Q: What about performance of the merge?**
A: Merge is O(sections × changes), typically < 1s. LLM calls async if enabled.

---

**Last Updated**: February 25, 2026  
**Test Status**: 28/28 passing ✅  
**Ready for**: Real PRD scenario testing
