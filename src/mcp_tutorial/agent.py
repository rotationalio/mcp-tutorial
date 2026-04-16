"""
Run a short chat where the model can call database tools served by MCP Toolbox.

Flow in plain words:
1. Connect to Toolbox and load the ``combined`` toolset (Postgres + Mongo).
2. Turn those tools into the “function calling” shape OpenRouter expects.
3. Loop: send the chat to the model; if it picks a tool, run it via Toolbox,
   append the result, repeat—until you get plain text or hit the round limit.

The Toolbox library uses MCP internally; you only pass the server base URL.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Sequence

from openai import OpenAI
from toolbox_core import ToolboxSyncClient
from toolbox_core.protocol import Protocol
from toolbox_core.sync_tool import ToolboxSyncTool

from .settings import Settings

logger = logging.getLogger(__name__)


###############################################################################
# Public API
###############################################################################

# Default instructions for the model when your script does not pass a custom
# system prompt. Override per call with ``system_prompt=...`` if you like.
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. " "Use tools when they improve factual accuracy."
)


def run_chat_with_tools(
    settings: Settings,
    *,
    user_prompt: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> str:
    """
    Run one user turn against OpenRouter with Toolbox tools available.

    What happens:
        - Opens a synchronous MCP Toolbox client at ``settings.toolbox_base_url``.
        - Loads the ``combined`` toolset (Postgres + Mongo tools from YAML).
        - Sends ``user_prompt`` and ``system_prompt`` to the model (blocking HTTP).
        - If the model returns ``tool_calls``, each call runs against Toolbox
          and the results are sent back; this repeats until the model replies
          with plain text or ``settings.agent_max_tool_rounds`` is hit.

    Args:
        settings: API keys, URLs, model id, and tool-round cap from the env.
        user_prompt: The natural-language question or task for the model.
        system_prompt: Optional system message; defaults to
            ``DEFAULT_SYSTEM_PROMPT``. A short note with
            ``settings.agent_max_tool_rounds`` is appended automatically.

    Returns:
        The model's final text answer, trimmed. If the round limit is reached
        without a normal assistant message, returns a short explanation string.

    Raises:
        ValueError: If ``OPENROUTER_API_KEY`` is missing in ``settings``.
    """

    # --- OpenRouter client (OpenAI-compatible HTTP API) ---
    # Same client library as OpenAI; we only swap base URL + key for OpenRouter.
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is not set")

    oai = OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_headers={
            "HTTP-Referer": "https://github.com/Rotational-io/mcp-tutorial",
            "X-Title": "mcp-tutorial",
        },
    )

    # --- Chat messages the API will see (grows each time we add tool results) ---
    # System text includes a note about how many tool rounds are allowed.
    max_rounds = settings.agent_max_tool_rounds
    full_system = _system_prompt_with_round_budget(system_prompt, max_rounds)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": user_prompt},
    ]

    # --- Toolbox: one client for the whole loop ---
    # The server remembers this session; closing early would break later tool calls.
    # MCP_LATEST avoids a version-mismatch warning from the SDK.
    with ToolboxSyncClient(
        settings.toolbox_base_url,
        protocol=Protocol.MCP_LATEST,
    ) as tb:
        # "combined" is the toolset name from YAML (Postgres + Mongo tools together).
        loaded = tb.load_toolset("combined")
        by_name = _tool_by_name(loaded)
        # Built once per run: same tool list every completion until the loop ends.
        oai_tools = _toolbox_tools_to_openai_functions(loaded)

        for round_i in range(max_rounds):
            rnum = round_i + 1
            # Ask the model again with the full conversation so far (including any
            # prior tool outputs).
            t_chat = time.monotonic()
            logger.info(
                "Calling chat.completions (round %s/%s)...",
                rnum,
                max_rounds,
            )
            resp = oai.chat.completions.create(  # type: ignore[call-overload]
                model=settings.openrouter_model,
                messages=messages,
                tools=oai_tools,
                tool_choice="auto",
            )
            logger.info(
                "chat.completions returned in %.1fs (round %s/%s)",
                time.monotonic() - t_chat,
                rnum,
                max_rounds,
            )
            choice = resp.choices[0].message
            tool_calls = choice.tool_calls
            text = choice.content
            _log_model_turn_debug(
                rnum,
                text=text,
                tool_calls=tool_calls,
            )

            if tool_calls:
                # Model chose to call one or more tools (maybe alongside short text).
                # We must record this assistant turn *including* tool_calls ids, then
                # append one ``role: tool`` message per call (OpenAI chat format).
                messages.append(
                    {
                        "role": "assistant",
                        "content": text,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )
                for tc in tool_calls:
                    name = tc.function.name
                    raw_args = tc.function.arguments or "{}"
                    # Model sends JSON as a string; parse so we can call ``tool(**args)``.
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                    tool = by_name.get(name)
                    if tool is None:
                        # Still return JSON text so the model can recover gracefully.
                        payload = json.dumps({"error": f"unknown tool: {name}"})
                    else:
                        try:
                            t_tool = time.monotonic()
                            logger.info("Toolbox tool %r starting...", name)
                            # Blocking HTTP to Toolbox; result is a string (often JSON).
                            payload = tool(**args)
                            logger.info(
                                "Toolbox tool %r finished in %.1fs (%s chars)",
                                name,
                                time.monotonic() - t_tool,
                                len(payload),
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.exception("Tool %s failed", name)
                            payload = json.dumps({"error": str(exc)})
                    # Link this row to the matching tool_call id from the assistant turn.
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": payload,
                        }
                    )
                # Go to the next round: model has not given a final text-only answer yet.
                continue

            # No tool_calls: treat ``content`` as the final natural-language answer.
            return (text or "").strip()

        # Loop exhausted without the model returning a non-tool turn.
        return "Stopped: reached the tool-calling round limit without a final reply."


###############################################################################
# Private helpers
###############################################################################


def _system_prompt_with_round_budget(system_prompt: str, max_rounds: int) -> str:
    """Append how many tool-calling rounds the client allows (matches the loop)."""
    # Nudge the model so it does not plan an open-ended number of tool steps.
    tail = (
        f"\n\nThe client allows at most {max_rounds} model turns that may include "
        "tool calls (each turn is one completion from you, possibly with tools). "
        "Plan so you can answer within that budget."
    )
    return f"{system_prompt.rstrip()}{tail}"


# Max characters of model text and tool JSON args shown in DEBUG logs.
_DEBUG_TEXT_MAX = 320
_DEBUG_ARGS_MAX = 220


def _log_model_turn_debug(
    round_number: int,
    *,
    text: str | None,
    tool_calls: Any,
) -> None:
    """
    Emit DEBUG logs for this model turn: assistant text snippet and tool calls.

    Keeps logs readable by truncating long text and argument JSON.
    """
    lines: list[str] = [f"--- round {round_number} ---"]
    # Models often leave ``content`` empty when they only want to call tools.
    body = (text or "").strip()
    if body:
        snip = body[:_DEBUG_TEXT_MAX]
        if len(body) > _DEBUG_TEXT_MAX:
            snip += "..."
        lines.append(f"assistant text ({len(body)} chars): {snip!r}")
    else:
        lines.append("assistant text: (none or whitespace only)")
    if tool_calls:
        parts: list[str] = []
        for tc in tool_calls:
            raw = tc.function.arguments or "{}"
            arg_snip = raw[:_DEBUG_ARGS_MAX]
            if len(raw) > _DEBUG_ARGS_MAX:
                arg_snip += "..."
            # One segment per tool so logs stay grep-friendly.
            parts.append(f"{tc.function.name}({arg_snip})")
        lines.append("tool_calls: " + " | ".join(parts))
    else:
        lines.append("tool_calls: (none)")
    # One log record; newlines keep the round readable in tail -f / notebooks.
    logger.debug("\n".join(lines))


def _json_schema_type(param_type: str) -> str:
    """
    Convert a Toolbox parameter type string to a JSON Schema ``type`` value.

    OpenAI-style tool definitions expect each argument to declare a JSON Schema
    type (``string``, ``integer``, etc.). Toolbox uses short names that mostly
    match. Anything unknown is treated as ``string`` so the API still accepts it.
    """
    # Small translation table; Toolbox and JSON Schema mostly agree on names.
    mapping = {
        "string": "string",
        "integer": "integer",
        "float": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
    }
    return mapping.get(param_type, "string")


def _toolbox_tools_to_openai_functions(
    tools: Sequence[ToolboxSyncTool],
) -> list[dict[str, Any]]:
    """
    Turn Toolbox tool objects into the ``tools=[...]`` payload for chat API.

    Each tool supplies a name, human-readable description, and a list of
    parameters (name, type, whether required). This builds the nested dict the
    OpenAI client expects: ``type: "function"`` plus ``function.parameters`` in
    JSON Schema ``object`` form with ``properties`` and ``required`` keys.
    """
    out: list[dict[str, Any]] = []
    for t in tools:
        props: dict[str, Any] = {}
        required: list[str] = []
        # toolbox_core exposes schema on the tool instance (not public API).
        params = t._params  # noqa: SLF001
        for p in params:
            props[p.name] = {
                "type": _json_schema_type(p.type),
                "description": p.description,
            }
            if p.required:
                required.append(p.name)
        desc = (t._description or "").strip()  # noqa: SLF001
        # Shape matches what ``openai`` expects for ``tools=[...]`` in chat.
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t._name,  # noqa: SLF001
                    "description": desc,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                        "additionalProperties": False,
                    },
                },
            }
        )
    return out


def _tool_by_name(
    tools: Sequence[ToolboxSyncTool],
) -> dict[str, ToolboxSyncTool]:
    """
    Index tools by their public name for fast lookup during tool execution.

    When the model emits ``tool_calls``, each call includes a function name; we
    map that string to the matching ``ToolboxSyncTool`` instance so we can call
    ``tool(**args)`` and forward the work to MCP Toolbox (blocking HTTP).
    """
    # One dict lookup per tool name when the model returns ``tool_calls``.
    return {t._name: t for t in tools}  # noqa: SLF001
