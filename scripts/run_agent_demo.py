#!/usr/bin/env python3
"""
Small demo you can run from the terminal after Docker and your venv are up.

It sends two tutorial-style questions to OpenRouter. Prompt B varies each run (random
keyword + which hit to prefer). The model may call MCP Toolbox tools (Postgres + Mongo).
Good sanity check before you open the notebook.

Usage (repo root, virtualenv active):

  pip install -e .
  export OPENROUTER_API_KEY=...
  # Optional if Toolbox is not on the default host port:
  # export TOOLBOX_BASE_URL=http://127.0.0.1:5050
  python scripts/run_agent_demo.py

``pip install -e .`` registers the ``mcp_tutorial`` package (under ``src/mcp_tutorial/``)
so imports work without ``PYTHONPATH`` hacks. A ``.env`` file in the repo root is loaded automatically
if present (``python-dotenv``).

Logging defaults to **DEBUG** for ``mcp_tutorial.agent`` (each model turn). **INFO** lines show
when each HTTP call starts and finishes so a stall is easier to spot.
"""

from __future__ import annotations

import logging
import sys
import textwrap
from pathlib import Path

from dotenv import load_dotenv

from mcp_tutorial.agent import run_chat_with_tools
from mcp_tutorial.prompts import (
    PROMPT_A,
    SUMMARY_A,
    TUTORIAL_SYSTEM_PROMPT,
    build_prompt_b,
)
from mcp_tutorial.settings import Settings


def main() -> None:
    """
    Load env, validate settings, print prompts, and run two agent loops (A then B).

    Exits with code 2 if ``OPENROUTER_API_KEY`` is missing.
    """

    # Env and API key (fail fast before any network).
    load_dotenv(_REPO_ROOT / ".env")
    settings = Settings.from_env()
    if not settings.openrouter_api_key:
        print("Set OPENROUTER_API_KEY to run this demo.", file=sys.stderr)
        raise SystemExit(2)

    # Banner: where Toolbox and the model are pointed.
    print()
    print(_rule("="))
    print("MCP Toolbox + OpenRouter — agent demo".center(_W))
    print(_rule("="))
    print(
        textwrap.fill(
            f"Toolbox: {settings.toolbox_base_url} | Model: {settings.openrouter_model} | "
            f"Tool rounds cap: {settings.agent_max_tool_rounds} (fixed in mcp_tutorial.settings).",
            width=_W,
        )
    )
    print(_rule("="))
    print(
        "Logs: DEBUG = model/tool detail from mcp_tutorial.agent; INFO = start/end of each "
        "chat request and Toolbox tool (with seconds).",
        file=sys.stderr,
    )

    # Run A: structured sources first, bios second.
    _print_block(
        "Prompt A — Postgres → Mongo",
        f"Summary: {SUMMARY_A}\n\nFull prompt:\n{PROMPT_A}",
    )
    print("Running… (watch INFO lines if this sits silent)\n", file=sys.stderr)
    out_a = run_chat_with_tools(
        settings, user_prompt=PROMPT_A, system_prompt=TUTORIAL_SYSTEM_PROMPT
    )
    print("\n>>> Final answer (A)\n")
    print(textwrap.fill(out_a.strip(), width=_W))
    print(_rule("="))

    # Run B: biography-led search, then cross-check in relational data.
    prompt_b, keyword_b, pick_b = build_prompt_b()
    summary_b = (
        f"Biography search for {keyword_b!r}, nudge toward hit index ≤{pick_b} when "
        f"several matches exist, then verify in structured tables."
    )
    _print_block(
        "Prompt B — Mongo → Postgres",
        f"Summary: {summary_b}\n\nFull prompt:\n{prompt_b}",
    )
    print("Running…\n", file=sys.stderr)
    out_b = run_chat_with_tools(
        settings, user_prompt=prompt_b, system_prompt=TUTORIAL_SYSTEM_PROMPT
    )
    print("\n>>> Final answer (B)\n")
    print(textwrap.fill(out_b.strip(), width=_W))
    print(_rule("="))
    print()


# -----------------------------------------------------------------------------
# Private layout and I/O helpers (used by ``main``)
# -----------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_W = 72


def _rule(char: str = "=") -> str:
    """Return a fixed-width horizontal rule for terminal banners."""
    return char * _W


def _print_block(title: str, body: str, *, subtitle: str | None = None) -> None:
    """Print a titled, word-wrapped block (prompt preview) with simple ASCII framing."""
    print()
    print(_rule("="))
    print(title.center(_W))
    print(_rule("="))
    if subtitle:
        print(subtitle)
        print()
    for line in body.strip().splitlines():
        print(textwrap.fill(line, width=_W, subsequent_indent="  ") or "")
    print(_rule("-"))


if __name__ == "__main__":
    # Logging only for CLI runs so importing this module for other reasons does not clobber setup.
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for _name in (
        "httpx",
        "httpcore",
        "openai",
        "asyncio",
        "httpcore.connection",
        "httpcore.http11",
    ):
        logging.getLogger(_name).setLevel(logging.WARNING)
    main()
