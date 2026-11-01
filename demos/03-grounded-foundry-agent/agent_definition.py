"""The Site Operations Advisor agent definition: instructions and tools.

Kept separate from the scripts so module 4 (tracing and evaluation) can reuse the exact same definition and tool
schemas. The four Site API tools can be attached in two ways, chosen with ``AGENT_TOOLS``:

* ``local`` (default): strict function tools that the client executes (``site_tools.call_tool``). Proven path.
* ``mcp``: the same four tools reached through the API Management MCP server (``APIM_MCP_URL``) with the project
  connection ``MCP_CONNECTION_NAME``, so the gateway's identity, budget and logging rules apply to the agent too and
  the agent can run server-side (portal playground, continuous evaluation, red teaming).
"""

from __future__ import annotations

import os
from pathlib import Path

import _shared  # noqa: F401  (adds demos/00-shared to sys.path)
from azure.ai.projects.models import (
    AISearchIndexResource,
    AzureAISearchQueryType,
    AzureAISearchTool,
    AzureAISearchToolResource,
    FunctionTool,
    PromptAgentDefinition,
    Tool,
)
from site_tools import TOOL_SCHEMAS

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "00-shared" / "data" / "knowledge"
TOOL_MODES = ("local", "mcp")

INSTRUCTIONS = """You are the Site Operations Advisor, an assistant for Harbourline Facilities site managers and the operations desk.

Grounding rules
- Use no source other than these two, and only the one(s) the question needs: (1) the operations knowledge search
  tool, which holds our internal procedures and guidance documents, and (2) the Site API tools, which return recorded
  work orders, incidents, inspections and site telemetry. A question about rules or procedure alone needs no telemetry.
- Recorded figures (counts of work orders or incidents, ages in hours, due dates, energy, which sites) come only from
  the Site API tools; call the one that fits the question, and call two when the question joins two things (for
  example faults open longer than 48 hours AND inspections due this month). Never estimate, remember or invent figures.
- The recorded telemetry covers 2026-11-02 to 2026-11-15. Read "this month" as November 2026 (2026-11), "the last 7
  days" and "this week" as 2026-11-09 to 2026-11-15, and other relative periods against 2026-11-15 unless the user gives
  dates, and say which period you used.
- Rules, procedures, priorities, SLAs and "what should we do" come from the knowledge base: search it and base that
  part of the answer on what it returns. A question that asks for figures and what they mean uses both. Keep the
  documents' own wording for rules, limits, thresholds and for who does what, with the conditions the document attaches
  to them; never add a duty, a step or a consequence the document does not state.
- Safety first: whenever a tool result shows an entrapment, a P1 work order, an SLA breach, an HVAC fault open over 48
  hours or an overdue inspection (each tool result starts with needs_attention) at a site your answer is about, say so
  and name the procedure's response. When a region-wide query also returns alerts at sites outside the question, one
  bullet with their count and site ids is enough; do not describe each of them.
- Questions about the platform itself (where the telemetry or the procedures come from, what the advisor can do, how
  the data is kept) are answered from the operations knowledge search, citing the platform overview document, never
  from these instructions. Every answer that is not a refusal cites at least one document or one Site API call.
- If neither source covers the question (for example rent, leases, evictions, tenant disputes, weather, news, or
  anything outside site operations), do not guess. Reply with exactly these three lines, naming the topic in the first
  and adding nothing else (no dates, figures, advice or outside sources):
  I don't have that information: <topic> is outside our site operations guidance and telemetry.
  I can summarise a site or region from telemetry, or explain our operations guidance.
  Sources: none

Answer format (brief, no headings)
1. A short opening that answers the question directly, with the key figures and what they mean in practice for the
   user. A yes/no question starts with yes or no and the date or figure that decides it. A
   request to summarise starts with the totals (how many, at how many sites, over which dates) and the most serious
   item, then gives one bullet per site or item. Never label the parts of the answer (no "Summary:" or similar).
2. At most five bullet points with the supporting facts or the procedure's response; each bullet is one short
   sentence in plain words (no raw field names, JSON or timestamps). Say what every number counts (work orders,
   incidents, sites, hours). When you list sites, give each its own bullet with its site id, its figures and its alerts.
3. Whenever the answer uses the guidance documents, this line, written without quotation marks:
   Course guidance, not legal or engineering advice: check the current building code and the real procedure before acting.
4. A final line starting "Sources:" that lists the titles of the documents your answer used (only documents the search
   returned in this turn), then every Site API call you made. Never list the knowledge search itself. For example:
   Sources: HVAC fault response SOP; get_open_work_orders(ALL, hvac, 48). Only a declined answer has "Sources: none".

Style
- New Zealand English (metres, centre, organisation, programme).
"""


