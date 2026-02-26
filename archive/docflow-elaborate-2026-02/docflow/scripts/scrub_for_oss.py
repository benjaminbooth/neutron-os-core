#!/usr/bin/env python3
"""
scrub_for_oss.py

Scrub UT Nuclear Engineering references for open source release.
Replaces domain-specific references with generic "Medical Research" equivalents.

Usage:
    # Dry run (show what would change)
    python scripts/scrub_for_oss.py .
    
    # Apply changes
    python scripts/scrub_for_oss.py . --apply
    
    # CI check (fail if unscrubbed content found)
    python scripts/scrub_for_oss.py . --check
"""

import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class Replacement:
    """A pattern replacement with metadata"""
    pattern: str
    replacement: str
    description: str
    case_sensitive: bool = False


# =============================================================================
# Replacement Definitions
# =============================================================================

REPLACEMENTS: List[Replacement] = [
    # === Organizations ===
    Replacement(
        r"UT Nuclear Engineering",
        "Medical Research Institute",
        "Organization name"
    ),
    Replacement(
        r"University of Texas Nuclear Engineering",
        "Medical Research Institute",
        "Full organization name"
    ),
    Replacement(
        r"UT Computational NE",
        "Computational Research Lab",
        "Lab name"
    ),
    Replacement(
        r"NETL(?![A-Za-z])",  # Not followed by letters (avoid matching partial words)
        "Research Laboratory",
        "Lab abbreviation"
    ),
    Replacement(
        r"Nuclear Engineering Teaching Laboratory",
        "Medical Research Laboratory",
        "Full lab name"
    ),
    
    # === Projects ===
    Replacement(
        r"TRIGA(?![A-Za-z])",
        "Research Reactor",
        "Reactor name"
    ),
    Replacement(
        r"bubble[_\s]?flow[_\s]?loop",
        "flow_loop",
        "Project name (lowercase)",
        case_sensitive=True
    ),
    Replacement(
        r"Bubble[_\s]?Flow[_\s]?Loop",
        "Flow Loop",
        "Project name (title case)",
        case_sensitive=True
    ),
    Replacement(
        r"MSR(?![A-Za-z])",
        "System",
        "MSR abbreviation"
    ),
    Replacement(
        r"Molten Salt Reactor",
        "Research System",
        "MSR full name"
    ),
    Replacement(
        r"MIT Irradiation Loop",
        "Irradiation System",
        "MIT loop name"
    ),
    Replacement(
        r"OffGas",
        "Processing",
        "OffGas system name"
    ),
    
    # === Technical Terms ===
    Replacement(
        r"nuclear\s+engineer(?:ing)?",
        "research engineer",
        "Job title (lowercase)"
    ),
    Replacement(
        r"Nuclear\s+Engineer(?:ing)?",
        "Research Engineer",
        "Job title (title case)",
        case_sensitive=True
    ),
    Replacement(
        r"reactor\s+physics",
        "system physics",
        "Technical term"
    ),
    Replacement(
        r"neutronics",
        "particle transport",
        "Technical term"
    ),
    Replacement(
        r"criticality",
        "system stability",
        "Technical term"
    ),
    Replacement(
        r"fuel\s+assembly",
        "component assembly",
        "Technical term"
    ),
    
    # === File/Path Patterns ===
    Replacement(
        r"triga_",
        "research_",
        "File prefix"
    ),
    Replacement(
        r"msr_",
        "system_",
        "File prefix"
    ),
    Replacement(
        r"netl_",
        "lab_",
        "File prefix"
    ),
    
    # === Email Domains ===
    Replacement(
        r"@utexas\.edu",
        "@research-institute.edu",
        "Email domain"
    ),
    Replacement(
        r"@ne\.utexas\.edu",
        "@research-institute.edu",
        "Email domain"
    ),
]

# Patterns that indicate a file should be reviewed manually
REVIEW_PATTERNS = [
    r"classified",
    r"proprietary",
    r"confidential",
    r"export\s+control",
    r"ITAR",
    r"EAR",
]

# Files/directories to skip
SKIP_PATTERNS = [
    r"\.git/",
    r"node_modules/",
    r"__pycache__/",
    r"\.pyc$",
    r"\.egg-info/",
    r"dist/",
    r"build/",
    r"\.env$",
    r"\.env\.",
    r"scrub_for_oss\.py$",  # Don't scrub this file
    r"\.lock$",
    r"\.png$",
    r"\.jpg$",
    r"\.jpeg$",
    r"\.gif$",
    r"\.ico$",
    r"\.woff",
    r"\.ttf$",
    r"\.eot$",
    r"\.pdf$",
]

# File extensions to process
PROCESS_EXTENSIONS = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".json", ".toml",
    ".sql", ".sh", ".bash", ".zsh",
    ".ts", ".tsx", ".js", ".jsx",
    ".html", ".htm", ".css", ".scss",
    ".tf", ".hcl",
    ".xml", ".csv",
    ".rst", ".adoc",
    ".dockerfile", "Dockerfile",
    ".gitignore", ".dockerignore",
    "Makefile", ".mk",
}


# =============================================================================
# Core Functions
# =============================================================================

