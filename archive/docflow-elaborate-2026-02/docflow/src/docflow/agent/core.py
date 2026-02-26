"""
DocFlow Agent - AI assistant for document workflows

This agent handles all document-related tasks:
- Search and retrieval
- Document creation and editing
- Workflow management (requirements → PRD → design → spec)
- Diagram generation
- Review and collaboration

Can be used standalone via CLI or as a tool by higher-level agents (Neutron).
"""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import httpx

from ..rag.retriever import HybridRetriever, QueryType
from ..rag.pgvector import PgVectorStore, Collection
from ..rag.embedder import Embedder
from ..core.config import get_config


@dataclass
class Message:
    """A message in the conversation"""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: Optional[str] = None  # Tool name if role is "tool"
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class Tool:
    """A tool the agent can use"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    requires_confirmation: bool = False


@dataclass
class AgentResponse:
    """Response from the agent"""
    message: str
    citations: List[Dict] = field(default_factory=list)
    tool_calls_made: List[Dict] = field(default_factory=list)
    confidence: float = 1.0
    follow_up_suggestions: List[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Configuration for DocFlowAgent"""
    # LLM settings
    llm_base_url: str = "http://localhost:8000/v1"
    llm_model: str = "kimi-k2.5"
    llm_api_key: str = "local"
    temperature: float = 0.7
    max_tokens: int = 4096
    
    # Fallback LLM
    fallback_provider: Optional[str] = None  # "anthropic"
    fallback_model: Optional[str] = None
    fallback_api_key: Optional[str] = None
    
    # Agent behavior
    max_iterations: int = 10
    timeout_seconds: float = 60.0
    
    # Tool settings
    require_confirmation_for: List[str] = field(default_factory=lambda: [
        "create_document", "delete_document", "publish_document"
    ])
    
    # Persona
    system_prompt: Optional[str] = None


