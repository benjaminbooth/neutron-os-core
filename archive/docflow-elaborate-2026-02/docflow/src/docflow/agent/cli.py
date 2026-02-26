"""
DocFlow Agent CLI

Interactive chat and query interface for DocFlowAgent.
"""
import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from .core import DocFlowAgent, AgentConfig, create_agent

# CLI app for agent commands
app = typer.Typer(help="DocFlow AI Agent commands")
console = Console()


def print_welcome():
    """Print welcome message"""
    console.print(Panel.fit(
        "[bold blue]DocFlow Agent[/bold blue]\n"
        "AI assistant for document workflows\n\n"
        "[dim]Commands:[/dim]\n"
        "  /help     - Show available commands\n"
        "  /search   - Quick search shortcut\n"
        "  /new      - Create new document\n"
        "  /chain    - Show workflow chain\n"
        "  /clear    - Clear conversation\n"
        "  /quit     - Exit chat\n\n"
        "[dim]Or just type your question![/dim]",
        title="Welcome",
        border_style="blue"
    ))


def print_response(response):
    """Print agent response with formatting"""
    # Main response
    console.print()
    console.print(Markdown(response.message))
    
    # Citations
    if response.citations:
        console.print()
        console.print("[dim]Sources:[/dim]")
        for citation in response.citations:
            console.print(f"  • {citation['title']}")
    
    # Follow-up suggestions
    if response.follow_up_suggestions:
        console.print()
        console.print("[dim]You might also ask:[/dim]")
        for suggestion in response.follow_up_suggestions:
            console.print(f"  → {suggestion}")
    
    console.print()


async def run_chat_session(config: Optional[AgentConfig] = None):
    """Run interactive chat session"""
    print_welcome()
    
    async with create_agent(config) as agent:
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("[bold green]You[/bold green]")
                
                if not user_input.strip():
                    continue
                
                # Handle slash commands
                if user_input.startswith('/'):
                    command = user_input.lower().split()[0]
                    args = user_input[len(command):].strip()
                    
                    if command in ['/quit', '/exit', '/q']:
                        console.print("[dim]Goodbye![/dim]")
                        break
                    
                    elif command == '/help':
                        print_help()
                        continue
                    
                    elif command == '/clear':
                        agent.clear_history()
                        console.print("[dim]Conversation cleared.[/dim]")
                        continue
                    
                    elif command == '/search':
                        if args:
                            user_input = f"Search for documents about: {args}"
                        else:
                            console.print("[yellow]Usage: /search <query>[/yellow]")
                            continue
                    
                    elif command == '/new':
                        if args:
                            user_input = f"Create a new document titled: {args}"
                        else:
                            console.print("[yellow]Usage: /new <title>[/yellow]")
                            continue
                    
                    elif command == '/chain':
                        if args:
                            user_input = f"Show the workflow chain for document: {args}"
                        else:
                            console.print("[yellow]Usage: /chain <doc_id>[/yellow]")
                            continue
                    
                    elif command == '/status':
                        user_input = "Show my pending reviews and draft documents"
                    
                    else:
                        console.print(f"[yellow]Unknown command: {command}[/yellow]")
                        continue
                
                # Show thinking indicator
                with console.status("[bold blue]Thinking...[/bold blue]", spinner="dots"):
                    response = await agent.chat(user_input)
                
                # Print response
                print_response(response)
                
            except KeyboardInterrupt:
                console.print("\n[dim]Use /quit to exit[/dim]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")


def print_help():
    """Print help information"""
    table = Table(title="Available Commands", show_header=True)
    table.add_column("Command", style="cyan")
    table.add_column("Description")
    
    commands = [
        ("/search <query>", "Search for documents"),
        ("/new <title>", "Create a new document"),
        ("/chain <doc_id>", "Show workflow chain (req → PRD → spec)"),
        ("/status", "Show pending reviews and drafts"),
        ("/clear", "Clear conversation history"),
        ("/help", "Show this help"),
        ("/quit", "Exit chat"),
    ]
    
    for cmd, desc in commands:
        table.add_row(cmd, desc)
    
    console.print(table)
    console.print()
    console.print("[dim]Or just type any question about your documents![/dim]")


@app.command()
def chat(
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use"),
    local: bool = typer.Option(True, "--local/--cloud", help="Use local or cloud LLM"),
):
    """Start interactive chat with DocFlow Agent"""
    config = AgentConfig()
    
    if model:
        config.llm_model = model
    
    if not local:
        config.fallback_provider = "anthropic"
        config.fallback_api_key = typer.prompt("Anthropic API Key", hide_input=True)
    
    asyncio.run(run_chat_session(config))


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use"),
):
    """Ask a one-shot question (no conversation history)"""
    
    async def run_query():
        config = AgentConfig()
        if model:
            config.llm_model = model
        
        async with create_agent(config) as agent:
            with console.status("[bold blue]Thinking...[/bold blue]", spinner="dots"):
                response = await agent.query(question)
            
            print_response(response)
    
    asyncio.run(run_query())


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    project: str = typer.Option(None, "--project", "-p", help="Filter by project"),
    author: str = typer.Option(None, "--author", "-a", help="Filter by author"),
    stage: str = typer.Option(None, "--stage", "-s", help="Filter by workflow stage"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results"),
):
    """Quick document search"""
    
    async def run_search():
        async with create_agent() as agent:
            # Build search request
            filters = []
            if project:
                filters.append(f"in project {project}")
            if author:
                filters.append(f"by {author}")
            if stage:
                filters.append(f"at {stage} stage")
            
            search_query = f"Search for: {query}"
            if filters:
                search_query += " " + " ".join(filters)
            search_query += f" (limit {limit} results)"
            
            with console.status("[bold blue]Searching...[/bold blue]", spinner="dots"):
                response = await agent.query(search_query)
            
            print_response(response)
    
    asyncio.run(run_search())