def should_skip(path: Path) -> bool:
    """Check if file should be skipped"""
    path_str = str(path)
    return any(re.search(pattern, path_str) for pattern in SKIP_PATTERNS)


def should_process(path: Path) -> bool:
    """Check if file should be processed"""
    # Check extension
    if path.suffix.lower() in PROCESS_EXTENSIONS:
        return True
    # Check full name (for files like Makefile, Dockerfile)
    if path.name in PROCESS_EXTENSIONS:
        return True
    return False


def check_for_review(content: str, path: Path) -> List[str]:
    """Check for patterns that require manual review"""
    issues = []
    for pattern in REVIEW_PATTERNS:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            issues.append(f"  ⚠️  Line {line_num}: Found '{match.group()}' - requires manual review")
    return issues


def scrub_content(content: str) -> Tuple[str, List[str]]:
    """
    Apply replacements to content.
    Returns (scrubbed_content, list_of_changes)
    """
    changes = []
    result = content
    
    for repl in REPLACEMENTS:
        flags = 0 if repl.case_sensitive else re.IGNORECASE
        matches = list(re.finditer(repl.pattern, result, flags))
        
        if matches:
            for match in matches:
                line_num = result[:match.start()].count('\n') + 1
                changes.append(
                    f"  Line {line_num}: '{match.group()}' → '{repl.replacement}' ({repl.description})"
                )
            result = re.sub(repl.pattern, repl.replacement, result, flags=flags)
    
    return result, changes


def scrub_file(path: Path, dry_run: bool = True) -> Tuple[List[str], List[str]]:
    """
    Scrub a single file.
    Returns (list_of_changes, list_of_review_issues)
    """
    try:
        content = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return [], []
    except Exception as e:
        return [f"  Error reading file: {e}"], []
    
    # Check for content requiring manual review
    review_issues = check_for_review(content, path)
    
    # Apply scrubbing
    scrubbed, changes = scrub_content(content)
    
    if changes and not dry_run:
        try:
            path.write_text(scrubbed, encoding='utf-8')
        except Exception as e:
            return [f"  Error writing file: {e}"], review_issues
    
    return changes, review_issues


def scrub_directory(root: Path, dry_run: bool = True, verbose: bool = True) -> Tuple[int, int, List[str]]:
    """
    Scrub all files in directory.
    Returns (total_changes, files_changed, review_issues)
    """
    total_changes = 0
    files_changed = 0
    all_review_issues = []
    
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        if not should_process(path):
            continue
        
        changes, review_issues = scrub_file(path, dry_run)
        
        if changes:
            files_changed += 1
            total_changes += len(changes)
            
            if verbose:
                rel_path = path.relative_to(root)
                print(f"\n📄 {rel_path}")
                for change in changes:
                    print(change)
        
        if review_issues:
            rel_path = path.relative_to(root)
            all_review_issues.append(f"\n📄 {rel_path}")
            all_review_issues.extend(review_issues)
    
    return total_changes, files_changed, all_review_issues


def print_summary(
    total_changes: int,
    files_changed: int,
    review_issues: List[str],
    dry_run: bool
):
    """Print summary of changes"""
    print("\n" + "=" * 60)
    
    if dry_run:
        print("📋 DRY RUN SUMMARY")
    else:
        print("✅ CHANGES APPLIED")
    
    print("=" * 60)
    print(f"  Files modified: {files_changed}")
    print(f"  Total replacements: {total_changes}")
    
    if review_issues:
        print(f"\n⚠️  MANUAL REVIEW REQUIRED ({len([i for i in review_issues if i.startswith('  ⚠️')])} issues)")
        for issue in review_issues:
            print(issue)
    
    if dry_run and total_changes > 0:
        print("\n💡 Run with --apply to make these changes")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Scrub content for open source release",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes (dry run)
  python scripts/scrub_for_oss.py .
  
  # Apply changes
  python scripts/scrub_for_oss.py . --apply
  
  # CI check (exit 1 if changes needed)
  python scripts/scrub_for_oss.py . --check
  
  # Quiet mode (summary only)
  python scripts/scrub_for_oss.py . --quiet
        """
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Directory to scrub"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry run)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with error if changes needed (for CI)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only show summary"
    )
    
    args = parser.parse_args()
    
    if not args.path.exists():
        print(f"❌ Error: {args.path} does not exist")
        return 1
    
    if not args.path.is_dir():
        print(f"❌ Error: {args.path} is not a directory")
        return 1
    
    dry_run = not args.apply
    verbose = not args.quiet
    
    if verbose:
        if dry_run:
            print(f"🔍 Scanning {args.path} for content to scrub (dry run)...")
        else:
            print(f"✏️  Scrubbing content in {args.path}...")
    
    total_changes, files_changed, review_issues = scrub_directory(
        args.path,
        dry_run=dry_run,
        verbose=verbose
    )
    
    print_summary(total_changes, files_changed, review_issues, dry_run)
    
    # Exit codes
    if args.check:
        if total_changes > 0:
            print("\n❌ CI Check Failed: Unscrubbed content found")
            return 1
        if review_issues:
            print("\n⚠️  CI Check Warning: Content requires manual review")
            # Don't fail for review issues, just warn
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
