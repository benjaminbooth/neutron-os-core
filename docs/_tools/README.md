# Documentation Tools

**Updated:** 2026-03-16

## Document Generation

Use `neut pub` for all document generation and publishing:

```bash
# Generate a single .docx
neut pub generate docs/requirements/prd-executive.md

# Generate all changed docs
neut pub publish --all --changed-only

# Push to OneDrive (browser-based, no API keys needed)
neut pub push --endpoint onedrive .neut/generated/prd/prd_neutron-os-executive.docx
```

Generated `.docx` files are written to `.neut/generated/` (gitignored).

## Legacy Scripts (deprecated)

| Script | Status | Replacement |
|--------|--------|-------------|
| `md_to_docx.py` | Deprecated | `neut pub generate <file>` |
| `generate_all_docs.py` | Deprecated | `neut pub publish --all` |
| `pdf_to_text.py` | Still useful | No replacement yet |

## Notes

- `generated/` subdirectory is gitignored — generated artifacts don't belong in version control
- Archived tools and one-offs are in `../_archive/`
