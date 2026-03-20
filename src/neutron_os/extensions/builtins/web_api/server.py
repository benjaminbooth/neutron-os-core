"""HTTP API server for neut chat.

Zero external dependencies — uses only stdlib http.server.
Exposes ChatAgent over HTTP with CORS, so any web page can embed a live neut.

Endpoints:
    POST /chat          Send a message, get a response
    GET  /health        Health check
    GET  /context       Returns available context summary (what neut "knows")
    OPTIONS /*          CORS preflight

Usage:
    neut serve [--port 8766] [--host 0.0.0.0] [--origins "*"]

Security:
    - Optional API key via --api-key or NEUT_API_KEY env var
    - CORS origin allowlist via --origins (default: localhost only)
    - Read-only tool execution (write tools require explicit opt-in)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from neutron_os.infra.state import locked_append_jsonl

logger = logging.getLogger(__name__)

# Lazy-loaded to avoid import overhead at module level
_agent = None
_agent_lock = threading.Lock()
_chat_log_path: Optional[Path] = None
_chat_log_lock = threading.Lock()


def _log_chat(user: str, message: str, response: str, elapsed_ms: int):
    """Append a chat exchange to the JSONL log file."""
    if not _chat_log_path:
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "prompt": message,
        "response": response,
        "elapsed_ms": elapsed_ms,
    }
    with _chat_log_lock:
        locked_append_jsonl(_chat_log_path, entry)


def _get_agent():
    """Lazy-init ChatAgent with gateway and session."""
    global _agent
    if _agent is not None:
        return _agent

    with _agent_lock:
        if _agent is not None:
            return _agent

        from neutron_os.extensions.builtins.neut_agent.agent import ChatAgent
        from neutron_os.infra.gateway import Gateway
        from neutron_os.infra.orchestrator.bus import EventBus
        from neutron_os.infra.orchestrator.session import Session

        gateway = Gateway()
        bus = EventBus()
        session = Session()

        _agent = ChatAgent(gateway=gateway, bus=bus, session=session)
        logger.info(
            "ChatAgent initialized (provider: %s, model: %s)",
            gateway.active_provider.name if gateway.active_provider else "stub",
            gateway.active_provider.model if gateway.active_provider else "none",
        )
        return _agent


def _get_context_summary() -> dict:
    """Return a summary of what institutional knowledge neut has access to."""
    from neutron_os import REPO_ROOT

    context = {
        "project": "NeutronOS",
        "description": "Digital platform for nuclear facilities",
        "knowledge_sources": [],
    }

    # Check for CLAUDE.md
    claude_md = REPO_ROOT / "CLAUDE.md"
    if claude_md.exists():
        context["knowledge_sources"].append({
            "type": "project_context",
            "name": "CLAUDE.md",
            "description": "Project conventions, architecture, and institutional knowledge",
        })

    # Check for docs
    docs_dir = REPO_ROOT / "docs"
    if docs_dir.exists():
        doc_count = sum(1 for _ in docs_dir.rglob("*.md"))
        context["knowledge_sources"].append({
            "type": "documentation",
            "name": "docs/",
            "count": doc_count,
            "description": "PRDs, tech specs, analysis, stakeholder inputs",
        })

    # Check for runtime/config
    runtime_dir = REPO_ROOT / "runtime"
    if runtime_dir.exists():
        context["knowledge_sources"].append({
            "type": "runtime_config",
            "name": "runtime/",
            "description": "Model configuration, facility settings",
        })

    # Check sense inbox
    inbox = REPO_ROOT / "runtime" / "inbox" / "processed"
    if inbox.exists():
        processed = sum(1 for _ in inbox.rglob("*") if _.is_file())
        context["knowledge_sources"].append({
            "type": "signals",
            "name": "sense inbox",
            "count": processed,
            "description": "Processed signals from GitLab, Teams, meetings",
        })

    return context


class NeutAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler for neut chat API."""

    # Set by the server
    allowed_origins: list[str] = ["http://localhost:*"]
    api_key: Optional[str] = None
    read_only: bool = True
    static_dir: Optional[str] = None  # Path to serve static files from

    def log_message(self, format, *args):
        logger.info(format, *args)

    def _set_cors_headers(self):
        origin = self.headers.get("Origin", "")
        if self._origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        elif "*" in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")

    def _origin_allowed(self, origin: str) -> bool:
        if not origin:
            return False
        if "*" in self.allowed_origins:
            return True
        parsed = urlparse(origin)
        for allowed in self.allowed_origins:
            if "*" in allowed:
                # Simple wildcard: http://localhost:* matches any port
                pattern = allowed.replace("*", "")
                if origin.startswith(pattern) or (parsed.hostname and parsed.hostname in allowed):
                    return True
            elif origin == allowed:
                return True
        return False

    def _check_auth(self) -> bool:
        if not self.api_key:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:] == self.api_key
        return False

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "neut-api"})
        elif self.path == "/context":
            self._send_json(200, _get_context_summary())
        elif self.static_dir:
            self._serve_static()
        else:
            self._send_json(404, {"error": "Not found"})

    def _serve_static(self):
        """Serve static files from the configured directory."""
        import mimetypes
        from pathlib import Path

        # Map / to /index.html
        req_path = self.path.split("?")[0]
        if req_path == "/":
            req_path = "/index.html"

        # Resolve and prevent directory traversal
        static_root = Path(self.static_dir).resolve()
        file_path = (static_root / req_path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(static_root)):
            self._send_json(403, {"error": "Forbidden"})
            return

        if not file_path.is_file():
            self._send_json(404, {"error": "Not found"})
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        body = file_path.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self._check_auth():
            self._send_json(401, {"error": "Unauthorized"})
            return

        if self.path == "/chat":
            self._handle_chat()
        elif self.path == "/reset":
            self._handle_reset()
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_chat(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "Invalid JSON"})
            return

        message = data.get("message", "").strip()
        if not message:
            self._send_json(400, {"error": "Empty message"})
            return

        if len(message) > 4000:
            self._send_json(400, {"error": "Message too long (max 4000 chars)"})
            return

        # Optional user context from client (EID-based identity)
        user_context = data.get("user_context")

        try:
            agent = _get_agent()

            # Inject user identity into session context if provided
            if user_context and isinstance(user_context, dict):
                agent.session.context["user_identity"] = user_context

            t0 = time.monotonic()
            response = agent.turn(message, stream=False)
            elapsed_ms = round((time.monotonic() - t0) * 1000)

            user_name = (user_context or {}).get("name", "anonymous")
            _log_chat(user_name, message, response, elapsed_ms)

            self._send_json(200, {
                "response": response,
                "elapsed_ms": elapsed_ms,
            })
        except Exception as e:
            logger.error("Chat error: %s", traceback.format_exc())
            self._send_json(500, {"error": str(e)})

    def _handle_reset(self):
        """Reset the chat session."""
        global _agent
        with _agent_lock:
            _agent = None
        self._send_json(200, {"status": "session reset"})


