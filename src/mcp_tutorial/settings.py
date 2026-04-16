"""
Read settings from the environment.

Typical flow: call ``load_dotenv()`` once, then ``Settings.from_env()`` for
``OPENROUTER_*`` and ``TOOLBOX_BASE_URL`` (``python-dotenv`` loads ``.env``).

The tool-calling round cap is ``AGENT_MAX_TOOL_ROUNDS`` below (not env-driven).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Max model turns that may include tool calls (fixed for this tutorial; change in code).
AGENT_MAX_TOOL_ROUNDS = 16


@dataclass(frozen=True)
class Settings:
    """URLs and keys from the environment; ``agent_max_tool_rounds`` is fixed in code."""

    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    toolbox_base_url: str
    agent_max_tool_rounds: int

    @staticmethod
    def from_env() -> "Settings":
        """Build settings from ``os.environ`` (missing keys use sane defaults)."""
        key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
        base = (
            os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
        ).strip()
        model = (os.environ.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini").strip()
        toolbox = (
            (os.environ.get("TOOLBOX_BASE_URL") or "http://127.0.0.1:5050")
            .strip()
            .rstrip("/")
        )
        return Settings(
            openrouter_api_key=key,
            openrouter_base_url=base,
            openrouter_model=model,
            toolbox_base_url=toolbox,
            agent_max_tool_rounds=AGENT_MAX_TOOL_ROUNDS,
        )
