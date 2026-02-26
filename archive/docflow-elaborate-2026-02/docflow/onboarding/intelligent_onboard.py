#!/usr/bin/env python3
"""
Intelligent Document Onboarding System for DocFlow

This module automatically discovers existing documents, analyzes their link structure,
and provides interactive or automated onboarding with smart matching to OneDrive.
"""

import os
import re
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from enum import Enum
from datetime import datetime
import json
import yaml
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.tree import Tree
from rich.panel import Panel
from rich.markdown import Markdown
import networkx as nx
from fuzzywuzzy import fuzz
import frontmatter

from ..state.document import DocumentState, StateEnum
from ..storage.onedrive import OneDriveStorage
from ..llm.anthropic import AnthropicLLM
from ..convert.markdown import MarkdownConverter


class OnboardingAction(Enum):
    """Actions available during onboarding"""
    LINK = "link"  # Link to existing OneDrive document
    PUBLISH = "publish"  # Publish as new document
    SKIP = "skip"  # Skip for now
    IGNORE = "ignore"  # Permanently ignore
    DOWNLOAD = "download"  # Download from OneDrive
    REPLACE = "replace"  # Replace OneDrive version
    MERGE = "merge"  # Merge changes
    MANUAL = "manual"  # Require manual intervention


@dataclass
class DocumentMatch:
    """Represents a potential match between local and OneDrive documents"""
    local_path: Optional[Path] = None
    onedrive_path: Optional[str] = None
    onedrive_id: Optional[str] = None
    similarity_score: float = 0.0
    match_criteria: List[str] = field(default_factory=list)
    last_modified_local: Optional[datetime] = None
    last_modified_onedrive: Optional[datetime] = None
    onedrive_author: Optional[str] = None
    content_hash_local: Optional[str] = None
    content_hash_onedrive: Optional[str] = None


@dataclass
class DocumentNode:
    """Node in the document graph for traversal"""
    path: Path
    title: str
    outgoing_links: Set[str] = field(default_factory=set)
    incoming_links: Set[str] = field(default_factory=set)
    link_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_preview: str = ""
    frontmatter: Dict[str, Any] = field(default_factory=dict)


