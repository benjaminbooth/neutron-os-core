"""Agent tools for Model Corral — exposed to LLM agents via chat_tools.

These tools let agents search, inspect, and validate physics models
without requiring the user to run CLI commands directly.
"""

from __future__ import annotations

from pathlib import Path

TOOLS = [
    {
        "name": "model_search",
        "description": "Search the physics model registry by reactor type, physics code, or keyword. Returns matching models with metadata.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'TRIGA transient MCNP')",
                },
                "reactor_type": {"type": "string", "description": "Filter by reactor type"},
                "physics_code": {"type": "string", "description": "Filter by physics code"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "model_show",
        "description": "Get full details for a specific model including all versions, validation status, and lineage.",
        "parameters": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "Model identifier (e.g., 'triga-netl-mcnp-v3')",
                },
            },
            "required": ["model_id"],
        },
    },
    {
        "name": "model_validate",
        "description": "Validate a model directory against the Model Corral schema. Checks model.yaml, file references, and metadata completeness.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to model directory"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "model_lineage",
        "description": "Show the lineage chain for a model — parent models, ROM training sources, fork history.",
        "parameters": {
            "type": "object",
            "properties": {
                "model_id": {"type": "string", "description": "Model identifier"},
            },
            "required": ["model_id"],
        },
    },
]


def execute(tool_name: str, params: dict) -> dict:
    """Execute a model corral agent tool."""
    if tool_name == "model_search":
        return _tool_search(params)
    if tool_name == "model_show":
        return _tool_show(params)
    if tool_name == "model_validate":
        return _tool_validate(params)
    if tool_name == "model_lineage":
        return _tool_lineage(params)
    return {"error": f"Unknown tool: {tool_name}"}


def _tool_search(params: dict) -> dict:
    from neutron_os.extensions.builtins.model_corral.cli import _get_service

    svc = _get_service()
    query = params.get("query", "")
    reactor_type = params.get("reactor_type")
    physics_code = params.get("physics_code")

    if reactor_type or physics_code:
        results = svc.list_models(reactor_type=reactor_type, physics_code=physics_code)
        if query:
            q = query.lower()
            results = [
                r
                for r in results
                if q
                in (r.get("name", "") + r.get("description", "") + r.get("model_id", "")).lower()
            ]
    else:
        results = svc.search(query)

    return {"count": len(results), "models": results}


def _tool_show(params: dict) -> dict:
    from neutron_os.extensions.builtins.model_corral.cli import _get_service

    svc = _get_service()
    info = svc.show(params["model_id"])
    if info is None:
        return {"error": f"Model not found: {params['model_id']}"}
    return info


def _tool_validate(params: dict) -> dict:
    from neutron_os.extensions.builtins.model_corral.manifest import validate_model_dir

    result = validate_model_dir(Path(params["path"]))
    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
    }


def _tool_lineage(params: dict) -> dict:
    from neutron_os.extensions.builtins.model_corral.cli import _get_service

    svc = _get_service()
    chain = svc.lineage(params["model_id"])
    return {"model_id": params["model_id"], "lineage": chain}