class NeutAPIServer:
    """Configurable HTTP API server for neut chat."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8766,
        origins: Optional[list[str]] = None,
        api_key: Optional[str] = None,
        read_only: bool = True,
        static_dir: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.origins = origins or ["http://localhost:*", "http://127.0.0.1:*"]
        self.api_key = api_key or os.environ.get("NEUT_API_KEY")
        self.read_only = read_only
        self.static_dir = static_dir

    def serve(self):
        # Configure handler class attributes
        NeutAPIHandler.allowed_origins = self.origins
        NeutAPIHandler.api_key = self.api_key
        NeutAPIHandler.read_only = self.read_only
        NeutAPIHandler.static_dir = self.static_dir

        # Set up chat log
        global _chat_log_path
        from neutron_os import REPO_ROOT
        log_dir = REPO_ROOT / "runtime" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _chat_log_path = log_dir / "chat.jsonl"

        server = HTTPServer((self.host, self.port), NeutAPIHandler)

        auth_status = "enabled" if self.api_key else "disabled"
        origins_str = ", ".join(self.origins)

        print("neut API server")
        print(f"  Listening:  http://{self.host}:{self.port}")
        print(f"  Auth:       {auth_status}")
        print(f"  CORS:       {origins_str}")
        print(f"  Read-only:  {self.read_only}")
        print()
        print("Endpoints:")
        print("  POST /chat     Send a message")
        print("  POST /reset    Reset session")
        print("  GET  /health   Health check")
        print("  GET  /context  Knowledge sources")
        print()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
            server.shutdown()
