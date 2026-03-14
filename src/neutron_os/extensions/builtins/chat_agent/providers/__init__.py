"""Chat UI providers — render and input abstraction layer.

Follows the DocFlow Factory/Provider pattern. The chat engine works
through RenderProvider and InputProvider ABCs, never importing rich
or prompt_toolkit directly.
"""
