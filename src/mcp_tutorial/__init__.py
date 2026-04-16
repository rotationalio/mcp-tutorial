"""
Package ``mcp_tutorial``: OpenRouter + MCP Toolbox helpers for the tutorial.

- ``Settings``: load URLs and API keys from the environment or ``.env``.
- ``run_chat_with_tools``: one blocking loop that may call Toolbox tools.
- ``mcp_tutorial.prompts``: shared tutorial user prompts (CLI demo and notebook).
"""

from .agent import run_chat_with_tools
from .settings import Settings

__all__ = ["Settings", "run_chat_with_tools"]
