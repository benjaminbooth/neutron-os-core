#!/usr/bin/env python3
"""
Universal Document Converter for DocFlow

Supports conversion between multiple document formats including:
- Markdown, reStructuredText, AsciiDoc, Org Mode
- LaTeX, HTML, XML, JSON, YAML
- Word (DOCX), Google Docs, PDF
- Jupyter Notebooks, Confluence, MediaWiki
"""

import os
import json
import yaml
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import tempfile
import shutil

import pypandoc
import nbformat
from nbconvert import MarkdownExporter
from docx import Document as DocxDocument
from bs4 import BeautifulSoup
import xmltodict
from jinja2 import Template
import frontmatter
from googleapiclient.discovery import build
from google.oauth2 import service_account
import mistune
from rst2html5 import HTML5Writer
from docutils.core import publish_string


class DocumentFormat(Enum):
    """Supported document formats"""
    # Markup formats
    MARKDOWN = ("markdown", [".md", ".markdown"])
    RESTRUCTUREDTEXT = ("rst", [".rst"])
    ASCIIDOC = ("asciidoc", [".adoc", ".asciidoc"])
    ORG = ("org", [".org"])
    LATEX = ("latex", [".tex"])
    HTML = ("html", [".html", ".htm"])
    MEDIAWIKI = ("mediawiki", [".wiki"])
    
    # Data formats
    XML = ("xml", [".xml", ".dita"])
    JSON = ("json", [".json"])
    YAML = ("yaml", [".yaml", ".yml"])
    
    # Notebook formats
    JUPYTER = ("jupyter", [".ipynb"])
    
    # Office formats
    DOCX = ("docx", [".docx", ".doc"])
    GOOGLE_DOCS = ("google_docs", [])
    PDF = ("pdf", [".pdf"])
    
    # Plain text
    TEXT = ("text", [".txt"])
    
    # API-based formats
    CONFLUENCE = ("confluence", [])
    SHAREPOINT = ("sharepoint", [])
    GITHUB_WIKI = ("github_wiki", [])
    
    @classmethod
    def from_extension(cls, path: Path) -> Optional['DocumentFormat']:
        """Detect format from file extension"""
        ext = path.suffix.lower()
        for format_type in cls:
            if ext in format_type.value[1]:
                return format_type
        return None
    
    @classmethod
    def from_string(cls, format_name: str) -> Optional['DocumentFormat']:
        """Get format from string name"""
        format_name = format_name.lower()
        for format_type in cls:
            if format_name == format_type.value[0]:
                return format_type
        return None


@dataclass
class ConversionResult:
    """Result of a document conversion"""
    success: bool
    output_path: Optional[Path]
    content: Optional[str]
    metadata: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


