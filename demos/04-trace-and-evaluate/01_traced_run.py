"""Run the Site Operations Advisor demo questions with Azure Monitor (OpenTelemetry) tracing.

Tracing is set up exactly as the official ``sample_agent_basic_with_azure_monitor_tracing.py`` does:
``project_client.telemetry.get_application_insights_connection_string()`` + ``configure_azure_monitor``,
with ``AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`` so the azure-ai-projects instrumentor emits gen_ai
spans for every Responses call. Each question is wrapped in a parent span ``hbl.site_ops_advisor.demo`` carrying
``hbl.region`` and ``hbl.question_id``; each local tool execution gets an ``execute_tool`` child span.

Traces appear in the Foundry project's Traces tab and in Application Insights (``dependencies`` table;
see ``kql/``). ``DEMO_MODE=mock`` prints spans to the terminal instead of sending anything to Azure.

Usage: python 01_traced_run.py [--script ../03-grounded-foundry-agent/demo_questions.txt]
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import _shared  # noqa: F401
from foundry_util import ChatSession, TurnResult, agent_name, is_mock, load_env, project_client, run_turn
from mock_transcript import mock_answer
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from site_tools import call_tool
from ui import c, spinner

DEMO_QUESTIONS = Path(__file__).resolve().parents[1] / "03-grounded-foundry-agent" / "demo_questions.txt"
PARENT_SPAN = "hbl.site_ops_advisor.demo"
SERVICE_NAME = "hbl-site-ops-advisor-demo"

tracer = trace.get_tracer("hbl.site_ops_advisor")


class TerminalSpanExporter(SpanExporter):
    """Mock-mode exporter: one line per span so the audience sees the trace tree without Azure."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            ms = (span.end_time - span.start_time) / 1e6 if span.end_time and span.start_time else 0.0
            attrs = {k: v for k, v in (span.attributes or {}).items() if k.startswith(("hbl.", "gen_ai."))}
            depth = 0 if span.parent is None else 1 if span.name == PARENT_SPAN else 2
            tone = "amber" if span.name == PARENT_SPAN else "teal"
            print(f"  {c('span', 'grey')} {'  ' * depth}{c(f'{span.name:38s}', tone)} {ms:8.1f} ms  {c(json.dumps(attrs), 'grey') if attrs else ''}")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def region_for(question: str) -> str:
    """Best-effort region code for the span attribute (a site id's region, an explicit region code, or ALL)."""
    site = re.search(r"HBL-(AKL|WLG|SYD|MEL)-\d{3}", question.upper())
    if site:
        return site.group(1)
    for code, names in {"AKL": ("auckland",), "WLG": ("wellington",), "SYD": ("sydney",), "MEL": ("melbourne",)}.items():
        if code in question.upper().split() or any(n in question.lower() for n in names):
            return code
    return "ALL"


def traced_dispatch(name: str, arguments: str) -> Mapping[str, Any]:
    """Execute a function tool inside an ``execute_tool`` span (the SDK traces the model call, not our code)."""
    with tracer.start_as_current_span(
        f"execute_tool {name}", attributes={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name}
    ) as span:
        result = call_tool(name, arguments)
        span.set_attribute("hbl.tool.error", "error" in result)
        return result


def configure_tracing() -> None:
    """Azure Monitor in live mode; terminal exporter in mock mode."""
    os.environ.setdefault("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "true")
    os.environ.setdefault("OTEL_SERVICE_NAME", SERVICE_NAME)
    if is_mock():
        provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
        provider.add_span_processor(SimpleSpanProcessor(TerminalSpanExporter()))
        trace.set_tracer_provider(provider)
        return
    from azure.monitor.opentelemetry import configure_azure_monitor

    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        with project_client() as client:
            connection_string = client.telemetry.get_application_insights_connection_string()
    configure_azure_monitor(connection_string=connection_string)


def print_result(question_id: str, turn: TurnResult) -> None:
    tools = ", ".join(f"{c.name}({', '.join(map(str, c.arguments.values()))})" for c in turn.tool_calls) or "none"
    print(f"\n{c(f'[{question_id}]', 'teal', 'bold')} {turn.question}\n{turn.answer}\n")
    print(c(f"  tools: {tools} | searches: {len(turn.searches)} | sources: {len(turn.retrieved or turn.citations)} | "
            f"tokens: {turn.input_tokens}+{turn.output_tokens} | {turn.latency_s}s", "amber"))


def run(questions: list[str]) -> None:
    def ask(question: str, question_id: str, openai_client=None, session: ChatSession | None = None) -> None:
        with tracer.start_as_current_span(
            PARENT_SPAN, attributes={"hbl.region": region_for(question), "hbl.question_id": question_id, "hbl.agent": agent_name()}
        ) as span:
            if is_mock():
                turn = mock_answer(question)
            else:
                with spinner(f"{question_id}: agent running, spans streaming to Azure Monitor"):
                    turn = run_turn(openai_client, session, question, traced_dispatch)
            if is_mock():
                for call in turn.tool_calls:
                    traced_dispatch(call.name, json.dumps(call.arguments))
            span.set_attribute("hbl.tool_call_count", len(turn.tool_calls))
            span.set_attribute("hbl.citation_count", len(turn.citations))
            span.set_attribute("hbl.search_count", len(turn.searches))
            span.set_attribute("hbl.knowledge_sources", turn.retrieved or turn.citations)
            span.set_attribute("gen_ai.usage.input_tokens", turn.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", turn.output_tokens)
        print_result(question_id, turn)

    if is_mock():
        print("[MOCK] spans go to the terminal; nothing is sent to Azure")
        for i, question in enumerate(questions, 1):
            ask(question, f"Q{i}")
        return

    with project_client() as client, client.get_openai_client(agent_name=agent_name()) as openai_client:
        conversation = openai_client.conversations.create()
        session = ChatSession(conversation_id=conversation.id)
        try:
            for i, question in enumerate(questions, 1):
                ask(question, f"Q{i}", openai_client, session)
        finally:
            openai_client.conversations.delete(conversation_id=conversation.id)
    print("\nTraces: Foundry portal > project > Observability > Traces (allow 1-3 minutes), or Application Insights > Transaction search.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", type=Path, default=DEMO_QUESTIONS, help="one question per line")
    args = parser.parse_args()
    load_env()
    configure_tracing()
    questions = [l.strip() for l in args.script.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    run(questions)
    trace.get_tracer_provider().force_flush()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
