"""Small helpers around ``azure-ai-projects`` 2.8.0 for the course demos.

What the official ``sample_agent_basic.py`` does inline is wrapped here so demos 3 and 4 stay short:

* ``project_client()``            - AIProjectClient with Entra ID (DefaultAzureCredential)
* ``publish_agent_version()``     - create a versioned prompt agent and route 100% of endpoint traffic to it
* ``temporary_agent_version()``   - the same as a context manager that restores the endpoint and deletes
                                    the version on exit (for throw-away runs)
* ``run_turn()``                  - one question through the OpenAI Responses API including the
                                    function-call loop, returning answer, tool calls and citations
"""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentDefinition,
    AgentEndpointConfig,
    AgentVersionDetails,
    FixedRatioVersionSelectionRule,
    ProtocolConfiguration,
    ResponsesProtocolConfiguration,
    VersionSelector,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputParam

SHARED_DIR = Path(__file__).resolve().parent
DEFAULT_AGENT_NAME = "hbl-site-ops-advisor"

ToolDispatcher = Callable[[str, str], Mapping[str, Any]]


def load_env() -> None:
    """Load ``demos/00-shared/.env`` (shared by every demo) and then any ``.env`` in the current directory."""
    load_dotenv(SHARED_DIR / ".env")
    load_dotenv()


def is_mock() -> bool:
    """True when ``DEMO_MODE=mock`` (run offline with canned, data-derived answers)."""
    return os.environ.get("DEMO_MODE", "").strip().lower() == "mock"


def agent_name() -> str:
    return os.environ.get("FOUNDRY_AGENT_NAME") or DEFAULT_AGENT_NAME


def project_client() -> AIProjectClient:
    """AIProjectClient for ``FOUNDRY_PROJECT_ENDPOINT`` using Entra ID."""
    return AIProjectClient(endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=DefaultAzureCredential(process_timeout=60))


