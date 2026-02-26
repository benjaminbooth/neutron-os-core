"""Document link registry and git context management."""

import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, TypedDict
from zipfile import ZipFile
import re


class LinkEntry(TypedDict, total=False):
    """Registry entry for a document's published URLs."""
    
    source_file: str  # docs/prd/foo.md
    doc_id: str  # foo or experiment-manager-prd
    published_url: Optional[str]  # https://.../foo.docx
    draft_url: Optional[str]  # https://.../foo-DRAFT.docx
    published_storage_id: Optional[str]  # OneDrive file ID
    draft_storage_id: Optional[str]


@dataclass
class GitContext:
    """Current Git repository context."""
    
    current_branch: str = ""
    commit_sha: str = ""
    is_dirty: bool = False
    ahead_count: int = 0
    behind_count: int = 0
    
    def is_main_branch(self) -> bool:
        """Check if on main/master branch."""
        return self.current_branch in ("main", "master")
    
    def is_publish_branch(self) -> bool:
        """Check if current branch should trigger publishing."""
        main = self.is_main_branch()
        release = self.current_branch.startswith("release/")
        return main or release
    
    def is_draft_branch(self) -> bool:
        """Check if current branch should only generate local drafts."""
        feature = self.current_branch.startswith("feature/")
        dev = self.current_branch.startswith("dev")
        return feature or dev
    
    @staticmethod
    def from_git_repo(repo_root: Path) -> "GitContext":
        """Detect current Git context from repository."""
        try:
            branch = subprocess.check_output(
                ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL
            ).strip()
            
            commit = subprocess.check_output(
                ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL
            ).strip()
            
            # Check if dirty
            is_dirty = subprocess.run(
                ["git", "-C", str(repo_root), "diff-index", "--quiet", "HEAD"],
                capture_output=True
            ).returncode != 0
            
            # Check ahead/behind
            try:
                status = subprocess.check_output(
                    ["git", "-C", str(repo_root), "rev-list", "--left-right", "--count", "HEAD...@{u}"],
                    text=True,
                    stderr=subprocess.DEVNULL
                ).strip()
                
                if status:
                    ahead, behind = status.split()
                    ahead_count = int(ahead)
                    behind_count = int(behind)
                else:
                    ahead_count = behind_count = 0
            except:
                ahead_count = behind_count = 0
            
            return GitContext(
                current_branch=branch,
                commit_sha=commit,
                is_dirty=is_dirty,
                ahead_count=ahead_count,
                behind_count=behind_count,
            )
        except subprocess.CalledProcessError:
            # Not a git repo or git not available
            return GitContext()


class LinkRegistry:
    """Manages document-to-URL mappings for cross-document linking."""
    
    def __init__(self, registry_file: Optional[Path] = None):
        """Initialize registry, loading from file if it exists."""
        self.registry_file = registry_file or Path.cwd() / ".doc-registry.json"
        self.entries: dict[str, LinkEntry] = {}
        
        if self.registry_file.exists():
            self._load()
    
    def _load(self) -> None:
        """Load registry from JSON file."""
        try:
            with open(self.registry_file, "r") as f:
                data = json.load(f)
            self.entries = {k: v for k, v in data.items()}
        except (json.JSONDecodeError, FileNotFoundError):
            self.entries = {}
    
    def save(self) -> None:
        """Save registry to JSON file."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_file, "w") as f:
            json.dump(self.entries, f, indent=2)
    
    def register(self, doc_id: str, source_file: str, published_url: Optional[str] = None,
                 draft_url: Optional[str] = None, published_storage_id: Optional[str] = None,
                 draft_storage_id: Optional[str] = None) -> None:
        """Register a document with its publication URLs."""
        self.entries[doc_id] = {
            "source_file": source_file,
            "doc_id": doc_id,
            "published_url": published_url,
            "draft_url": draft_url,
            "published_storage_id": published_storage_id,
            "draft_storage_id": draft_storage_id,
        }
    
    def resolve_link(self, doc_id: str, draft: bool = False) -> Optional[str]:
        """Get the published URL for a document."""
        entry = self.entries.get(doc_id)
        if not entry:
            return None
        
        if draft:
            return entry.get("draft_url")
        else:
            return entry.get("published_url")
    
    def resolve_by_filename(self, filename: str) -> Optional[str]:
        """Resolve a filename to its published URL.
        
        Handles:
        - foo.md → foo
        - experiment-manager-prd.md → experiment-manager-prd
        """
        doc_id = filename.replace(".md", "")
        return self.resolve_link(doc_id)
    
    def rewrite_links_in_docx(self, docx_path: Path) -> None:
        """Rewrite internal .md links in a DOCX file to published URLs.
        
        Converts:
        - [Link text](foo.md) → [Link text](https://.../foo.docx)
        - [Link text](../prd/foo.md) → [Link text](https://.../foo.docx)
        """
        # DOCX is a ZIP file containing XML
        # Links are in document.xml with <a:hyperlink> tags
        
        with ZipFile(docx_path, "a") as docx:
            # Get document.xml
            doc_xml_path = "word/document.xml"
            if doc_xml_path not in docx.namelist():
                return  # No document.xml, skip
            
            with docx.open(doc_xml_path) as f:
                doc_xml = f.read().decode("utf-8")
            
            # Find and replace markdown links
            # Regex: href="[relative-path/]filename.md"
            pattern = r'href="(?:.*?/)?([^/]+\.md)"'
            
            def replace_link(match):
                filename = match.group(1)
                url = self.resolve_by_filename(filename)
                if url:
                    return f'href="{url}"'
                return match.group(0)
            
            doc_xml = re.sub(pattern, replace_link, doc_xml)
            
            # Write back
            docx.writestr(doc_xml_path, doc_xml.encode("utf-8"))
    
    def check_links(self, markdown_content: str) -> dict[str, str]:
        """Check all markdown links in a document.
        
        Returns a dict of unresolved links:
        {filename: reason}
        """
        unresolved = {}
        
        # Regex: [text](ref.md) or [text](../path/ref.md)
        pattern = r'\[.*?\]\((?:.*?/)?([^/]+\.md)\)'
        
        for match in re.finditer(pattern, markdown_content):
            filename = match.group(1)
            url = self.resolve_by_filename(filename)
            if not url:
                unresolved[filename] = "No published URL registered"
        
        return unresolved