class UniversalConverter:
    """
    Universal document converter supporting multiple formats.
    Uses various libraries and tools for optimal conversion quality.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Initialize Google Drive service if configured
        self.google_service = self._init_google_service() if config else None
        
        # Conversion quality settings
        self.preserve_formatting = config.get("preserve_formatting", True)
        self.preserve_comments = config.get("preserve_comments", True)
        self.preserve_metadata = config.get("preserve_metadata", True)
        
        # Custom templates for structured data
        self.json_template = config.get("json_template")
        self.xml_template = config.get("xml_template")
    
    def __del__(self):
        """Cleanup temp directory"""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _init_google_service(self) -> Optional[Any]:
        """Initialize Google Drive API service"""
        try:
            creds_path = self.config.get("google_credentials_path")
            if not creds_path:
                return None
            
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=['https://www.googleapis.com/auth/drive', 
                       'https://www.googleapis.com/auth/documents']
            )
            
            return build('docs', 'v1', credentials=credentials)
        except Exception as e:
            print(f"Failed to initialize Google service: {e}")
            return None
    
    def convert(
        self,
        source_path: Path,
        target_format: DocumentFormat,
        output_path: Optional[Path] = None
    ) -> ConversionResult:
        """
        Convert document from source to target format
        """
        # Detect source format
        source_format = DocumentFormat.from_extension(source_path)
        if not source_format:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[f"Unknown source format for {source_path}"],
                warnings=[]
            )
        
        # Choose conversion path
        if source_format == target_format:
            return ConversionResult(
                success=True,
                output_path=source_path,
                content=source_path.read_text(),
                metadata={},
                errors=[],
                warnings=["Source and target formats are the same"]
            )
        
        # Route to appropriate converter
        converter_map = {
            (DocumentFormat.MARKDOWN, DocumentFormat.DOCX): self._markdown_to_docx,
            (DocumentFormat.MARKDOWN, DocumentFormat.HTML): self._markdown_to_html,
            (DocumentFormat.MARKDOWN, DocumentFormat.PDF): self._markdown_to_pdf,
            (DocumentFormat.DOCX, DocumentFormat.MARKDOWN): self._docx_to_markdown,
            (DocumentFormat.JUPYTER, DocumentFormat.MARKDOWN): self._jupyter_to_markdown,
            (DocumentFormat.RESTRUCTUREDTEXT, DocumentFormat.MARKDOWN): self._rst_to_markdown,
            (DocumentFormat.LATEX, DocumentFormat.MARKDOWN): self._latex_to_markdown,
            (DocumentFormat.XML, DocumentFormat.MARKDOWN): self._xml_to_markdown,
            (DocumentFormat.JSON, DocumentFormat.MARKDOWN): self._json_to_markdown,
            (DocumentFormat.YAML, DocumentFormat.MARKDOWN): self._yaml_to_markdown,
            (DocumentFormat.HTML, DocumentFormat.MARKDOWN): self._html_to_markdown,
            (DocumentFormat.ASCIIDOC, DocumentFormat.MARKDOWN): self._asciidoc_to_markdown,
            (DocumentFormat.ORG, DocumentFormat.MARKDOWN): self._org_to_markdown,
            (DocumentFormat.MEDIAWIKI, DocumentFormat.MARKDOWN): self._mediawiki_to_markdown,
        }
        
        converter_key = (source_format, target_format)
        
        # Try direct conversion
        if converter_key in converter_map:
            return converter_map[converter_key](source_path, output_path)
        
        # Try via markdown intermediate
        if target_format != DocumentFormat.MARKDOWN:
            # First convert to markdown
            md_result = self.convert(source_path, DocumentFormat.MARKDOWN)
            if md_result.success and md_result.output_path:
                # Then convert from markdown to target
                return self.convert(md_result.output_path, target_format, output_path)
        
        # Use pandoc as fallback
        return self._pandoc_convert(source_path, source_format, target_format, output_path)
    
    def _markdown_to_docx(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert Markdown to DOCX"""
        try:
            output_path = output_path or source_path.with_suffix('.docx')
            
            # Parse markdown with frontmatter
            with open(source_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
            
            # Use pypandoc for conversion
            pypandoc.convert_file(
                str(source_path),
                'docx',
                outputfile=str(output_path),
                extra_args=['--standalone', '--preserve-tabs']
            )
            
            # Add metadata if present
            if post.metadata and self.preserve_metadata:
                doc = DocxDocument(str(output_path))
                core_props = doc.core_properties
                
                if 'title' in post.metadata:
                    core_props.title = post.metadata['title']
                if 'author' in post.metadata:
                    core_props.author = post.metadata['author']
                if 'keywords' in post.metadata:
                    core_props.keywords = ', '.join(post.metadata['keywords'])
                
                doc.save(str(output_path))
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=None,
                metadata=post.metadata,
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _docx_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert DOCX to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Extract with pypandoc
            content = pypandoc.convert_file(
                str(source_path),
                'markdown',
                extra_args=['--extract-media=.']
            )
            
            # Extract metadata
            doc = DocxDocument(str(source_path))
            metadata = {}
            
            if doc.core_properties.title:
                metadata['title'] = doc.core_properties.title
            if doc.core_properties.author:
                metadata['author'] = doc.core_properties.author
            if doc.core_properties.created:
                metadata['created'] = doc.core_properties.created.isoformat()
            
            # Extract comments if configured
            comments = []
            if self.preserve_comments:
                # Note: python-docx doesn't directly support comments
                # Would need to use XML parsing for full comment extraction
                pass
            
            # Write with frontmatter
            if metadata:
                post = frontmatter.Post(content, **metadata)
                output_path.write_text(frontmatter.dumps(post))
            else:
                output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata=metadata,
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _jupyter_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert Jupyter Notebook to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Load notebook
            with open(source_path, 'r') as f:
                notebook = nbformat.read(f, as_version=4)
            
            # Convert to markdown
            exporter = MarkdownExporter()
            body, resources = exporter.from_notebook_node(notebook)
            
            # Extract metadata
            metadata = notebook.metadata.get('docflow', {})
            if 'kernelspec' in notebook.metadata:
                metadata['kernel'] = notebook.metadata['kernelspec'].get('display_name')
            
            # Save output
            output_path.write_text(body)
            
            # Save images if any
            if 'outputs' in resources:
                images_dir = output_path.parent / (output_path.stem + "_files")
                images_dir.mkdir(exist_ok=True)
                for filename, data in resources['outputs'].items():
                    (images_dir / filename).write_bytes(data)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=body,
                metadata=metadata,
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _rst_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert reStructuredText to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Use pypandoc for high-quality conversion
            content = pypandoc.convert_file(
                str(source_path),
                'markdown',
                format='rst'
            )
            
            output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata={},
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _latex_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert LaTeX to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Use pandoc for LaTeX conversion
            content = pypandoc.convert_file(
                str(source_path),
                'markdown',
                format='latex',
                extra_args=['--wrap=preserve']
            )
            
            # Extract LaTeX metadata (title, author, etc.)
            latex_content = source_path.read_text()
            metadata = {}
            
            title_match = re.search(r'\\title\{([^}]+)\}', latex_content)
            if title_match:
                metadata['title'] = title_match.group(1)
            
            author_match = re.search(r'\\author\{([^}]+)\}', latex_content)
            if author_match:
                metadata['author'] = author_match.group(1)
            
            # Write with frontmatter
            if metadata:
                post = frontmatter.Post(content, **metadata)
                output_path.write_text(frontmatter.dumps(post))
            else:
                output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata=metadata,
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _xml_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert XML to Markdown using templates"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Parse XML
            with open(source_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            xml_dict = xmltodict.parse(xml_content)
            
            # Use custom template if provided
            if self.xml_template:
                template = Template(self.xml_template)
                content = template.render(data=xml_dict)
            else:
                # Default conversion
                content = self._xml_dict_to_markdown(xml_dict)
            
            output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata={'source_format': 'xml'},
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _json_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert JSON to Markdown using templates"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Parse JSON
            with open(source_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Use custom template if provided
            if self.json_template:
                template = Template(self.json_template)
                content = template.render(data=json_data)
            else:
                # Default conversion - pretty print as code block
                content = f"# {source_path.stem}\n\n"
                content += "```json\n"
                content += json.dumps(json_data, indent=2)
                content += "\n```\n"
                
                # Try to extract structured content
                if isinstance(json_data, dict):
                    content += "\n## Extracted Content\n\n"
                    content += self._dict_to_markdown(json_data)
            
            output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata={'source_format': 'json'},
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _yaml_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert YAML to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Parse YAML
            with open(source_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            # Convert to markdown
            content = f"# {source_path.stem}\n\n"
            
            # If it's documentation-like YAML
            if isinstance(yaml_data, dict):
                if 'title' in yaml_data:
                    content = f"# {yaml_data['title']}\n\n"
                if 'description' in yaml_data:
                    content += f"{yaml_data['description']}\n\n"
                
                content += self._dict_to_markdown(yaml_data)
            else:
                content += "```yaml\n"
                content += yaml.dump(yaml_data, default_flow_style=False)
                content += "\n```\n"
            
            output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata={'source_format': 'yaml'},
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _html_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert HTML to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Parse HTML
            with open(source_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
            
            # Extract metadata
            metadata = {}
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.string
            
            meta_author = soup.find('meta', attrs={'name': 'author'})
            if meta_author:
                metadata['author'] = meta_author.get('content')
            
            # Use pypandoc for conversion
            content = pypandoc.convert_file(
                str(source_path),
                'markdown',
                format='html'
            )
            
            # Write with frontmatter
            if metadata:
                post = frontmatter.Post(content, **metadata)
                output_path.write_text(frontmatter.dumps(post))
            else:
                output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata=metadata,
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _asciidoc_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert AsciiDoc to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Use asciidoctor to convert to HTML first
            html_path = self.temp_dir / "temp.html"
            subprocess.run([
                'asciidoctor',
                '-b', 'html5',
                '-o', str(html_path),
                str(source_path)
            ], check=True)
            
            # Then convert HTML to Markdown
            content = pypandoc.convert_file(
                str(html_path),
                'markdown',
                format='html'
            )
            
            output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata={},
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _org_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert Org Mode to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Use pandoc for Org mode
            content = pypandoc.convert_file(
                str(source_path),
                'markdown',
                format='org'
            )
            
            output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata={},
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _mediawiki_to_markdown(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert MediaWiki to Markdown"""
        try:
            output_path = output_path or source_path.with_suffix('.md')
            
            # Use pandoc for MediaWiki
            content = pypandoc.convert_file(
                str(source_path),
                'markdown',
                format='mediawiki'
            )
            
            output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata={},
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _markdown_to_html(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert Markdown to HTML"""
        try:
            output_path = output_path or source_path.with_suffix('.html')
            
            # Parse markdown
            with open(source_path, 'r') as f:
                post = frontmatter.load(f)
            
            # Convert to HTML
            markdown = mistune.create_markdown(
                plugins=['strikethrough', 'footnotes', 'table', 'task_lists']
            )
            html_content = markdown(post.content)
            
            # Create full HTML document
            html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{post.metadata.get('title', source_path.stem)}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; }}
        pre {{ background: #f4f4f4; padding: 1rem; overflow-x: auto; }}
        code {{ background: #f4f4f4; padding: 0.2rem 0.4rem; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
            
            output_path.write_text(html_template)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=html_template,
                metadata=post.metadata,
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _markdown_to_pdf(self, source_path: Path, output_path: Optional[Path]) -> ConversionResult:
        """Convert Markdown to PDF"""
        try:
            output_path = output_path or source_path.with_suffix('.pdf')
            
            # Use pypandoc with LaTeX engine
            pypandoc.convert_file(
                str(source_path),
                'pdf',
                outputfile=str(output_path),
                extra_args=['--pdf-engine=xelatex', '-V', 'geometry:margin=1in']
            )
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=None,
                metadata={},
                errors=[],
                warnings=[]
            )
        except Exception as e:
            # Fallback to HTML->PDF if LaTeX not available
            try:
                html_result = self._markdown_to_html(source_path, None)
                if html_result.success and html_result.output_path:
                    # Use wkhtmltopdf or weasyprint
                    subprocess.run([
                        'wkhtmltopdf',
                        str(html_result.output_path),
                        str(output_path)
                    ], check=True)
                    
                    return ConversionResult(
                        success=True,
                        output_path=output_path,
                        content=None,
                        metadata={},
                        errors=[],
                        warnings=["Used HTML->PDF fallback"]
                    )
            except:
                pass
            
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _pandoc_convert(
        self,
        source_path: Path,
        source_format: DocumentFormat,
        target_format: DocumentFormat,
        output_path: Optional[Path]
    ) -> ConversionResult:
        """Fallback conversion using pandoc"""
        try:
            output_path = output_path or source_path.with_suffix(
                target_format.value[1][0] if target_format.value[1] else '.txt'
            )
            
            content = pypandoc.convert_file(
                str(source_path),
                target_format.value[0],
                format=source_format.value[0]
            )
            
            if output_path:
                output_path.write_text(content)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata={},
                errors=[],
                warnings=["Used generic pandoc conversion"]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _dict_to_markdown(self, data: Dict, level: int = 2) -> str:
        """Convert dictionary to markdown structure"""
        lines = []
        
        for key, value in data.items():
            if key in ['title', 'description', 'source_format']:
                continue  # Skip already processed
            
            heading = '#' * level + f" {key.replace('_', ' ').title()}"
            lines.append(heading + "\n")
            
            if isinstance(value, dict):
                lines.append(self._dict_to_markdown(value, level + 1))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        lines.append(self._dict_to_markdown(item, level + 1))
                    else:
                        lines.append(f"- {item}")
                lines.append("")
            else:
                lines.append(f"{value}\n")
        
        return "\n".join(lines)
    
    def _xml_dict_to_markdown(self, xml_dict: Dict) -> str:
        """Convert XML dictionary to markdown"""
        lines = []
        
        # Try to extract common XML structures
        root_key = list(xml_dict.keys())[0]
        root_data = xml_dict[root_key]
        
        if '@title' in root_data:
            lines.append(f"# {root_data['@title']}\n")
        elif 'title' in root_data:
            lines.append(f"# {root_data['title']}\n")
        else:
            lines.append(f"# {root_key}\n")
        
        lines.append(self._dict_to_markdown(root_data))
        
        return "\n".join(lines)
    
    def convert_google_doc_to_markdown(self, doc_id: str, output_path: Path) -> ConversionResult:
        """Convert Google Doc to Markdown"""
        try:
            if not self.google_service:
                raise ValueError("Google service not initialized")
            
            # Get document content
            document = self.google_service.documents().get(documentId=doc_id).execute()
            
            # Extract text and convert to markdown
            content = self._google_doc_to_markdown(document)
            
            # Extract metadata
            metadata = {
                'title': document.get('title', ''),
                'documentId': doc_id
            }
            
            # Write with frontmatter
            post = frontmatter.Post(content, **metadata)
            output_path.write_text(frontmatter.dumps(post))
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                content=content,
                metadata=metadata,
                errors=[],
                warnings=[]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                output_path=None,
                content=None,
                metadata={},
                errors=[str(e)],
                warnings=[]
            )
    
    def _google_doc_to_markdown(self, document: Dict) -> str:
        """Convert Google Docs structure to Markdown"""
        lines = []
        
        for element in document.get('body', {}).get('content', []):
            if 'paragraph' in element:
                paragraph = element['paragraph']
                text = ''
                
                for elem in paragraph.get('elements', []):
                    if 'textRun' in elem:
                        run = elem['textRun']
                        run_text = run.get('content', '')
                        
                        # Apply formatting
                        style = run.get('textStyle', {})
                        if style.get('bold'):
                            run_text = f"**{run_text}**"
                        if style.get('italic'):
                            run_text = f"*{run_text}*"
                        
                        text += run_text
                
                # Handle headings
                style = paragraph.get('paragraphStyle', {})
                heading = style.get('headingId')
                if heading:
                    level = int(heading[-1]) if heading[-1].isdigit() else 1
                    text = '#' * level + ' ' + text
                
                lines.append(text)
            
            elif 'table' in element:
                # Convert tables
                lines.append("\n| " + " | ".join(["Cell"] * 3) + " |")
                lines.append("|" + "---|" * 3)
                # Would need to parse table structure
                lines.append("| ... | ... | ... |\n")
        
        return '\n'.join(lines)


def batch_convert(
    source_dir: Path,
    target_format: DocumentFormat,
    output_dir: Optional[Path] = None,
    recursive: bool = True
) -> List[ConversionResult]:
    """
    Batch convert all documents in a directory
    """
    converter = UniversalConverter()
    results = []
    
    pattern = "**/*" if recursive else "*"
    
    for source_path in source_dir.glob(pattern):
        if source_path.is_file():
            source_format = DocumentFormat.from_extension(source_path)
            if source_format:
                if output_dir:
                    relative = source_path.relative_to(source_dir)
                    output_path = output_dir / relative.with_suffix(
                        target_format.value[1][0] if target_format.value[1] else '.md'
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    output_path = None
                
                result = converter.convert(source_path, target_format, output_path)
                results.append(result)
                
                if result.success:
                    print(f"✓ Converted {source_path}")
                else:
                    print(f"✗ Failed {source_path}: {result.errors}")
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: universal_converter.py <source_file> <target_format>")
        sys.exit(1)
    
    source = Path(sys.argv[1])
    target_format = DocumentFormat.from_string(sys.argv[2])
    
    if not target_format:
        print(f"Unknown target format: {sys.argv[2]}")
        sys.exit(1)
    
    converter = UniversalConverter()
    result = converter.convert(source, target_format)
    
    if result.success:
        print(f"Success! Output: {result.output_path}")
    else:
        print(f"Failed: {result.errors}")