class IntelligentOnboarder:
    """
    Intelligent document onboarding system that:
    1. Discovers all documents in repository
    2. Analyzes link structure to find root documents
    3. Matches with existing OneDrive documents
    4. Provides interactive or automated onboarding
    """
    
    def __init__(
        self,
        repository_root: Path,
        storage_provider: Optional[OneDriveStorage] = None,
        llm_provider: Optional[AnthropicLLM] = None,
        config_path: Optional[Path] = None
    ):
        self.repository_root = Path(repository_root)
        self.storage = storage_provider
        self.llm = llm_provider
        self.console = Console()
        
        # Document graph for link analysis
        self.doc_graph = nx.DiGraph()
        self.documents: Dict[str, DocumentNode] = {}
        
        # Onboarding state
        self.decisions: Dict[str, OnboardingAction] = {}
        self.matches: Dict[str, DocumentMatch] = {}
        
        # Configuration
        self.config = self._load_config(config_path) if config_path else {}
        
        # Statistics
        self.stats = {
            'discovered': 0,
            'linked': 0,
            'published': 0,
            'skipped': 0,
            'errors': 0,
            'downloaded': 0
        }
    
    def _load_config(self, config_path: Path) -> Dict:
        """Load configuration from file"""
        if config_path.suffix == '.yaml':
            with open(config_path) as f:
                return yaml.safe_load(f)
        elif config_path.suffix == '.json':
            with open(config_path) as f:
                return json.load(f)
        return {}
    
    async def discover_documents(
        self,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None
    ) -> List[DocumentNode]:
        """
        Discover all documents in repository
        """
        include_patterns = include_patterns or ['*.md', '*.markdown']
        exclude_patterns = exclude_patterns or [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/.docflow/**'
        ]
        
        documents = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Discovering documents...", total=None)
            
            for pattern in include_patterns:
                for file_path in self.repository_root.rglob(pattern):
                    # Check exclusions
                    if any(file_path.match(exc) for exc in exclude_patterns):
                        continue
                    
                    if file_path.is_file():
                        doc_node = await self._analyze_document(file_path)
                        if doc_node:
                            documents.append(doc_node)
                            rel_path = file_path.relative_to(self.repository_root)
                            self.documents[str(rel_path)] = doc_node
                            self.stats['discovered'] += 1
                            progress.update(
                                task,
                                description=f"Discovered {self.stats['discovered']} documents"
                            )
        
        self.console.print(
            f"\n[green]✓[/] Discovered {len(documents)} documents"
        )
        return documents
    
    async def _analyze_document(self, file_path: Path) -> Optional[DocumentNode]:
        """
        Analyze a single document for metadata and links
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse frontmatter
            post = frontmatter.loads(content)
            
            # Extract title
            title = post.metadata.get('title', '')
            if not title:
                # Try to extract from first # heading
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1) if title_match else file_path.stem
            
            # Extract links
            # Markdown links: [text](url)
            md_links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', content)
            # Wiki-style links: [[page]]
            wiki_links = re.findall(r'\[\[([^\]]+)\]\]', content)
            
            outgoing_links = set()
            for _, url in md_links:
                if not url.startswith(('http://', 'https://', '#')):
                    # Relative link
                    outgoing_links.add(url)
            
            for link in wiki_links:
                outgoing_links.add(link)
            
            # Get content preview (first paragraph)
            paragraphs = re.split(r'\n\s*\n', post.content)
            preview = paragraphs[0][:200] if paragraphs else ""
            
            # Create content hash for matching
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            return DocumentNode(
                path=file_path,
                title=title,
                outgoing_links=outgoing_links,
                metadata={
                    'size': file_path.stat().st_size,
                    'modified': file_path.stat().st_mtime,
                    'hash': content_hash
                },
                content_preview=preview,
                frontmatter=post.metadata
            )
        except Exception as e:
            self.console.print(f"[yellow]Warning:[/] Could not analyze {file_path}: {e}")
            return None
    
    def build_link_graph(self):
        """
        Build a directed graph of document links
        """
        self.console.print("\nBuilding document link graph...")
        
        # Add nodes
        for rel_path, doc in self.documents.items():
            self.doc_graph.add_node(rel_path, doc=doc)
        
        # Add edges (links between documents)
        for rel_path, doc in self.documents.items():
            for link in doc.outgoing_links:
                # Resolve link to absolute path
                link_path = self._resolve_link(doc.path.parent, link)
                if link_path:
                    target_rel = link_path.relative_to(self.repository_root)
                    target_str = str(target_rel)
                    
                    if target_str in self.documents:
                        self.doc_graph.add_edge(rel_path, target_str)
                        self.documents[target_str].incoming_links.add(rel_path)
        
        # Calculate link counts
        for rel_path, doc in self.documents.items():
            doc.link_count = (
                len(doc.outgoing_links) * 2 +  # Outgoing weighted more
                len(doc.incoming_links)
            )
        
        self.console.print(
            f"[green]✓[/] Built graph with {self.doc_graph.number_of_nodes()} nodes "
            f"and {self.doc_graph.number_of_edges()} edges"
        )
    
    def _resolve_link(self, base_dir: Path, link: str) -> Optional[Path]:
        """Resolve a relative link to absolute path"""
        if link.startswith('/'):
            # Absolute from repo root
            path = self.repository_root / link.lstrip('/')
        else:
            # Relative to current document
            path = base_dir / link
        
        # Try with .md extension if not present
        if not path.exists() and not path.suffix:
            path = path.with_suffix('.md')
        
        if path.exists():
            try:
                return path.resolve()
            except:
                pass
        return None
    
    def find_root_documents(self, top_n: int = 10) -> List[DocumentNode]:
        """
        Find the most connected documents (likely root/index documents)
        """
        # Sort by link count (outgoing * 2 + incoming)
        sorted_docs = sorted(
            self.documents.values(),
            key=lambda d: d.link_count,
            reverse=True
        )
        
        # Display top documents
        table = Table(title="Most Connected Documents (Likely Root Documents)")
        table.add_column("Rank", style="cyan", width=6)
        table.add_column("Document", style="green")
        table.add_column("Outgoing", style="yellow", width=10)
        table.add_column("Incoming", style="blue", width=10)
        table.add_column("Total Score", style="magenta", width=12)
        
        for i, doc in enumerate(sorted_docs[:top_n], 1):
            rel_path = doc.path.relative_to(self.repository_root)
            table.add_row(
                str(i),
                str(rel_path),
                str(len(doc.outgoing_links)),
                str(len(doc.incoming_links)),
                str(doc.link_count)
            )
        
        self.console.print(table)
        return sorted_docs[:top_n]
    
    async def match_with_onedrive(
        self,
        documents: Optional[List[DocumentNode]] = None
    ) -> Dict[str, List[DocumentMatch]]:
        """
        Match local documents with OneDrive documents
        """
        if not self.storage:
            self.console.print("[yellow]No storage provider configured, skipping matching[/]")
            return {}
        
        documents = documents or list(self.documents.values())
        matches = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task(
                "Matching with OneDrive...",
                total=len(documents)
            )
            
            # Get all OneDrive documents
            onedrive_docs = await self.storage.list_documents()
            
            for doc in documents:
                rel_path = str(doc.path.relative_to(self.repository_root))
                doc_matches = []
                
                for od_doc in onedrive_docs:
                    match = self._calculate_match(doc, od_doc)
                    if match.similarity_score > 0.5:  # Threshold
                        doc_matches.append(match)
                
                # Sort by similarity
                doc_matches.sort(key=lambda m: m.similarity_score, reverse=True)
                if doc_matches:
                    matches[rel_path] = doc_matches
                
                progress.update(task, advance=1)
        
        self.matches = matches
        return matches
    
    def _calculate_match(self, local_doc: DocumentNode, onedrive_doc: Dict) -> DocumentMatch:
        """
        Calculate similarity between local and OneDrive document
        """
        match = DocumentMatch(
            local_path=local_doc.path,
            onedrive_path=onedrive_doc.get('name', ''),
            onedrive_id=onedrive_doc.get('id'),
            last_modified_onedrive=onedrive_doc.get('lastModifiedDateTime'),
            onedrive_author=onedrive_doc.get('lastModifiedBy', {}).get('user', {}).get('displayName')
        )
        
        scores = []
        criteria = []
        
        # 1. Filename similarity
        local_name = local_doc.path.stem.lower()
        od_name = Path(onedrive_doc.get('name', '')).stem.lower()
        
        # Exact match
        if local_name == od_name:
            scores.append(1.0)
            criteria.append('exact_filename')
        else:
            # Fuzzy match
            ratio = fuzz.ratio(local_name, od_name) / 100.0
            if ratio > 0.7:
                scores.append(ratio)
                criteria.append(f'fuzzy_filename_{int(ratio*100)}%')
        
        # 2. Title similarity (if available)
        if 'title' in onedrive_doc and local_doc.title:
            title_ratio = fuzz.ratio(
                local_doc.title.lower(),
                onedrive_doc['title'].lower()
            ) / 100.0
            if title_ratio > 0.7:
                scores.append(title_ratio)
                criteria.append(f'title_match_{int(title_ratio*100)}%')
        
        # 3. Path structure similarity
        local_parts = local_doc.path.relative_to(self.repository_root).parts[:-1]
        od_path = onedrive_doc.get('parentReference', {}).get('path', '')
        if local_parts and od_path:
            path_match = all(part in od_path for part in local_parts)
            if path_match:
                scores.append(0.8)
                criteria.append('path_structure')
        
        # Calculate weighted average
        if scores:
            match.similarity_score = sum(scores) / len(scores)
            match.match_criteria = criteria
        
        return match
    
    async def interactive_onboard(
        self,
        start_from: Optional[str] = None,
        auto_mode: bool = False
    ):
        """
        Interactive onboarding process
        """
        # Determine starting document
        if not start_from:
            root_docs = self.find_root_documents(5)
            if root_docs:
                choices = [
                    str(doc.path.relative_to(self.repository_root))
                    for doc in root_docs
                ]
                start_from = Prompt.ask(
                    "\nSelect starting document",
                    choices=choices,
                    default=choices[0]
                )
        
        if not start_from or start_from not in self.documents:
            self.console.print("[red]Invalid starting document[/]")
            return
        
        # Traverse graph from starting document
        visited = set()
        queue = [start_from]
        
        self.console.print(f"\n[bold]Starting onboarding from: {start_from}[/]\n")
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            
            visited.add(current)
            doc = self.documents[current]
            
            # Get matches for this document
            doc_matches = self.matches.get(current, [])
            
            # Make decision
            if auto_mode:
                action = self._auto_decide(doc, doc_matches)
            else:
                action = await self._interactive_decide(doc, doc_matches)
            
            self.decisions[current] = action
            
            # Process action
            await self._process_action(doc, doc_matches, action)
            
            # Add linked documents to queue
            for link in doc.outgoing_links:
                link_path = self._resolve_link(doc.path.parent, link)
                if link_path:
                    rel_path = str(link_path.relative_to(self.repository_root))
                    if rel_path in self.documents and rel_path not in visited:
                        queue.append(rel_path)
        
        # Show summary
        self._show_summary()
    
    async def _interactive_decide(
        self,
        doc: DocumentNode,
        matches: List[DocumentMatch]
    ) -> OnboardingAction:
        """
        Interactive decision for a single document
        """
        rel_path = doc.path.relative_to(self.repository_root)
        
        # Create display panel
        panel_content = f"[bold]{rel_path}[/]\n"
        panel_content += f"Title: {doc.title}\n"
        panel_content += f"Links: {len(doc.outgoing_links)} out, {len(doc.incoming_links)} in\n"
        
        if doc.content_preview:
            panel_content += f"\n[dim]{doc.content_preview}[/]"
        
        self.console.print(Panel(panel_content, title="Document"))
        
        # Show matches if any
        if matches:
            match_table = Table(title="OneDrive Matches")
            match_table.add_column("File", style="cyan")
            match_table.add_column("Similarity", style="yellow")
            match_table.add_column("Modified", style="blue")
            match_table.add_column("Author", style="green")
            
            for m in matches[:3]:  # Show top 3
                match_table.add_row(
                    m.onedrive_path or "Unknown",
                    f"{m.similarity_score:.1%}",
                    str(m.last_modified_onedrive)[:10] if m.last_modified_onedrive else "Unknown",
                    m.onedrive_author or "Unknown"
                )
            
            self.console.print(match_table)
            
            # Offer choices based on match quality
            best_match = matches[0]
            if best_match.similarity_score > 0.9:
                self.console.print("[green]✓ High confidence match found[/]")
                choices = {
                    'l': 'Link to existing',
                    'p': 'Publish as new',
                    's': 'Skip',
                    'r': 'Replace OneDrive version'
                }
            elif best_match.similarity_score > 0.7:
                self.console.print("[yellow]⚠ Possible match found (review recommended)[/]")
                choices = {
                    'l': 'Link to existing',
                    'p': 'Publish as new',
                    'm': 'Merge changes',
                    's': 'Skip',
                    'r': 'Replace OneDrive version'
                }
            else:
                self.console.print("[blue]ℹ Weak match - likely different document[/]")
                choices = {
                    'p': 'Publish as new',
                    'l': 'Link anyway',
                    's': 'Skip',
                    'i': 'Ignore permanently'
                }
        else:
            self.console.print("[yellow]No OneDrive matches found[/]")
            choices = {
                'p': 'Publish as new',
                's': 'Skip',
                'i': 'Ignore permanently'
            }
        
        # Show choices
        choice_text = " | ".join([f"[{k}]{v}" for k, v in choices.items()])
        choice = Prompt.ask(f"\nAction? {choice_text}", choices=list(choices.keys()))
        
        # Map choice to action
        action_map = {
            'l': OnboardingAction.LINK,
            'p': OnboardingAction.PUBLISH,
            's': OnboardingAction.SKIP,
            'i': OnboardingAction.IGNORE,
            'r': OnboardingAction.REPLACE,
            'm': OnboardingAction.MERGE
        }
        
        return action_map.get(choice, OnboardingAction.SKIP)
    
    def _auto_decide(
        self,
        doc: DocumentNode,
        matches: List[DocumentMatch]
    ) -> OnboardingAction:
        """
        Automatic decision based on rules
        """
        if not matches:
            return OnboardingAction.PUBLISH
        
        best_match = matches[0]
        
        # Decision matrix
        if best_match.similarity_score > 0.95:
            return OnboardingAction.LINK  # Nearly identical
        elif best_match.similarity_score > 0.8:
            # Check dates
            if doc.metadata.get('modified', 0) > best_match.last_modified_onedrive.timestamp():
                return OnboardingAction.REPLACE  # Local is newer
            else:
                return OnboardingAction.LINK  # OneDrive is newer
        elif best_match.similarity_score > 0.6:
            return OnboardingAction.MERGE  # Similar but different
        else:
            return OnboardingAction.PUBLISH  # Too different
    
    async def _process_action(
        self,
        doc: DocumentNode,
        matches: List[DocumentMatch],
        action: OnboardingAction
    ):
        """
        Process the onboarding action for a document
        """
        rel_path = str(doc.path.relative_to(self.repository_root))
        
        if action == OnboardingAction.LINK:
            if matches:
                # Link to best match
                best_match = matches[0]
                self.console.print(
                    f"[green]✓[/] Linked {rel_path} to {best_match.onedrive_path}"
                )
                self.stats['linked'] += 1
                
                # TODO: Update database with link
                
        elif action == OnboardingAction.PUBLISH:
            self.console.print(f"[blue]📝[/] Marked {rel_path} for publishing")
            self.stats['published'] += 1
            
            # TODO: Queue for publishing
            
        elif action == OnboardingAction.SKIP:
            self.console.print(f"[yellow]⏭[/] Skipped {rel_path}")
            self.stats['skipped'] += 1
            
        elif action == OnboardingAction.REPLACE:
            self.console.print(f"[orange]🔄[/] Will replace OneDrive version of {rel_path}")
            # TODO: Queue for replacement
            
        elif action == OnboardingAction.MERGE:
            self.console.print(f"[purple]🔀[/] Will merge {rel_path}")
            # TODO: Queue for merge
            
        elif action == OnboardingAction.DOWNLOAD:
            if matches:
                self.console.print(f"[cyan]⬇[/] Downloaded {rel_path} from OneDrive")
                self.stats['downloaded'] += 1
                # TODO: Download file
    
    def _show_summary(self):
        """
        Show onboarding summary
        """
        self.console.print("\n" + "="*60)
        self.console.print("[bold]Onboarding Summary[/]")
        self.console.print("="*60)
        
        summary_table = Table(show_header=False)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Count", style="yellow")
        summary_table.add_column("Percentage", style="green")
        
        total = self.stats['discovered']
        for key, value in self.stats.items():
            if key != 'discovered':
                percentage = (value / total * 100) if total > 0 else 0
                summary_table.add_row(
                    key.capitalize(),
                    str(value),
                    f"{percentage:.1f}%"
                )
        
        self.console.print(summary_table)
        
        # Show next steps
        self.console.print("\n[bold]Next Steps:[/]")
        if self.stats['published'] > 0:
            self.console.print(f"1. Publish {self.stats['published']} new documents: docflow publish --all-drafts")
        if self.stats['linked'] > 0:
            self.console.print(f"2. Verify {self.stats['linked']} linked documents: docflow check-links")
        if self.stats['skipped'] > 0:
            self.console.print(f"3. Review {self.stats['skipped']} skipped documents: docflow onboard review-skipped")
    
    async def bulk_onboard(
        self,
        strategy: str = "smart",
        threshold: float = 0.8
    ):
        """
        Bulk onboard all documents with a specific strategy
        """
        self.console.print(f"\n[bold]Bulk onboarding with strategy: {strategy}[/]\n")
        
        for rel_path, doc in self.documents.items():
            matches = self.matches.get(rel_path, [])
            
            if strategy == "exact-match":
                # Only link if exact filename match
                if matches and matches[0].similarity_score == 1.0:
                    action = OnboardingAction.LINK
                else:
                    action = OnboardingAction.PUBLISH
                    
            elif strategy == "fuzzy":
                # Link if above threshold
                if matches and matches[0].similarity_score >= threshold:
                    action = OnboardingAction.LINK
                else:
                    action = OnboardingAction.PUBLISH
                    
            elif strategy == "publish-all":
                # Publish everything as new
                action = OnboardingAction.PUBLISH
                
            elif strategy == "smart":
                # Use automatic decision logic
                action = self._auto_decide(doc, matches)
            
            else:
                action = OnboardingAction.SKIP
            
            self.decisions[rel_path] = action
            await self._process_action(doc, matches, action)
        
        self._show_summary()
    
    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """
        Generate detailed onboarding report
        """
        report = []
        report.append("# DocFlow Onboarding Report")
        report.append(f"\nGenerated: {datetime.now().isoformat()}")
        report.append(f"Repository: {self.repository_root}")
        
        # Statistics
        report.append("\n## Statistics\n")
        report.append(f"- Total documents discovered: {self.stats['discovered']}")
        report.append(f"- Documents linked: {self.stats['linked']}")
        report.append(f"- Documents to publish: {self.stats['published']}")
        report.append(f"- Documents skipped: {self.stats['skipped']}")
        report.append(f"- Documents downloaded: {self.stats['downloaded']}")
        
        # Link analysis
        report.append("\n## Link Analysis\n")
        if self.doc_graph.number_of_nodes() > 0:
            report.append(f"- Total nodes: {self.doc_graph.number_of_nodes()}")
            report.append(f"- Total edges: {self.doc_graph.number_of_edges()}")
            
            # Find disconnected documents
            disconnected = [
                node for node in self.doc_graph.nodes()
                if self.doc_graph.degree(node) == 0
            ]
            if disconnected:
                report.append(f"\n### Disconnected Documents ({len(disconnected)}):\n")
                for doc_path in disconnected[:10]:
                    report.append(f"- {doc_path}")
            
            # Find broken links
            broken_links = []
            for rel_path, doc in self.documents.items():
                for link in doc.outgoing_links:
                    link_path = self._resolve_link(doc.path.parent, link)
                    if not link_path or not link_path.exists():
                        broken_links.append((rel_path, link))
            
            if broken_links:
                report.append(f"\n### Broken Links ({len(broken_links)}):\n")
                for source, target in broken_links[:20]:
                    report.append(f"- {source} → {target}")
        
        # Decisions made
        report.append("\n## Onboarding Decisions\n")
        
        for action in OnboardingAction:
            docs_with_action = [
                path for path, a in self.decisions.items()
                if a == action
            ]
            if docs_with_action:
                report.append(f"\n### {action.value.capitalize()} ({len(docs_with_action)}):\n")
                for doc_path in docs_with_action[:20]:
                    report.append(f"- {doc_path}")
        
        # Join report
        report_text = "\n".join(report)
        
        # Save if path provided
        if output_path:
            output_path.write_text(report_text)
            self.console.print(f"\n[green]Report saved to: {output_path}[/]")
        
        return report_text


# CLI Commands
@click.group()
def onboard():
    """Intelligent document onboarding commands"""
    pass


@onboard.command()
@click.argument('repository_path', type=click.Path(exists=True, path_type=Path))
@click.option('--recursive', is_flag=True, help='Recursively discover documents')
@click.option('--include', multiple=True, help='Include patterns (e.g., *.md)')
@click.option('--exclude', multiple=True, help='Exclude patterns (e.g., node_modules)')
def discover(repository_path: Path, recursive: bool, include: List[str], exclude: List[str]):
    """Discover documents in repository"""
    onboarder = IntelligentOnboarder(repository_path)
    asyncio.run(onboarder.discover_documents(include, exclude))
    onboarder.build_link_graph()
    onboarder.find_root_documents()


@onboard.command()
@click.argument('repository_path', type=click.Path(exists=True, path_type=Path))
@click.option('--root', help='Root document to start from')
@click.option('--auto', is_flag=True, help='Automatic mode (no prompts)')
def start(repository_path: Path, root: Optional[str], auto: bool):
    """Start interactive onboarding"""
    onboarder = IntelligentOnboarder(repository_path)
    
    async def run():
        await onboarder.discover_documents()
        onboarder.build_link_graph()
        await onboarder.match_with_onedrive()
        await onboarder.interactive_onboard(root, auto)
    
    asyncio.run(run())


@onboard.command()
@click.argument('repository_path', type=click.Path(exists=True, path_type=Path))
@click.option('--strategy', type=click.Choice(['exact-match', 'fuzzy', 'smart', 'publish-all']), default='smart')
@click.option('--threshold', type=float, default=0.8, help='Similarity threshold for fuzzy matching')
def bulk(repository_path: Path, strategy: str, threshold: float):
    """Bulk onboard all documents"""
    onboarder = IntelligentOnboarder(repository_path)
    
    async def run():
        await onboarder.discover_documents()
        onboarder.build_link_graph()
        await onboarder.match_with_onedrive()
        await onboarder.bulk_onboard(strategy, threshold)
    
    asyncio.run(run())


@onboard.command()
@click.argument('repository_path', type=click.Path(exists=True, path_type=Path))
@click.option('--output', type=click.Path(path_type=Path), help='Output path for report')
def report(repository_path: Path, output: Optional[Path]):
    """Generate onboarding report"""
    onboarder = IntelligentOnboarder(repository_path)
    
    async def run():
        await onboarder.discover_documents()
        onboarder.build_link_graph()
        await onboarder.match_with_onedrive()
        report_text = onboarder.generate_report(output)
        if not output:
            console = Console()
            console.print(Markdown(report_text))
    
    asyncio.run(run())


if __name__ == "__main__":
    onboard()