#!/usr/bin/env python3
"""
Mermaid Diagram Linter

Checks for common Mermaid diagram issues that cause rendering problems:
1. graph LR with long subgraph titles (causes text overlap)
2. Style blocks missing explicit color
3. Subgraphs with multi-line titles but no spacer

Usage:
    python scripts/lint_mermaid.py docs/
    python scripts/lint_mermaid.py docs/tech-specs/spec-foo.md
"""

import argparse
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator

# Thresholds
MAX_SUBGRAPH_TITLE_LEN_FOR_LR = 25  # Characters before title wraps in LR mode


@dataclass
class LintError:
    file: Path
    line: int
    code: str
    message: str

    def __str__(self):
        return f"{self.file}:{self.line}: [{self.code}] {self.message}"


def extract_mermaid_blocks(content: str) -> Iterator[tuple[int, str]]:
    """Yield (start_line, block_content) for each mermaid block."""
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
    lines = content.split("\n")
    
    for match in pattern.finditer(content):
        # Find line number of match start
        start_pos = match.start()
        line_num = content[:start_pos].count("\n") + 1
        yield line_num, match.group(1)


def check_lr_long_titles(block: str, start_line: int, file: Path) -> Iterator[LintError]:
    """Check for graph LR with long subgraph titles."""
    # Is this a graph LR or flowchart LR?
    is_lr = bool(re.search(r"^(graph|flowchart)\s+LR", block, re.MULTILINE))
    if not is_lr:
        return
    
    # Find subgraph titles
    for i, line in enumerate(block.split("\n")):
        match = re.search(r'subgraph\s+"([^"]+)"', line)
        if match:
            title = match.group(1)
            if len(title) > MAX_SUBGRAPH_TITLE_LEN_FOR_LR:
                yield LintError(
                    file=file,
                    line=start_line + i,
                    code="MM001",
                    message=f"Subgraph title '{title[:30]}...' ({len(title)} chars) too long for LR layout. "
                            f"Max {MAX_SUBGRAPH_TITLE_LEN_FOR_LR} chars, or use TB layout."
                )


def check_missing_color(block: str, start_line: int, file: Path) -> Iterator[LintError]:
    """Check for style statements missing explicit color."""
    for i, line in enumerate(block.split("\n")):
        # Look for style statements
        if re.search(r"^\s*style\s+\w+", line):
            # Check if it has a color specification
            if "fill:" in line and "color:" not in line:
                yield LintError(
                    file=file,
                    line=start_line + i,
                    code="MM002",
                    message="Style has fill: but no explicit color:. Add color:#333 or color:#fff"
                )


def check_multiline_title_no_spacer(block: str, start_line: int, file: Path) -> Iterator[LintError]:
    """Check for subgraphs with <br/> in title but no spacer node."""
    lines = block.split("\n")
    
    for i, line in enumerate(lines):
        match = re.search(r'subgraph\s+(\w+)\["([^"]+)"', line)
        if match and "<br/>" in match.group(2):
            subgraph_id = match.group(1)
            # Look for a spacer in the next few lines
            spacer_found = False
            for j in range(i + 1, min(i + 5, len(lines))):
                if re.search(rf"{subgraph_id}_SPACER|SPACER", lines[j], re.IGNORECASE):
                    spacer_found = True
                    break
                if "end" in lines[j]:
                    break
            
            if not spacer_found:
                yield LintError(
                    file=file,
                    line=start_line + i,
                    code="MM003",
                    message=f"Subgraph '{subgraph_id}' has multi-line title (<br/>) but no spacer node. "
                            "Add a spacer to prevent overlap."
                )


def lint_file(file: Path) -> list[LintError]:
    """Run all lint checks on a file."""
    errors = []
    content = file.read_text()
    
    for start_line, block in extract_mermaid_blocks(content):
        errors.extend(check_lr_long_titles(block, start_line, file))
        errors.extend(check_missing_color(block, start_line, file))
        errors.extend(check_multiline_title_no_spacer(block, start_line, file))
    
    return errors


def lint_path(path: Path) -> list[LintError]:
    """Lint a file or directory recursively."""
    errors = []
    
    if path.is_file():
        if path.suffix == ".md":
            errors.extend(lint_file(path))
    elif path.is_dir():
        for md_file in path.rglob("*.md"):
            errors.extend(lint_file(md_file))
    
    return errors


def main():
    parser = argparse.ArgumentParser(description="Lint Mermaid diagrams in Markdown files")
    parser.add_argument("paths", nargs="+", type=Path, help="Files or directories to lint")
    parser.add_argument("--fix", action="store_true", help="Attempt to auto-fix issues (not yet implemented)")
    args = parser.parse_args()
    
    all_errors = []
    for path in args.paths:
        all_errors.extend(lint_path(path))
    
    if all_errors:
        print(f"\n🔴 Found {len(all_errors)} Mermaid diagram issue(s):\n")
        for error in sorted(all_errors, key=lambda e: (str(e.file), e.line)):
            print(f"  {error}")
        print("\n📚 See docs/tech-specs/spec-mermaid-best-practices.md for fixes\n")
        sys.exit(1)
    else:
        print("✅ No Mermaid diagram issues found")
        sys.exit(0)


if __name__ == "__main__":
    main()
