# Diagram Architecture & Sizing Standards

## Current Status

✓ **No Rate Limiting**: mermaid.ink API is fully functional  
✓ **Fast API**: Response times 0.2-2.2 seconds per diagram  
✓ **Script Ready**: md_to_docx.py is error-free and production-ready

## Project Rules: Diagram Design for Documents

When creating diagrams for Word document inclusion:

### Size Constraints (Letter-Size, 8.5" × 11")
- **Maximum Height**: 7.2 inches (80% of available 9" height)
- **Target Width**: 6.5 inches (full page width with 1" margins)
- **Rendering**: Mermaid scale=2 for quality text at final size

### Implementation Approach

1. **Design Phase** (Root Problem Fix)
   - Create all diagrams with the 7.2" height limit in mind
   - Break complex diagrams into multiple simpler ones if needed
   - Use subgraphs to organize content hierarchically

2. **Validation Phase** (--check-diagrams mode)
   - Run: `python md_to_docx.py FILE.md --check-diagrams`
   - Identifies which diagrams exceed 7.2" height
   - No Word document generation, just validation

3. **Conversion Phase** (--draft mode)
   - Run: `python md_to_docx.py FILE.md OUTPUT.docx --draft`
   - Converts markdown with embedded diagrams to Word
   - Warnings printed if diagrams exceed limits (for info only)
   - Document includes "DRAFT - FOR INTERNAL REVIEW ONLY" notice

## Workflow for Your Project

### Step 1: Validate Existing Diagrams
```bash
python md_to_docx.py ./Neutron_OS/docs/tech-specs/spec-executive.md --check-diagrams
```
This will show which diagrams are oversized and by how much.

### Step 2: Fix Oversized Diagrams
For any diagram exceeding 7.2":
- Edit the .mmd file in `docs/_tools/diagrams/`
- Reduce complexity or break into multiple diagrams
- Re-run validation to confirm

### Step 3: Convert to Word
```bash
python md_to_docx.py ./Neutron_OS/docs/tech-specs/spec-executive.md ./generated/neutron-os-master-tech-spec.docx --draft
```
Expected time: ~10-30 seconds (depends on diagram count and complexity)

### Step 4: Batch Convert All Docs (After Validation)
```bash
python md_to_docx.py ./Neutron_OS/docs ./generated --all --draft
```
Expected time: 2-5 minutes for all 23 files

## Performance Notes

- **First diagram in a session**: 2-3 seconds (API call + render)
- **Subsequent identical diagrams**: Instant (cached in memory)
- **Network varies**: If slow, add delays in the script with: `time.sleep(1)` between renders

## Configuration Files

- **[DIAGRAM_GUIDELINES.md](DIAGRAM_GUIDELINES.md)** - Full design standards
- **[md_to_docx.py](md_to_docx.py)** - Converter (production-ready)
- **[diagrams/](diagrams/)** - 16 externalized .mmd files

## Script Capabilities

| Command | Purpose | Use When |
|---------|---------|----------|
| `python md_to_docx.py FILE.md` | Convert single file | Quick one-off conversion |
| `python md_to_docx.py FILE.md --draft` | Add draft notice | Review copies |
| `python md_to_docx.py DIR --all` | Batch convert | Generate all docs |
| `python md_to_docx.py FILE.md --check-diagrams` | Validate sizes only | Diagnosing oversized diagrams |

## Next Actions

1. ✓ Type errors fixed (script is clean)
2. ✓ Rate limiting verified (not an issue)  
3. → **Run diagram validation** on master tech spec
4. → **Fix any oversized diagrams** in the .mmd files
5. → **Convert to Word** for review
