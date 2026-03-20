# AWS Budget Proposal — Publisher Living Example

This directory contains the Dr. Clarno AWS cloud compute budget proposal structured as a
Publisher-native document. It serves as the canonical working example for the Publisher
system (see [spec §19](../../tech-specs/spec-publisher.md)).

## Document Structure

| File | Section | Status |
|------|---------|--------|
| `00-executive-summary.md` | Executive Summary | draft |
| `01-research-program.md` | Research Program Overview | draft |
| `02-technical-requirements.md` | Technical Requirements | draft |
| `03-budget-justification.md` | Budget Justification (data-sources: cost-model.csv) | draft |
| `04-timeline.md` | Timeline and Milestones | draft |
| `assets/cost-model.csv` | Tracked data source for §3 | needs pricing data |

## Using Publisher

```bash
# Check status of all sections
neut pub status docs/proposals/aws-budget/

# Compile and generate draft PDF
neut pub compile docs/proposals/aws-budget/.compile.yaml --draft

# Check provenance (will warn when cost-model.csv changes)
neut pub status docs/proposals/aws-budget/03-budget-justification.md
```

## Next Steps

1. Populate `assets/cost-model.csv` with actual AWS pricing from the console.
2. Run `neut pub compile --draft` to generate the review PDF.
3. Share with Dr. Clarno via `neut pub push --draft --provider onedrive` (once OneDrive configured).
4. After review, run `neut pub compile` for the final version.