class DocFlowAgent:
    """
    AI agent for document workflows.
    
    Capabilities:
    - Semantic search across all document collections
    - Workflow chain navigation (requirement → PRD → design → spec)
    - Document creation from templates
    - Diagram generation with AI
    - Review management
    
    Usage:
        agent = DocFlowAgent()
        await agent.initialize()
        
        # Interactive chat
        response = await agent.chat("Find all documents about thermal hydraulics")
        
        # One-shot query
        response = await agent.query("What's the status of the MSR PRD?")
        
        # As a tool for Neutron Agent
        tool = agent.as_tool()
    """
    
    DEFAULT_SYSTEM_PROMPT = """You are DocFlow, an AI assistant for document workflows in a nuclear engineering research environment.

Your capabilities:
- Search and retrieve documents across personal, team, and code repositories
- Navigate document workflows (requirements → PRDs → designs → specs)
- Create new documents from templates
- Generate diagrams with AI
- Manage document reviews and feedback
- Track document relationships and dependencies

Guidelines:
- Always cite sources using [Document Title] notation
- Be concise but thorough
- When uncertain, search for more information before answering
- For complex tasks, break them into steps
- Respect document states (draft, review, published)
- When creating documents, follow the established templates

You have access to tools for searching, creating, and managing documents. Use them to fulfill user requests."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._retriever: Optional[HybridRetriever] = None
        self._store: Optional[PgVectorStore] = None
        self._embedder: Optional[Embedder] = None
        self._tools: Dict[str, Tool] = {}
        self._conversation_history: List[Message] = []
        self._local_llm_available: Optional[bool] = None
    
    async def initialize(self) -> None:
        """Initialize agent components"""
        self._http_client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        
        # Initialize RAG components
        app_config = get_config()
        self._store = PgVectorStore(
            connection_string=app_config.database_url,
            dimensions=768
        )
        await self._store.initialize()
        
        self._embedder = Embedder()
        self._retriever = HybridRetriever(
            store=self._store,
            embedder=self._embedder
        )
        
        # Register tools
        self._register_tools()
    
    async def close(self) -> None:
        """Cleanup resources"""
        if self._http_client:
            await self._http_client.aclose()
        if self._store:
            await self._store.close()
        if self._embedder:
            await self._embedder.close()
    
    def _register_tools(self) -> None:
        """Register available tools"""
        from .tools import get_docflow_tools
        for tool in get_docflow_tools(self):
            self._tools[tool.name] = tool
    
    async def chat(
        self,
        message: str,
        history: Optional[List[Message]] = None
    ) -> AgentResponse:
        """
        Process a user message and return a response.
        
        This is the main entry point for interactive chat.
        """
        # Use provided history or existing conversation
        if history is not None:
            self._conversation_history = history.copy()
        
        # Add user message
        self._conversation_history.append(Message(role="user", content=message))
        
        # Run agent loop
        return await self._run_agent_loop()
    
    async def query(self, question: str) -> AgentResponse:
        """
        One-shot query without conversation history.
        """
        self._conversation_history = []
        return await self.chat(question)
    
    def clear_history(self) -> None:
        """Clear conversation history"""
        self._conversation_history = []
    
    async def _run_agent_loop(self) -> AgentResponse:
        """
        Run the agent loop: generate → maybe use tools → respond
        """
        tool_calls_made = []
        
        for iteration in range(self.config.max_iterations):
            # Generate response (may include tool calls)
            response = await self._generate_response()
            
            if response.get('tool_calls'):
                # Execute tool calls
                tool_results = []
                for tool_call in response['tool_calls']:
                    result = await self._execute_tool(tool_call)
                    tool_results.append(result)
                    tool_calls_made.append({
                        'tool': tool_call['function']['name'],
                        'arguments': tool_call['function']['arguments'],
                        'result_preview': str(result)[:200]
                    })
                
                # Add assistant message with tool calls
                self._conversation_history.append(Message(
                    role="assistant",
                    content=response.get('content', ''),
                    tool_calls=response['tool_calls']
                ))
                
                # Add tool results
                for tool_call, result in zip(response['tool_calls'], tool_results):
                    self._conversation_history.append(Message(
                        role="tool",
                        content=json.dumps(result, default=str),
                        tool_call_id=tool_call['id'],
                        name=tool_call['function']['name']
                    ))
            else:
                # Final response
                final_message = response.get('content', '')
                
                # Extract citations from the response
                citations = self._extract_citations(final_message)
                
                # Generate follow-up suggestions
                follow_ups = await self._generate_follow_ups(final_message)
                
                # Add to history
                self._conversation_history.append(Message(
                    role="assistant",
                    content=final_message
                ))
                
                return AgentResponse(
                    message=final_message,
                    citations=citations,
                    tool_calls_made=tool_calls_made,
                    follow_up_suggestions=follow_ups
                )
        
        # Max iterations reached
        return AgentResponse(
            message="I wasn't able to complete the task within the allowed steps. Please try breaking your request into smaller parts.",
            tool_calls_made=tool_calls_made
        )
    
    async def _generate_response(self) -> Dict[str, Any]:
        """Generate a response using the LLM"""
        # Check local availability
        if await self._check_local_llm():
            return await self._generate_local()
        elif self.config.fallback_provider:
            return await self._generate_fallback()
        else:
            raise RuntimeError(
                "Local LLM unavailable and no fallback configured. "
                f"Start local server at {self.config.llm_base_url}"
            )
    
    async def _check_local_llm(self) -> bool:
        """Check if local LLM is available"""
        if self._local_llm_available is not None:
            return self._local_llm_available
        
        try:
            response = await self._http_client.get(
                f"{self.config.llm_base_url}/models",
                timeout=5.0
            )
            self._local_llm_available = response.status_code == 200
        except Exception:
            self._local_llm_available = False
        
        return self._local_llm_available
    
    async def _generate_local(self) -> Dict[str, Any]:
        """Generate using local LLM"""
        messages = self._build_messages()
        tools = self._build_tool_definitions()
        
        response = await self._http_client.post(
            f"{self.config.llm_base_url}/chat/completions",
            json={
                "model": self.config.llm_model,
                "messages": messages,
                "tools": tools if tools else None,
                "tool_choice": "auto" if tools else None,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
        )
        response.raise_for_status()
        
        data = response.json()
        choice = data['choices'][0]
        
        return {
            'content': choice['message'].get('content'),
            'tool_calls': choice['message'].get('tool_calls')
        }
    
    async def _generate_fallback(self) -> Dict[str, Any]:
        """Generate using fallback provider (Anthropic)"""
        if self.config.fallback_provider == "anthropic":
            return await self._generate_anthropic()
        else:
            raise ValueError(f"Unknown fallback provider: {self.config.fallback_provider}")
    
    async def _generate_anthropic(self) -> Dict[str, Any]:
        """Generate using Anthropic API"""
        messages = self._build_messages(format="anthropic")
        tools = self._build_tool_definitions(format="anthropic")
        
        response = await self._http_client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.config.fallback_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": self.config.fallback_model or "claude-3-haiku-20240307",
                "max_tokens": self.config.max_tokens,
                "system": self.config.system_prompt or self.DEFAULT_SYSTEM_PROMPT,
                "messages": messages,
                "tools": tools if tools else None
            }
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Extract content and tool calls from Anthropic format
        content = ""
        tool_calls = []
        
        for block in data.get('content', []):
            if block['type'] == 'text':
                content += block['text']
            elif block['type'] == 'tool_use':
                tool_calls.append({
                    'id': block['id'],
                    'function': {
                        'name': block['name'],
                        'arguments': json.dumps(block['input'])
                    }
                })
        
        return {
            'content': content if content else None,
            'tool_calls': tool_calls if tool_calls else None
        }
    
    def _build_messages(self, format: str = "openai") -> List[Dict]:
        """Build messages array for LLM"""
        messages = []
        
        # System prompt
        if format == "openai":
            messages.append({
                "role": "system",
                "content": self.config.system_prompt or self.DEFAULT_SYSTEM_PROMPT
            })
        
        # Conversation history
        for msg in self._conversation_history:
            if format == "openai":
                message = {"role": msg.role, "content": msg.content}
                if msg.tool_calls:
                    message["tool_calls"] = msg.tool_calls
                if msg.tool_call_id:
                    message["tool_call_id"] = msg.tool_call_id
                if msg.name:
                    message["name"] = msg.name
                messages.append(message)
            else:  # anthropic
                if msg.role == "tool":
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content
                        }]
                    })
                elif msg.role == "assistant" and msg.tool_calls:
                    content = []
                    if msg.content:
                        content.append({"type": "text", "text": msg.content})
                    for tc in msg.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tc['id'],
                            "name": tc['function']['name'],
                            "input": json.loads(tc['function']['arguments'])
                        })
                    messages.append({"role": "assistant", "content": content})
                elif msg.role != "system":
                    messages.append({"role": msg.role, "content": msg.content})
        
        return messages
    
    def _build_tool_definitions(self, format: str = "openai") -> List[Dict]:
        """Build tool definitions for LLM"""
        tools = []
        
        for tool in self._tools.values():
            if format == "openai":
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters
                    }
                })
            else:  # anthropic
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters
                })
        
        return tools
    
    async def _execute_tool(self, tool_call: Dict) -> Any:
        """Execute a tool call"""
        name = tool_call['function']['name']
        args = json.loads(tool_call['function']['arguments'])
        
        if name not in self._tools:
            return {"error": f"Unknown tool: {name}"}
        
        tool = self._tools[name]
        
        try:
            # Check if confirmation required
            if tool.requires_confirmation:
                # In CLI context, we'd prompt user
                # For now, just execute
                pass
            
            result = await tool.function(**args)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_citations(self, text: str) -> List[Dict]:
        """Extract citations from response text"""
        import re
        citations = []
        
        # Find [Document Title] patterns
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, text)
        
        seen = set()
        for match in matches:
            if match not in seen and not match.startswith('http'):
                seen.add(match)
                citations.append({
                    'title': match,
                    'type': 'document_reference'
                })
        
        return citations
    
    async def _generate_follow_ups(self, response: str) -> List[str]:
        """Generate follow-up question suggestions"""
        # Simple heuristic-based suggestions
        # TODO: Use LLM for better suggestions
        suggestions = []
        
        response_lower = response.lower()
        
        if 'document' in response_lower or 'found' in response_lower:
            suggestions.append("Can you summarize these documents?")
            suggestions.append("Show me related documents")
        
        if 'requirement' in response_lower:
            suggestions.append("What PRDs implement this requirement?")
        
        if 'prd' in response_lower:
            suggestions.append("Show the implementation specs for this PRD")
        
        return suggestions[:3]  # Max 3 suggestions
    
    # === Public API for higher-level agents ===
    
    def as_tool(self) -> Tool:
        """
        Expose this agent as a tool for higher-level agents (e.g., Neutron Agent).
        
        Usage:
            neutron_tools = [
                docflow_agent.as_tool(),
                sam_agent.as_tool(),
                # ...
            ]
        """
        return Tool(
            name="docflow_agent",
            description="""Expert agent for document management and workflows.
            