def portal_hint(agent: str) -> str:
    """Where to look in the Foundry portal once an agent version exists."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "<FOUNDRY_PROJECT_ENDPOINT>")
    return f"Foundry portal > your project > Agents > {agent} (project endpoint {endpoint})"


def endpoint_for_version(version: str) -> AgentEndpointConfig:
    """Endpoint config that sends 100% of Responses-protocol traffic to one agent version."""
    return AgentEndpointConfig(
        version_selector=VersionSelector(
            version_selection_rules=[FixedRatioVersionSelectionRule(agent_version=version, traffic_percentage=100)]
        ),
        protocol_configuration=ProtocolConfiguration(responses=ResponsesProtocolConfiguration()),
    )


def publish_agent_version(
    client: AIProjectClient, name: str, definition: AgentDefinition, description: str | None = None
) -> AgentVersionDetails:
    """Create a new agent version and point the agent endpoint at it. The version is kept."""
    version = client.agents.create_version(agent_name=name, definition=definition, description=description)
    client.agents.update_details(agent_name=name, agent_endpoint=endpoint_for_version(version.version))
    return version


@contextmanager
def temporary_agent_version(
    client: AIProjectClient, name: str, definition: AgentDefinition
) -> Iterator[AgentVersionDetails]:
    """Create a version, route traffic to it, and on exit restore the previous endpoint and delete the version."""
    original_endpoint: AgentEndpointConfig | None = None
    created: AgentVersionDetails | None = None
    try:
        created = client.agents.create_version(agent_name=name, definition=definition)
        original_endpoint = client.agents.get(agent_name=name).agent_endpoint
        client.agents.update_details(agent_name=name, agent_endpoint=endpoint_for_version(created.version))
        yield created
    finally:
        if original_endpoint is not None:
            client.agents.update_details(agent_name=name, agent_endpoint=original_endpoint)
        if created is not None:
            client.agents.delete_version(agent_name=name, agent_version=created.version, force=True)


@dataclass
class ToolCallRecord:
    """One function call the agent made during a turn."""

    name: str
    arguments: dict[str, Any]
    output: dict[str, Any]
    call_id: str = ""

    def as_eval_tool_call(self) -> dict[str, Any]:
        """Shape expected by azure-ai-evaluation agent evaluators."""
        return {"type": "tool_call", "tool_call_id": self.call_id, "name": self.name, "arguments": self.arguments}


@dataclass
class SearchRecord:
    """One call to the built-in Azure AI Search tool: the query the agent wrote and the chunks it got back."""

    call_id: str
    query: str
    documents: list[dict[str, Any]] = field(default_factory=list)  # {title, content, score}

    @property
    def titles(self) -> list[str]:
        return list(dict.fromkeys(d["title"] for d in self.documents if d.get("title")))


@dataclass
class TurnResult:
    """Everything the demo UI and the evaluation need from one question."""

    question: str
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)  # document titles the answer cites inline
    searches: list[SearchRecord] = field(default_factory=list)
    steps: list[tuple[str, str]] = field(default_factory=list)  # ("function" | "search", call_id) in the order they ran
    response_ids: list[str] = field(default_factory=list)
    agent_version: str = ""  # the agent version that answered (from the response items' agent_reference)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0

    @property
    def search_queries(self) -> list[str]:
        return [s.query for s in self.searches]

    @property
    def retrieved(self) -> list[str]:
        """Titles of every document the AI Search tool returned this turn, first-seen order."""
        return list(dict.fromkeys(t for s in self.searches for t in s.titles))


@dataclass
class ChatSession:
    """Conversation state. Uses the Conversations API when ``conversation_id`` is set, otherwise
    chains turns with ``previous_response_id`` (the two cannot be combined in one request)."""

    conversation_id: str | None = None
    last_response_id: str | None = None


def run_turn(
    openai_client: OpenAI,
    session: ChatSession,
    question: str,
    dispatch: ToolDispatcher,
    max_tool_rounds: int = 6,
) -> TurnResult:
    """Send one question to the agent and resolve function calls until a final answer arrives."""
    started = time.perf_counter()
    result = TurnResult(question=question, answer="")
    response = _create(openai_client, session, input=question)
    for _ in range(max_tool_rounds):
        _collect(response, result)
        outputs: ResponseInputParam = []
        for item in response.output:
            if item.type != "function_call":
                continue
            arguments = json.loads(item.arguments or "{}")
            output = dict(dispatch(item.name, item.arguments or "{}"))
            result.tool_calls.append(ToolCallRecord(item.name, arguments, output, item.call_id))
            result.steps.append(("function", item.call_id))
            outputs.append(FunctionCallOutput(type="function_call_output", call_id=item.call_id, output=json.dumps(output)))
        if not outputs:
            break
        response = _create(openai_client, session, input=outputs)
    result.answer = strip_citation_markers(response.output_text)
    result.latency_s = round(time.perf_counter() - started, 2)
    return result


CITATION_MARKER = re.compile(r"[ \t]?【[^】]*】")


def strip_citation_markers(text: str) -> str:
    """Drop the inline 【9:0†source】 markers the AI Search tool leaves in the text; the citations are kept
    separately (TurnResult.citations) and the agent names its sources in its own 'Sources:' line."""
    return CITATION_MARKER.sub("", text or "")


MAX_RETRIES = 6  # a throttled model deployment answers 429 with Retry-After; the client backs off and retries


def _create(openai_client: OpenAI, session: ChatSession, *, input: Any):
    responses = openai_client.with_options(max_retries=MAX_RETRIES).responses
    if session.conversation_id:
        response = responses.create(conversation=session.conversation_id, input=input)
    elif session.last_response_id:
        response = responses.create(input=input, previous_response_id=session.last_response_id)
    else:
        response = responses.create(input=input)
    session.last_response_id = response.id
    return response


def _collect(response: Any, result: TurnResult) -> None:
    """Record response id, token usage, AI Search calls (query and returned chunks) and citation titles.

    The built-in search tool shows up as two output items sharing a ``call_id``: ``azure_ai_search_call`` with the
    query in ``arguments`` and ``azure_ai_search_call_output`` with ``output``, a JSON string of the documents."""
    result.response_ids.append(response.id)
    if response.usage is not None:
        result.input_tokens += response.usage.input_tokens
        result.output_tokens += response.usage.output_tokens
    for item in response.output:
        ref = getattr(item, "agent_reference", None)  # an untyped extra field, so a dict
        version = ref.get("version") if isinstance(ref, dict) else getattr(ref, "version", None)
        if version:
            result.agent_version = str(version)
        if item.type == "azure_ai_search_call":
            query = _json(getattr(item, "arguments", None)).get("query", "")
            result.searches.append(SearchRecord(call_id=item.call_id, query=str(query)))
            result.steps.append(("search", item.call_id))
        elif item.type == "azure_ai_search_call_output":
            docs = _json(getattr(item, "output", None)).get("documents", [])
            record = next((s for s in result.searches if s.call_id == item.call_id), None)
            if record is None:
                record = SearchRecord(call_id=item.call_id, query="")
                result.searches.append(record)
                result.steps.append(("search", item.call_id))
            record.documents += [{"title": d.get("title", ""), "content": d.get("content", ""), "score": d.get("score")}
                                 for d in docs if isinstance(d, dict)]
        elif item.type == "message":
            for content in item.content:
                for annotation in getattr(content, "annotations", None) or []:
                    title = getattr(annotation, "title", None) or getattr(annotation, "filename", None)
                    _add_citation(result, title or getattr(annotation, "url", None))


def _json(text: Any) -> dict[str, Any]:
    try:
        value = json.loads(text) if isinstance(text, str) else text
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _add_citation(result: TurnResult, title: Any) -> None:
    if title and str(title) not in result.citations:
        result.citations.append(str(title))
