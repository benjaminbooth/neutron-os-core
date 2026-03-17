"""Drop-in tool extension directory for neut chat.

Place self-contained tool modules here. Each module exports:
  TOOLS: list[ToolDef]       — tool definitions
  execute(name, params) -> dict  — handler function

The registry auto-discovers modules in this directory on each turn.
"""