@app.command()
def chain(
    doc_id: str = typer.Argument(..., help="Document ID"),
    direction: str = typer.Option("both", "--direction", "-d", help="upstream, downstream, or both"),
):
    """Show workflow chain for a document"""
    
    async def show_chain():
        async with create_agent() as agent:
            query = f"Show the {direction} workflow chain for document {doc_id}"
            
            with console.status("[bold blue]Tracing chain...[/bold blue]", spinner="dots"):
                response = await agent.query(query)
            
            print_response(response)
    
    asyncio.run(show_chain())


@app.command()
def new(
    title: str = typer.Argument(..., help="Document title"),
    doc_type: str = typer.Option("note", "--type", "-t", help="Document type"),
    project: str = typer.Option(None, "--project", "-p", help="Project name"),
    template: str = typer.Option(None, "--template", help="Template to use"),
    parent: str = typer.Option(None, "--parent", help="Parent document ID"),
):
    """Create a new document"""
    
    async def create_doc():
        async with create_agent() as agent:
            parts = [f'Create a new {doc_type} document titled "{title}"']
            if project:
                parts.append(f"for project {project}")
            if template:
                parts.append(f"using the {template} template")
            if parent:
                parts.append(f"derived from document {parent}")
            
            query = " ".join(parts)
            
            with console.status("[bold blue]Creating document...[/bold blue]", spinner="dots"):
                response = await agent.query(query)
            
            print_response(response)
    
    asyncio.run(create_doc())


# === LSP/IDE Interface ===

class AgentServer:
    """
    Server interface for IDE plugins.
    
    Provides JSON-RPC style interface that can be used by:
    - VS Code extension
    - PyCharm plugin
    - Neovim plugin
    - Web UI
    """
    
    def __init__(self):
        self.agent: Optional[DocFlowAgent] = None
    
    async def initialize(self, config: dict = None):
        """Initialize the agent server"""
        agent_config = AgentConfig(**(config or {}))
        self.agent = DocFlowAgent(agent_config)
        await self.agent.initialize()
        return {"status": "initialized"}
    
    async def shutdown(self):
        """Shutdown the agent server"""
        if self.agent:
            await self.agent.close()
        return {"status": "shutdown"}
    
    async def chat(self, message: str, conversation_id: str = None):
        """Process a chat message"""
        if not self.agent:
            return {"error": "Agent not initialized"}
        
        response = await self.agent.chat(message)
        
        return {
            "message": response.message,
            "citations": response.citations,
            "suggestions": response.follow_up_suggestions,
            "tools_used": [t['tool'] for t in response.tool_calls_made]
        }
    
    async def query(self, question: str):
        """One-shot query"""
        if not self.agent:
            return {"error": "Agent not initialized"}
        
        response = await self.agent.query(question)
        
        return {
            "message": response.message,
            "citations": response.citations,
            "suggestions": response.follow_up_suggestions
        }
    
    async def search(self, query: str, filters: dict = None):
        """Direct search without LLM"""
        if not self.agent:
            return {"error": "Agent not initialized"}
        
        results = await self.agent._retriever.retrieve_hybrid(
            query=query,
            k=filters.get('limit', 10) if filters else 10,
            filters=filters
        )
        
        return {
            "count": len(results),
            "results": [
                {
                    "doc_id": r.chunk.doc_id,
                    "title": r.chunk.metadata.get('title'),
                    "preview": r.chunk.content[:200],
                    "score": r.combined_score
                }
                for r in results
            ]
        }
    
    async def clear_history(self):
        """Clear conversation history"""
        if self.agent:
            self.agent.clear_history()
        return {"status": "cleared"}


def run_server(port: int = 8765):
    """
    Run agent as WebSocket server for IDE integration.
    
    Protocol: JSON-RPC 2.0 over WebSocket
    """
    import json
    import websockets
    
    server = AgentServer()
    
    async def handle_message(websocket, path):
        async for message in websocket:
            try:
                request = json.loads(message)
                method = request.get('method')
                params = request.get('params', {})
                request_id = request.get('id')
                
                # Route to appropriate handler
                if method == 'initialize':
                    result = await server.initialize(params.get('config'))
                elif method == 'shutdown':
                    result = await server.shutdown()
                elif method == 'chat':
                    result = await server.chat(params.get('message'), params.get('conversation_id'))
                elif method == 'query':
                    result = await server.query(params.get('question'))
                elif method == 'search':
                    result = await server.search(params.get('query'), params.get('filters'))
                elif method == 'clear_history':
                    result = await server.clear_history()
                else:
                    result = {"error": f"Unknown method: {method}"}
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
                
            except Exception as e:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get('id') if 'request' in dir() else None,
                    "error": {"code": -1, "message": str(e)}
                }
            
            await websocket.send(json.dumps(response))
    
    async def main():
        async with websockets.serve(handle_message, "localhost", port):
            console.print(f"[green]DocFlow Agent server running on ws://localhost:{port}[/green]")
            await asyncio.Future()  # Run forever
    
    asyncio.run(main())


@app.command()
def serve(
    port: int = typer.Option(8765, "--port", "-p", help="Port to listen on"),
):
    """Run as server for IDE integration"""
    run_server(port)


if __name__ == "__main__":
    app()
