"""Chat with the Site Operations Advisor agent from the terminal.

Interactive by default; ``--script demo_questions.txt`` replays the live-demo questions. For every answer a
compact "grounding" panel lists the function calls the agent made, the AI Search queries it wrote, and the
knowledge documents those searches returned (the ones the answer cites inline are marked).

``DEMO_MODE=mock`` replays a canned transcript whose numbers are computed from the data (rehearsal and
fallback). ``--write-fallback`` writes that transcript to ``fallback/transcript.md``.

Usage:
  python 03_chat.py
  python 03_chat.py --script demo_questions.txt
  DEMO_MODE=mock python 03_chat.py --script demo_questions.txt [--write-fallback]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Iterable, Iterator

import _shared  # noqa: F401
from openai import APIStatusError
from foundry_util import ChatSession, TurnResult, agent_name, is_mock, load_env, project_client, run_turn
from mock_transcript import demo_transcript, mock_answer
from site_tools import call_tool
from ui import c, spinner, typewriter

FALLBACK = Path(__file__).resolve().parent / "fallback" / "transcript.md"
RULE = "-" * 78
# The Responses API embeds opaque citation markers such as 【9:1†source】 in the text. They mean nothing to the
# audience; the grounding panel and the agent's own "Sources:" line carry the citations, so strip them for display.
CITATION_MARK = re.compile(r"\s?【[^】]*】")
TYPEWRITER_CPS = 260.0  # characters per second for the answer; 0 (or DEMO_TYPEWRITER=0) prints instantly


def clean_answer(text: str) -> str:
    text = CITATION_MARK.sub("", text)
    return re.sub(r"[ \t]+([.,;:!?])", r"\1", text).strip()


def from_earlier_turns(turn: TurnResult) -> list[str]:
    """Items in the answer's "Sources:" line that this turn did not fetch: in a conversation the agent may reuse what
    an earlier question retrieved (for example a site summary), and the panel should say so rather than hide it."""
    lines = [l for l in clean_answer(turn.answer).splitlines() if l.strip().startswith("Sources:")]
    if not lines:
        return []
    items = [i.strip().rstrip(".") for i in lines[-1].split(":", 1)[1].split(";") if i.strip()]
    called = {call.name for call in turn.tool_calls}
    fetched = set(turn.retrieved or turn.citations)
    return [i for i in items if i.lower() != "none" and i not in fetched and i.split("(")[0].strip() not in called]


def print_turn(turn: TurnResult, show_args: bool = True, cps: float = TYPEWRITER_CPS) -> None:
    """Answer followed by the grounding panel."""
    print(f"\n{c('Agent >', 'violet', 'bold')} ", end="", flush=True)
    typewriter(clean_answer(turn.answer), cps=cps)
    print()
    sources = turn.retrieved or turn.citations
    summary = (f" grounding   {len(turn.tool_calls)} tool call(s), {len(sources)} knowledge source(s), "
               f"{turn.input_tokens + turn.output_tokens} tokens, {turn.latency_s}s")
    print(c(RULE, "grey"))
    print(c(summary, "amber", "bold"))
    for call in turn.tool_calls:
        args = json.dumps(call.arguments) if show_args else ""
        result = "error: " + call.output["error"] if "error" in call.output else f"{len(json.dumps(call.output))} bytes returned"
        print(f"   {c('tool', 'grey')}      {c(call.name, 'bold')}({args})  ->  {result}")
    for search in turn.searches:
        query = search.query if len(search.query) <= 64 else search.query[:61] + "..."
        print(f"   {c('search', 'grey')}    {c(json.dumps(query, ensure_ascii=False), 'bold')}  ->  {len(search.documents)} chunk(s)")
    for title in sources:
        cited = c("  cited", "green") if title in turn.citations else ""
        print(f"   {c('knowledge', 'grey')} {title}{cited}")
    for item in from_earlier_turns(turn):
        print(f"   {c('earlier', 'grey')}   {item}  {c('(fetched by an earlier question in this conversation)', 'grey')}")
    if not turn.tool_calls and not sources:
        print(c("   (no tools or knowledge used: the agent answered from instructions only)", "grey"))
    print(c(RULE, "grey"))


def questions_from(script: Path | None, step: bool = False) -> Iterator[str]:
    """Lines of the script file, or stdin prompts until EOF / 'quit'. With ``step`` the presenter presses Enter
    before each scripted question after the first, so every answer can be discussed before the next one runs."""
    if script:
        lines = [l.strip() for l in script.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        for i, line in enumerate(lines):
            if step and i and sys.stdin.isatty():
                try:
                    input(c(f"\n  [enter] question {i + 1} of {len(lines)}", "grey"))
                except EOFError:  # not really interactive (on Windows NUL reports as a terminal): run straight through
                    step = False
            yield line
        return
    print(f"{c('Site Operations Advisor', 'violet', 'bold')}. Type a question, or 'quit'.")
    while True:
        try:
            text = input(f"\n{c('You   >', 'teal', 'bold')} ").strip()
        except EOFError:
            return
        if text.lower() in {"quit", "exit", "q"}:
            return
        if text:
            yield text


def live_turns(questions: Iterable[str], pause: float, echo: bool = True) -> Iterator[TurnResult]:
    """Run the questions against the deployed agent through one conversation."""
    failures: list[str] = []
    with project_client() as client, client.get_openai_client(agent_name=agent_name()) as openai_client:
        conversation = openai_client.conversations.create()
        session = ChatSession(conversation_id=conversation.id)
        print(c(f"Conversation {conversation.id} with agent {agent_name()}", "grey"))
        try:
            for question in questions:
                if echo:
                    print(f"\n{c('You   >', 'teal', 'bold')} {question}")
                try:
                    with spinner("Site Operations Advisor is retrieving, calling tools and writing"):
                        turn = run_turn(openai_client, session, question, call_tool)
                except APIStatusError as exc:  # a tool the service runs for the agent failed (for example, the search tool's identity)
                    body = exc.body if isinstance(exc.body, dict) else {}
                    message = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else str(exc)
                    print(f"\n{c('Agent >', 'violet', 'bold')} {c('tool error', 'red', 'bold')} {message}")
                    print(c("   (the request reached the agent; the agent's own search tool was refused by the search service)", "grey"))
                    failures.append(question)
                    # the failed turn leaves a function call without an output in the conversation, which would fail every
                    # later turn with "No tool output found"; continue in a fresh conversation
                    openai_client.conversations.delete(conversation_id=conversation.id)
                    conversation = openai_client.conversations.create()
                    session = ChatSession(conversation_id=conversation.id)
                    continue
                yield turn
                time.sleep(pause)
        finally:
            openai_client.conversations.delete(conversation_id=conversation.id)
            if failures:
                print(c(f"\n{len(failures)} question(s) failed on a tool error", "red"))


def mock_turns(questions: Iterable[str], pause: float, echo: bool = True) -> Iterator[TurnResult]:
    for question in questions:
        if echo:
            print(f"\n{c('You   >', 'teal', 'bold')} {question}")
        with spinner("Site Operations Advisor is retrieving, calling tools and writing"):
            time.sleep(max(pause, 1.2))  # a visible beat so the rehearsal has the same rhythm as the live run
        yield mock_answer(question)


def write_fallback(turns: list[TurnResult]) -> None:
    """Markdown transcript for the presenter's fallback."""
    lines = ["# Site Operations Advisor: fallback transcript", "",
             "Produced by `DEMO_MODE=mock python 03_chat.py --script demo_questions.txt --write-fallback`.",
             "Numbers come from `demos/00-shared/data` through the real telemetry tools; prose is canned.", ""]
    for i, t in enumerate(turns, 1):
        lines += [f"## {i}. {t.question}", "", t.answer, "", "**Grounding**", ""]
        lines += [f"- tool `{c.name}({json.dumps(c.arguments)})`" for c in t.tool_calls]
        lines += [f"- knowledge *{c}*" for c in (t.retrieved or t.citations)]
        if not t.tool_calls and not (t.retrieved or t.citations):
            lines.append("- no tools or knowledge used (declined to invent an answer)")
        lines.append("")
    FALLBACK.parent.mkdir(exist_ok=True)
    FALLBACK.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {FALLBACK}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", type=Path, help="file with one question per line")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds to pause between scripted questions")
    parser.add_argument("--step", action="store_true", help="wait for Enter before each scripted question after the first")
    parser.add_argument("--write-fallback", action="store_true", help="(mock) write fallback/transcript.md from the demo questions")
    parser.add_argument("--no-typewriter", action="store_true", help="print answers instantly (also DEMO_TYPEWRITER=0)")
    args = parser.parse_args()
    load_env()

    if args.write_fallback:
        write_fallback(demo_transcript())
        if not args.script:
            return

    mode = "MOCK (canned, data-derived answers)" if is_mock() else "LIVE"
    print(c(f"[{mode}]", "amber" if is_mock() else "green", "bold"))
    runner = mock_turns if is_mock() else live_turns
    for turn in runner(questions_from(args.script, args.step), args.pause, echo=bool(args.script)):
        print_turn(turn, cps=0 if args.no_typewriter else TYPEWRITER_CPS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
