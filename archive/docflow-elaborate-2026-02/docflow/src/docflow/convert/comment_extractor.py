"""Extract comments and tracked changes from DOCX files."""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CommentRange:
    """Range of text that a comment refers to."""
    
    paragraph_index: int
    run_index: int
    text: str


class DocxCommentExtractor:
    """Extract comments from DOCX files (word/comments.xml)."""
    
    # XML namespaces
    NAMESPACES = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
        'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    }
    
    def __init__(self, docx_path: Path):
        """Initialize with a DOCX file path."""
        self.docx_path = docx_path
        self.comments = []
        self.document_xml = None
        self.comments_xml = None
    
    def extract(self) -> list[dict]:
        """Extract all comments from the DOCX file.
        
        Returns:
            List of comment dicts with fields:
            - id: Comment ID
            - author: Comment author
            - date: Timestamp (ISO format)
            - text: Comment text
            - context: Surrounding text for context
            - initials: Author initials
            - resolved: Whether comment is marked resolved
        """
        if not self.docx_path.exists():
            logger.error(f"DOCX file not found: {self.docx_path}")
            return []
        
        try:
            with ZipFile(self.docx_path, 'r') as docx:
                # Load document.xml and comments.xml
                if 'word/document.xml' in docx.namelist():
                    self.document_xml = docx.read('word/document.xml').decode('utf-8')
                
                if 'word/comments.xml' in docx.namelist():
                    self.comments_xml = docx.read('word/comments.xml').decode('utf-8')
                else:
                    logger.debug(f"No comments in {self.docx_path}")
                    return []
            
            # Parse comments
            return self._parse_comments()
        
        except Exception as e:
            logger.error(f"Failed to extract comments from {self.docx_path}: {e}")
            return []
    
    def _parse_comments(self) -> list[dict]:
        """Parse comments.xml and extract comment data."""
        if not self.comments_xml:
            return []
        
        try:
            root = ET.fromstring(self.comments_xml)
            comments = []
            
            for comment_elem in root.findall('.//w:comment', self.NAMESPACES):
                comment_id = comment_elem.get(f"{{{self.NAMESPACES['w']}}}id")
                author = comment_elem.get(f"{{{self.NAMESPACES['w']}}}author")
                date_str = comment_elem.get(f"{{{self.NAMESPACES['w']}}}date")
                initials = comment_elem.get(f"{{{self.NAMESPACES['w']}}}initials")
                
                # Extract comment text (can be multiple paragraphs)
                text = self._extract_element_text(comment_elem)
                
                # Try to get surrounding context from document
                context = self._get_comment_context(comment_id) if self.document_xml else ""
                
                # Check if resolved (word 2013+)
                resolved_elem = comment_elem.find('.//w14:resolved', self.NAMESPACES)
                resolved = resolved_elem is not None and resolved_elem.get('w14:val', '').lower() == 'true' \
                    if resolved_elem is not None else False
                
                comments.append({
                    'id': comment_id or '',
                    'author': author or initials or 'Unknown',
                    'date': date_str or datetime.now().isoformat(),
                    'initials': initials or '',
                    'text': text.strip(),
                    'context': context,
                    'resolved': resolved,
                })
            
            return comments
        
        except Exception as e:
            logger.error(f"Failed to parse comments XML: {e}")
            return []
    
    def _extract_element_text(self, element: ET.Element) -> str:
        """Extract all text from an element and its children."""
        text_parts = []
        
        # Find all text elements (w:t)
        for t_elem in element.findall('.//w:t', self.NAMESPACES):
            if t_elem.text:
                text_parts.append(t_elem.text)
        
        # Handle line breaks (w:br)
        for br_elem in element.findall('.//w:br', self.NAMESPACES):
            # Find position and insert newline
            text_parts.append('\n')
        
        return ''.join(text_parts)
    
    def _get_comment_context(self, comment_id: str) -> str:
        """Extract surrounding text from document that comment refers to.
        
        Comments reference ranges using comment start/end markers.
        """
        if not self.document_xml or not comment_id:
            return ""
        
        try:
            # Parse document XML
            doc_root = ET.fromstring(self.document_xml)
            
            # Find comment range markers: commentRangeStart and commentRangeEnd
            # These mark the text that the comment applies to
            context_parts = []
            
            # Look for commentRangeStart with matching id
            for elem in doc_root.findall(f'.//w:commentRangeStart[@w:id="{comment_id}"]', 
                                        self.NAMESPACES):
                # Get following sibling paragraphs until commentRangeEnd
                in_range = False
                for sibling in self._iter_following_siblings(elem):
                    if sibling.tag == f"{{{self.NAMESPACES['w']}}}commentRangeStart":
                        if sibling.get(f"{{{self.NAMESPACES['w']}}}id") == comment_id:
                            in_range = True
                    elif sibling.tag == f"{{{self.NAMESPACES['w']}}}commentRangeEnd":
                        if sibling.get(f"{{{self.NAMESPACES['w']}}}id") == comment_id:
                            break
                    elif in_range:
                        context_parts.append(self._extract_element_text(sibling))
            
            return ''.join(context_parts)[:200]  # Limit to 200 chars
        
        except Exception as e:
            logger.debug(f"Failed to extract comment context: {e}")
            return ""
    
    def _iter_following_siblings(self, element: ET.Element):
        """Iterate over following sibling elements."""
        parent_map = {c: p for p in element.iter() for c in p}
        parent = parent_map.get(element)
        
        if parent is None:
            return
        
        found = False
        for sibling in parent:
            if found:
                yield sibling
            if sibling == element:
                found = True


class TrackChangesExtractor:
    """Extract tracked changes (revisions) from DOCX files."""
    
    NAMESPACES = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    }
    
    def __init__(self, docx_path: Path):
        """Initialize with a DOCX file path."""
        self.docx_path = docx_path
    
    def extract(self) -> list[dict]:
        """Extract all tracked changes from the DOCX file.
        
        Returns:
            List of change dicts with fields:
            - type: 'insert', 'delete', 'format'
            - author: Who made the change
            - date: When
            - text: What was changed
        """
        if not self.docx_path.exists():
            return []
        
        try:
            with ZipFile(self.docx_path, 'r') as docx:
                if 'word/document.xml' not in docx.namelist():
                    return []
                
                doc_xml = docx.read('word/document.xml').decode('utf-8')
            
            root = ET.fromstring(doc_xml)
            changes = []
            
            # Extract insertions (w:ins)
            for ins in root.findall('.//w:ins', self.NAMESPACES):
                author = ins.get(f"{{{self.NAMESPACES['w']}}}author")
                date_str = ins.get(f"{{{self.NAMESPACES['w']}}}date")
                
                text = ''.join([t.text or '' for t in ins.findall('.//w:t', self.NAMESPACES)])
                
                changes.append({
                    'type': 'insert',
                    'author': author or 'Unknown',
                    'date': date_str or '',
                    'text': text,
                })
            
            # Extract deletions (w:del)
            for delelt in root.findall('.//w:del', self.NAMESPACES):
                author = delelt.get(f"{{{self.NAMESPACES['w']}}}author")
                date_str = delelt.get(f"{{{self.NAMESPACES['w']}}}date")
                
                text = ''.join([t.text or '' for t in delelt.findall('.//w:t', self.NAMESPACES)])
                
                changes.append({
                    'type': 'delete',
                    'author': author or 'Unknown',
                    'date': date_str or '',
                    'text': text,
                })
            
            return changes
        
        except Exception as e:
            logger.error(f"Failed to extract tracked changes: {e}")
            return []