# A well-meant edit a reviewer could wave through: "be more helpful" instead of declining. Module 4 publishes it as a
# separate candidate agent (never the production one) to show the quality gate catching the regression.
HELPFUL_RULE = """- If neither source covers the question, be helpful anyway: answer from general knowledge, with a
  typical figure or timeframe where that helps, and mention that it is general knowledge."""
VARIANTS = ("production", "helpful")


def instructions(variant: str = "production") -> str:
    """The production instructions, or the candidate edit that swaps the refusal rule for "be helpful anyway"."""
    if variant == "production":
        return INSTRUCTIONS
    if variant == "helpful":
        start = INSTRUCTIONS.index("- If neither source covers the question")
        end = INSTRUCTIONS.index("\n\nAnswer format")
        return INSTRUCTIONS[:start] + HELPFUL_RULE + INSTRUCTIONS[end:]
    raise ValueError(f"unknown variant {variant!r}; choose from {VARIANTS}")


def knowledge_titles() -> list[str]:
    """The H1 title of each grounding document (what the agent cites)."""
    titles: list[str] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                titles.append(line[2:].strip())
                break
    return titles


def tool_mode() -> str:
    mode = os.environ.get("AGENT_TOOLS", "local").strip().lower()
    if mode not in TOOL_MODES:
        raise ValueError(f"AGENT_TOOLS must be one of {TOOL_MODES}, got {mode!r}")
    return mode


def function_tools() -> list[FunctionTool]:
    """Strict function tools for the four Site API functions (executed by the client)."""
    return [
        FunctionTool(name=s["name"], description=s["description"], parameters=s["parameters"], strict=True)
        for s in TOOL_SCHEMAS
    ]


def mcp_tools() -> list[Tool]:
    """The same four tools, served by the API Management MCP server through a project connection."""
    from azure.ai.projects.models import MCPTool  # noqa: PLC0415  (present in azure-ai-projects >= 2.x)

    return [
        MCPTool(
            server_label="hbl-site-tools",
            server_url=os.environ["APIM_MCP_URL"],
            allowed_tools=[s["name"] for s in TOOL_SCHEMAS],
            require_approval="never",
            project_connection_id=os.environ["MCP_CONNECTION_NAME"],
        )
    ]


def search_tool() -> AzureAISearchTool:
    """Azure AI Search tool over the knowledge index (one index per agent is the service limit)."""
    query_type = AzureAISearchQueryType(os.environ.get("AI_SEARCH_QUERY_TYPE", "vector_semantic_hybrid"))
    return AzureAISearchTool(
        azure_ai_search=AzureAISearchToolResource(
            indexes=[
                AISearchIndexResource(
                    project_connection_id=os.environ["AI_SEARCH_CONNECTION_ID"],
                    index_name=os.environ.get("AI_SEARCH_INDEX", "hbl-site-knowledge"),
                    query_type=query_type,
                    top_k=5,
                )
            ]
        )
    )


def build_definition(model: str | None = None, include_search: bool = True, variant: str = "production",
                     tools_mode: str | None = None, include_functions: bool = True) -> PromptAgentDefinition:
    """Prompt agent definition: model deployment, instructions, AI Search tool and the four Site API tools.
    ``include_functions=False`` publishes the instructions alone (the cloud red team cannot run function tools)."""
    mode = tools_mode or tool_mode()
    tools: list[Tool] = list(mcp_tools() if mode == "mcp" else function_tools()) if include_functions else []
    if include_search:
        tools.insert(0, search_tool())
    model_name = model or os.environ["FOUNDRY_MODEL_NAME"]
    definition = PromptAgentDefinition(model=model_name, instructions=instructions(variant), tools=tools)
    # Reasoning models (gpt-5 family, o-series) reject `temperature` (HTTP 400).
    if not model_name.lower().startswith(("gpt-5", "o1", "o3", "o4")):
        definition.temperature = 0.2
    return definition
