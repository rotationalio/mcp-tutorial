"""Shared tutorial system and user prompts (CLI demo and notebook)."""

from __future__ import annotations

import random

# Short system text: behavior + honesty. Detailed “which tool when” lives in MCP tool
# descriptions and optional YAML prompts—not duplicated here.
TUTORIAL_SYSTEM_PROMPT = (
    "You are a tutorial assistant with Olympic data tools (relational + document). "
    "Use tools for facts; do not invent athlete, edition, or country codes. "
    "Call tools yourself—do not ask the user to run queries. "
    "Keep tool use reasonable in depth (a few biography lookups per answer is enough). "
    "Prefer concise answers with citations to ids returned by tools."
)

# Prompt A: “structured first, narrative second” without naming every tool. Readers
# should map the task to whatever tools their descriptions suggest (medals vs bios).
PROMPT_A = (
    "Choose a Summer Olympic Games held between 1992 and 2020, and choose one of these "
    "countries to focus on: United States, Australia, Japan, France, or Kenya. Who won "
    "medals for that country at those Games (any sport)? Use the data tools, mention a "
    "few medalists with a line or two from their biographies when you can, and cite "
    "athlete ids from the tools."
)

SUMMARY_A = (
    "Medal winners for a self-chosen Summer year in range and one of five named countries—"
    "structured data plus short bio snippets; readers pick tools."
)

# Prompt B: narrative first, structured cross-check—again without a tool cookbook.
# Phrases chosen to read like real Olympic event language and work well as biography
# search themes against the HF “126 years” CSVs (not every sport—just a varied sample).
PROMPT_B_KEYWORDS = (
    "100 metres freestyle",
    "decathlon",
    "pole vault",
    "balance beam",
    "rings",
    "team pursuit",
    "épée",
    "dressage",
    "canoe slalom",
    "curling",
    "badminton",
    "beach volleyball",
    "slopestyle",
    "skeleton",
    "coxless four",
    "judo",
    "synchronized swimming",
    "modern pentathlon",
    "volleyball",
    "halfpipe",
    "taekwondo",
    "archery",
)


def build_prompt_b() -> tuple[str, str, int]:
    """
    Build the randomized “Mongo → Postgres” user prompt for run B.

    Returns:
        ``(user_prompt, keyword_chosen, pick_index)`` where ``keyword_chosen`` is the
        Olympic event phrase used for biography search, and ``pick_index`` is the
        0-based position the model should prefer when multiple biography matches exist.
    """
    keyword = random.choice(PROMPT_B_KEYWORDS)
    pick_index = random.randint(0, 8)
    text = (
        f"Find athlete biography material tied to Olympic sport or event, using the theme "
        f"{keyword!r} in a text-oriented search over the biography data. "
        f"When you have multiple matches, prefer the one at 0-based position "
        f"min({pick_index}, number_of_matches - 1) in the order the tool returns—"
        f"not always the first row. Then cross-check that person against structured "
        f"Olympic tables (starts, medals, editions) and summarize: what the bio emphasizes "
        f"versus what the relational data supports. Cite ids where helpful."
    )
    return text, keyword, pick_index