Use this tool when you need to:
- Search for documents (requirements, PRDs, designs, specs, meeting notes)
- Find relationships between documents
- Create or update documents
- Generate diagrams
- Manage document reviews
- Navigate the requirement → PRD → design → spec workflow

The agent will use multiple tools internally to fulfill complex requests.""",
            parameters={
                "type": "object",
                "properties": {
                    "request": {
                        "type": "string",
                        "description": "Natural language request about documents"
                    }
                },
                "required": ["request"]
            },
            function=self._handle_as_tool
        )
    
    async def _handle_as_tool(self, request: str) -> Dict[str, Any]:
        """Handle request when used as a tool by another agent"""
        response = await self.query(request)
        return {
            "response": response.message,
            "citations": response.citations,
            "tools_used": [t['tool'] for t in response.tool_calls_made]
        }


# === Context manager support ===

class DocFlowAgentContext:
    """Async context manager for DocFlowAgent"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.agent = DocFlowAgent(config)
    
    async def __aenter__(self) -> DocFlowAgent:
        await self.agent.initialize()
        return self.agent
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.agent.close()


def create_agent(config: Optional[AgentConfig] = None) -> DocFlowAgentContext:
    """
    Create an agent with context manager support.
    
    Usage:
        async with create_agent() as agent:
            response = await agent.chat("Find documents about thermal hydraulics")
    """
    return DocFlowAgentContext(config)
