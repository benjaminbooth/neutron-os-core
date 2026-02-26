"""
DocFlow Agent Module

AI agent for document workflows with RAG-enhanced capabilities.
"""

from .core import (
    DocFlowAgent,
    AgentConfig,
    AgentResponse,
    Message,
    Tool,
    create_agent,
)

from .tools import (
    DOCFLOW_TOOLS,
    search_documents,
    get_document,
    get_related_documents,
    get_workflow_chain,
    create_document,
    generate_diagram,
    summarize_documents,
    request_review,
    find_requirements_for_spec,
    find_specs_for_requirement,
)

from .cli import (
    app as cli_app,
    AgentServer,
)

__all__ = [
    # core agent
    "DocFlowAgent",
    "AgentConfig",
    "AgentResponse",
    "Message",
    "Tool",
    "create_agent",
    # tools
    "DOCFLOW_TOOLS",
    "search_documents",
    "get_document",
    "get_related_documents",
    "get_workflow_chain",
    "create_document",
    "generate_diagram",
    "summarize_documents",
    "request_review",
    "find_requirements_for_spec",
    "find_specs_for_requirement",
    # cli
    "cli_app",
    "AgentServer",
]
