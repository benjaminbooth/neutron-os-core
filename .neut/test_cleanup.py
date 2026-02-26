#!/usr/bin/env python
"""Test cleanup on medical-isotope-prd.md"""

from pathlib import Path
from tools.docflow.cleanup import MarkdownCleanup

prd_file = Path('docs/prd/medical-isotope-prd.md')

if prd_file.exists():
    print(f'Analyzing {prd_file}...')
    
    # Read original
    original = prd_file.read_text()
    original_size = len(original)
    
    # Apply cleanup (read-only, doesn't modify)
    cleaner = MarkdownCleanup()
    cleaned = cleaner.clean_content(original)
    cleaned_size = len(cleaned)
    
    # Show results
    print(f'Original size: {original_size} bytes')
    print(f'Cleaned size: {cleaned_size} bytes')
    print(f'Diff: {original_size - cleaned_size} bytes')
    print()
    print('Fixes that would be applied:')
    for fix_type, count in cleaner.fixes_applied.items():
        print(f'  - {fix_type}: {count}')
    
    if original != cleaned:
        print()
        print('✓ Document would benefit from cleanup')
    else:
        print()
        print('✓ Document is already clean (no fixes needed)')
else:
    print(f'{prd_file} not found')
