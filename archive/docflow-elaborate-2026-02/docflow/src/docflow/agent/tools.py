"""
DocFlow Agent Tools

Tools available to the DocFlowAgent for document operations.
Each tool is self-contained and handles its own errors.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .core import Tool
from ..rag.pgvector import Collection

if TYPE_CHECKING:
    from .core import DocFlowAgent


def get_docflow_tools(agent: "DocFlowAgent") -> List[Tool]:
    """Build and return all DocFlow tools"""
    
    # === Search Tools ===
    
    async def search_documents(
        query: str,
        collection: Optional[str] = None,
        project: Optional[str] = None,
        author: Optional[str] = None,
        workflow_stage: Optional[str] = None,
        k: int = 10
    ) -> Dict[str, Any]:
        """
        Search for documents across all collections.
        
        Args:
            query: Natural language search query
            collection: Filter by collection (personal, team, code, etc.)
            project: Filter by project name
            author: Filter by author
            workflow_stage: Filter by workflow stage (requirement, prd, design, spec)
            k: Maximum number of results
        """
        filters = {}
        if project:
            filters['project'] = project
        if author:
            filters['author'] = author
        if workflow_stage:
            filters['workflow_stage'] = workflow_stage
        
        coll = Collection(collection) if collection else None
        
        results = await agent._retriever.retrieve_hybrid(
            query=query,
            k=k,
            collection=coll,
            filters=filters if filters else None
        )
        
        return {
            "count": len(results),
            "documents": [
                {
                    "doc_id": r.chunk.doc_id,
                    "title": r.chunk.metadata.get('title', 'Untitled'),
                    "content_preview": r.chunk.content[:300] + "..." if len(r.chunk.content) > 300 else r.chunk.content,
                    "author": r.chunk.metadata.get('author'),
                    "project": r.chunk.metadata.get('project'),
                    "workflow_stage": r.chunk.metadata.get('workflow_stage'),
                    "state": r.chunk.metadata.get('state'),
                    "score": round(r.combined_score, 3),
                    "highlights": r.highlights
                }
                for r in results
            ]
        }
    
    async def get_document(
        doc_id: str,
        include_full_content: bool = False
    ) -> Dict[str, Any]:
        """
        Get a specific document by ID.
        
        Args:
            doc_id: Document ID
            include_full_content: Whether to include full content (vs summary)
        """
        # Search for this specific document
        results = await agent._store.search_dense(
            query_embedding=await agent._embedder.embed("document content"),
            k=100,
            filters={'doc_id': doc_id}
        )
        
        if not results:
            return {"error": f"Document not found: {doc_id}"}
        
        # Combine all chunks
        chunks = sorted(results, key=lambda r: r.chunk.chunk_index)
        
        if include_full_content:
            full_content = "\n\n".join(r.chunk.content for r in chunks)
        else:
            # Just first chunk as preview
            full_content = chunks[0].chunk.content
        
        return {
            "doc_id": doc_id,
            "title": chunks[0].chunk.metadata.get('title'),
            "author": chunks[0].chunk.metadata.get('author'),
            "project": chunks[0].chunk.metadata.get('project'),
            "workflow_stage": chunks[0].chunk.metadata.get('workflow_stage'),
            "state": chunks[0].chunk.metadata.get('state'),
            "chunk_count": len(chunks),
            "content": full_content
        }
    
    async def get_related_documents(
        doc_id: str,
        relationship_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find documents related to a given document.
        
        Args:
            doc_id: Source document ID
            relationship_type: Filter by type (references, supersedes, implements, derived_from)
        """
        rel_types = [relationship_type] if relationship_type else None
        
        related = await agent._store.get_related_documents(
            doc_id=doc_id,
            relationship_types=rel_types,
            direction="both"
        )
        
        return {
            "source_doc_id": doc_id,
            "count": len(related),
            "relationships": [
                {
                    "direction": "outgoing" if r['source_doc_id'] == doc_id else "incoming",
                    "related_doc_id": r['target_doc_id'] if r['source_doc_id'] == doc_id else r['source_doc_id'],
                    "relationship_type": r['relationship_type'],
                    "related_doc_title": r['related_doc'].get('title'),
                    "related_doc_stage": r['related_doc'].get('workflow_stage')
                }
                for r in related
            ]
        }
    
    async def get_workflow_chain(
        doc_id: str,
        direction: str = "both"
    ) -> Dict[str, Any]:
        """
        Get the workflow chain for a document.
        Traces requirement → PRD → design → spec relationships.
        
        Args:
            doc_id: Document ID to trace from
            direction: "upstream" (to requirements), "downstream" (to specs), or "both"
        """
        chain = await agent._store.get_workflow_chain(doc_id, direction)
        
        return {
            "root_doc_id": doc_id,
            "direction": direction,
            "chain": [
                {
                    "doc_id": d['doc_id'],
                    "title": d['title'],
                    "workflow_stage": d['workflow_stage'],
                    "depth": d['depth'],  # Negative = upstream, positive = downstream
                    "direction": d['direction']
                }
                for d in chain
            ]
        }
    
    # === Document Creation Tools ===
    
    async def create_document(
        title: str,
        doc_type: str,
        project: Optional[str] = None,
        template: Optional[str] = None,
        parent_doc_id: Optional[str] = None,
        initial_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new document.
        
        Args:
            title: Document title
            doc_type: Type (requirement, prd, design, spec, note, meeting)
            project: Project name
            template: Template to use (technical, meeting_notes, requirement, prd)
            parent_doc_id: Parent document ID (for workflow chains)
            initial_content: Optional initial content
        """
        # Generate document ID
        import uuid
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # Map doc_type to workflow_stage
        workflow_stage = doc_type if doc_type in ['requirement', 'prd', 'design', 'spec'] else None
        
        # Generate content from template or use provided
        if initial_content:
            content = initial_content
        elif template:
            content = _get_template_content(template, title, project)
        else:
            content = f"# {title}\n\n*Created: {datetime.now().isoformat()}*\n\n## Overview\n\n"
        
        # For now, return the document info
        # In production, this would create the file and index it
        return {
            "status": "created",
            "doc_id": doc_id,
            "title": title,
            "doc_type": doc_type,
            "workflow_stage": workflow_stage,
            "project": project,
            "parent_doc_id": parent_doc_id,
            "template_used": template,
            "content_preview": content[:500],
            "next_steps": [
                "Edit the document to add content",
                "Run 'docflow index' to update search index",
                f"Advance to review with 'docflow state advance {doc_id}'"
            ]
        }
    
    async def generate_diagram(
        description: str,
        diagram_type: str = "flowchart",
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a diagram using AI.
        
        Args:
            description: Natural language description of the diagram
            diagram_type: Type (flowchart, sequence, architecture, er, state)
            style: Optional style preset
        """
        # This would call the diagram intelligence system
        # For now, return a placeholder
        return {
            "status": "generated",
            "diagram_type": diagram_type,
            "description": description,
            "output_format": "svg",
            "message": "Diagram generation would be handled by DiagramIntelligence module",
            "suggested_filename": f"diagram_{diagram_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.svg"
        }
    
    # === Review Tools ===
    
    async def get_document_reviews(
        doc_id: str
    ) -> Dict[str, Any]:
        """
        Get review status and comments for a document.
        
        Args:
            doc_id: Document ID
        """
        # This would integrate with the review system
        return {
            "doc_id": doc_id,
            "status": "Review information would come from ReviewManager",
            "message": "Connect to review system for actual review data"
        }
    
    async def request_review(
        doc_id: str,
        reviewers: List[str],
        deadline_days: int = 7,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request a review for a document.
        
        Args:
            doc_id: Document ID
            reviewers: List of reviewer emails
            deadline_days: Days until deadline
            message: Optional message to reviewers
        """
        return {
            "status": "review_requested",
            "doc_id": doc_id,
            "reviewers": reviewers,
            "deadline": (datetime.now().date() + __import__('datetime').timedelta(days=deadline_days)).isoformat(),
            "message": message
        }
    
    # === Summarization Tools ===
    
    async def summarize_documents(
        doc_ids: List[str] = None,
        query: str = None,
        max_docs: int = 5
    ) -> Dict[str, Any]:
        """
        Summarize one or more documents.
        
        Args:
            doc_ids: Specific document IDs to summarize
            query: Or search query to find documents to summarize
            max_docs: Maximum documents to include
        """
        # Gather documents
        if doc_ids:
            docs = [await get_document(doc_id, include_full_content=True) for doc_id in doc_ids[:max_docs]]
        elif query:
            search_results = await search_documents(query, k=max_docs)
            docs = [await get_document(d['doc_id'], include_full_content=True) for d in search_results['documents']]
        else:
            return {"error": "Either doc_ids or query must be provided"}
        
        # For now, return the documents for the LLM to summarize
        return {
            "document_count": len(docs),
            "documents": [
                {
                    "doc_id": d['doc_id'],
                    "title": d['title'],
                    "content": d['content'][:2000]  # Limit for context
                }
                for d in docs if 'error' not in d
            ],
            "instruction": "Summarize these documents, highlighting key points and relationships"
        }
    
    # === Search by Metadata ===
    
    async def search_by_author(
        author: str,
        k: int = 10
    ) -> Dict[str, Any]:
        """
        Find documents by author.
        
        Args:
            author: Author name or email
            k: Maximum results
        """
        return await search_documents(query="*", author=author, k=k)
    
    async def search_by_project(
        project: str,
        k: int = 10
    ) -> Dict[str, Any]:
        """
        Find documents by project.
        
        Args:
            project: Project name
            k: Maximum results
        """
        return await search_documents(query="*", project=project, k=k)
    
    async def search_workflow_stage(
        stage: str,
        project: Optional[str] = None,
        k: int = 10
    ) -> Dict[str, Any]:
        """
        Find documents at a specific workflow stage.
        
        Args:
            stage: Workflow stage (requirement, prd, design, spec)
            project: Optional project filter
            k: Maximum results
        """
        return await search_documents(
            query="*",
            workflow_stage=stage,
            project=project,
            k=k
        )
    
    async def find_requirements_for_spec(
        spec_doc_id: str
    ) -> Dict[str, Any]:
        """
        Trace a spec back to its originating requirements.
        
        Args:
            spec_doc_id: Specification document ID
        """
        return await get_workflow_chain(spec_doc_id, direction="upstream")
    
    async def find_specs_for_requirement(
        requirement_doc_id: str
    ) -> Dict[str, Any]:
        """
        Find all specs that implement a requirement.
        
        Args:
            requirement_doc_id: Requirement document ID
        """
        return await get_workflow_chain(requirement_doc_id, direction="downstream")
    
    # === Build Tool List ===
    
    tools = [
        Tool(
            name="search_documents",
            description="Search for documents using natural language. Supports filtering by collection, project, author, and workflow stage.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "collection": {"type": "string", "enum": ["personal", "team", "code", "meeting", "requirements", "prd", "design", "spec"], "description": "Filter by collection"},
                    "project": {"type": "string", "description": "Filter by project name"},
                    "author": {"type": "string", "description": "Filter by author"},
                    "workflow_stage": {"type": "string", "enum": ["requirement", "prd", "design", "spec"], "description": "Filter by workflow stage"},
                    "k": {"type": "integer", "description": "Maximum results (default 10)", "default": 10}
                },
                "required": ["query"]
            },
            function=search_documents
        ),
        Tool(
            name="get_document",
            description="Retrieve a specific document by ID.",
            parameters={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Document ID"},
                    "include_full_content": {"type": "boolean", "description": "Include full content vs summary", "default": False}
                },
                "required": ["doc_id"]
            },
            function=get_document
        ),
        Tool(
            name="get_related_documents",
            description="Find documents related to a given document through references, dependencies, or workflow chains.",
            parameters={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Source document ID"},
                    "relationship_type": {"type": "string", "enum": ["references", "supersedes", "implements", "derived_from"], "description": "Filter by relationship type"}
                },
                "required": ["doc_id"]
            },
            function=get_related_documents
        ),
        Tool(
            name="get_workflow_chain",
            description="Get the workflow chain for a document. Traces the path from requirements through PRDs, designs, to specs.",
            parameters={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Document ID to trace from"},
                    "direction": {"type": "string", "enum": ["upstream", "downstream", "both"], "description": "Direction to trace", "default": "both"}
                },
                "required": ["doc_id"]
            },
            function=get_workflow_chain
        ),
        Tool(
            name="create_document",
            description="Create a new document from a template. Use this to start new requirements, PRDs, designs, or specs.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Document title"},
                    "doc_type": {"type": "string", "enum": ["requirement", "prd", "design", "spec", "note", "meeting"], "description": "Document type"},
                    "project": {"type": "string", "description": "Project name"},
                    "template": {"type": "string", "enum": ["technical", "meeting_notes", "requirement", "prd", "design", "spec"], "description": "Template to use"},
                    "parent_doc_id": {"type": "string", "description": "Parent document ID for workflow chains"},
                    "initial_content": {"type": "string", "description": "Optional initial content"}
                },
                "required": ["title", "doc_type"]
            },
            function=create_document,
            requires_confirmation=True
        ),
        Tool(
            name="generate_diagram",
            description="Generate a diagram using AI. Supports flowcharts, sequence diagrams, architecture diagrams, ER diagrams, and state machines.",
            parameters={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Natural language description of the diagram"},
                    "diagram_type": {"type": "string", "enum": ["flowchart", "sequence", "architecture", "er", "state"], "description": "Type of diagram", "default": "flowchart"},
                    "style": {"type": "string", "description": "Style preset"}
                },
                "required": ["description"]
            },
            function=generate_diagram
        ),
        Tool(
            name="summarize_documents",
            description="Summarize one or more documents. Can specify documents by ID or by search query.",
            parameters={
                "type": "object",
                "properties": {
                    "doc_ids": {"type": "array", "items": {"type": "string"}, "description": "Document IDs to summarize"},
                    "query": {"type": "string", "description": "Search query to find documents"},
                    "max_docs": {"type": "integer", "description": "Maximum documents", "default": 5}
                }
            },
            function=summarize_documents
        ),
        Tool(
            name="request_review",
            description="Request a review for a document from specified reviewers.",
            parameters={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Document ID"},
                    "reviewers": {"type": "array", "items": {"type": "string"}, "description": "Reviewer emails"},
                    "deadline_days": {"type": "integer", "description": "Days until deadline", "default": 7},
                    "message": {"type": "string", "description": "Message to reviewers"}
                },
                "required": ["doc_id", "reviewers"]
            },
            function=request_review,
            requires_confirmation=True
        ),
        Tool(
            name="find_requirements_for_spec",
            description="Trace a specification back to its originating requirements.",
            parameters={
                "type": "object",
                "properties": {
                    "spec_doc_id": {"type": "string", "description": "Specification document ID"}
                },
                "required": ["spec_doc_id"]
            },
            function=find_requirements_for_spec
        ),
        Tool(
            name="find_specs_for_requirement",
            description="Find all specifications that implement a requirement.",
            parameters={
                "type": "object",
                "properties": {
                    "requirement_doc_id": {"type": "string", "description": "Requirement document ID"}
                },
                "required": ["requirement_doc_id"]
            },
            function=find_specs_for_requirement
        ),
    ]
    
    return tools


def _get_template_content(template: str, title: str, project: Optional[str]) -> str:
    """Get content for a document template"""
    
    templates = {
        "requirement": f"""# {title}

**Project:** {project or 'TBD'}  
**Status:** Draft  
**Created:** {datetime.now().strftime('%Y-%m-%d')}

## 1. Overview

[Describe the requirement at a high level]

## 2. Background

[Context and motivation for this requirement]

## 3. Functional Requirements

### 3.1 [Requirement Category]

- **REQ-001**: [Requirement description]
- **REQ-002**: [Requirement description]

## 4. Non-Functional Requirements

### 4.1 Performance
### 4.2 Security
### 4.3 Usability

## 5. Constraints

## 6. Assumptions

## 7. Dependencies

## 8. Acceptance Criteria

---
*This requirement will be implemented in: [Link to PRD]*
""",
        
        "prd": f"""# PRD: {title}

**Project:** {project or 'TBD'}  
**Status:** Draft  
**Created:** {datetime.now().strftime('%Y-%m-%d')}  
**Implements:** [Link to Requirement]

## 1. Executive Summary

[Brief overview of what this PRD covers]

## 2. Problem Statement

[What problem are we solving?]

## 3. Goals and Non-Goals

### Goals
- 
- 

### Non-Goals
- 
- 

## 4. User Stories

### As a [user type], I want to [action] so that [benefit]

## 5. Proposed Solution

### 5.1 High-Level Design

### 5.2 Key Components

### 5.3 User Experience

## 6. Technical Considerations

### 6.1 Architecture Impact
### 6.2 Data Model Changes
### 6.3 API Changes

## 7. Timeline and Milestones

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Design Complete | | |
| Implementation Start | | |
| Testing Complete | | |
| Release | | |

## 8. Success Metrics

## 9. Open Questions

---
*Design documents: [Links]*  
*Implementation specs: [Links]*
""",

        "design": f"""# Design: {title}

**Project:** {project or 'TBD'}  
**Status:** Draft  
**Created:** {datetime.now().strftime('%Y-%m-%d')}  
**Implements PRD:** [Link to PRD]

## 1. Overview

[High-level description of the design]

## 2. Architecture

### 2.1 System Context

[DIAGRAM: System context diagram]

### 2.2 Component Design

[DIAGRAM: Component diagram]

### 2.3 Data Flow

[DIAGRAM: Data flow diagram]

## 3. Detailed Design

### 3.1 [Component 1]

#### Interface
#### Implementation Details
#### Error Handling

### 3.2 [Component 2]

## 4. Data Model

[DIAGRAM: ER diagram or data model]

## 5. API Design

### Endpoint: [Name]
- **Method:** 
- **Path:** 
- **Request:**
- **Response:**

## 6. Security Considerations

## 7. Performance Considerations

## 8. Testing Strategy

## 9. Deployment Plan

## 10. Rollback Plan

---
*Implementation specs: [Links]*
""",

        "spec": f"""# Implementation Spec: {title}

**Project:** {project or 'TBD'}  
**Status:** Draft  
**Created:** {datetime.now().strftime('%Y-%m-%d')}  
**Implements Design:** [Link to Design]

## 1. Scope

[What this spec covers]

## 2. Implementation Details

### 2.1 File Structure

```
project/
├── src/
│   └── ...
└── tests/
    └── ...
```

### 2.2 Key Classes/Functions

#### `ClassName`

```python
class ClassName:
    '''
    Description
    '''
    def method_name(self, param: Type) -> ReturnType:
        '''Method description'''
        pass
```

## 3. Configuration

## 4. Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| | | |

## 5. Testing

### 5.1 Unit Tests
### 5.2 Integration Tests
### 5.3 Test Data

## 6. Migration (if applicable)

## 7. Monitoring

## 8. Documentation Updates Needed

## 9. Checklist

- [ ] Code complete
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Code review complete
- [ ] Security review (if needed)
- [ ] Performance validated

---
*Code location: [repo/path]*
""",

        "technical": f"""# {title}

**Project:** {project or 'TBD'}  
**Author:** [Your Name]  
**Created:** {datetime.now().strftime('%Y-%m-%d')}  
**Status:** Draft

## 1. Introduction

## 2. Background

## 3. Technical Details

## 4. Implementation

## 5. Results

## 6. Conclusions

## 7. References

""",

        "meeting_notes": f"""# Meeting: {title}

**Date:** {datetime.now().strftime('%Y-%m-%d')}  
**Project:** {project or 'TBD'}  
**Attendees:** 

## Agenda

1. 
2. 
3. 

## Discussion

### Topic 1

### Topic 2

## Decisions Made

- **Decision 1:** 
- **Decision 2:** 

## Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| | | | |

## Next Meeting

**Date:** TBD  
**Topics:**
"""
    }
    
    return templates.get(template, templates["technical"])
