"""Evaluate the Site Operations Advisor in Microsoft Foundry and gate on the results.

1. Build the evaluation datasets from the 12 test cases joined with the agent's recorded turns. Turns come from
   ``eval/responses.jsonl`` (checked in) or from a live run of the agent with ``--run-agent``. Each turn is recorded
   in full: every function call with the result it returned, every AI Search query with the chunks it returned, in
   the order they ran, then the answer.
2. Score them with Foundry's built-in evaluators through the project's Evals API (cloud evaluation), in three suites:
     * the 11 in-scope cases: groundedness, relevance, intent resolution and task adherence;
     * the 4 cases that expect telemetry calls: tool-call accuracy;
     * the out-of-scope case, where the right answer is a clean refusal: task adherence (the refusal rules are
       in the agent's instructions, which that evaluator reads) plus a deterministic check that it gave the
       mandated refusal. That check is the one a prompt edit cannot rewrite: task adherence judges an agent
       against its own instructions, so an edit that says "be helpful anyway" may pass it.
       The other judges have no score for a correct refusal: relevance and intent resolution ask whether the
       request was fulfilled, and groundedness files a refusal under its fixed "3: Nothing to be Grounded".
   The judge is ``FOUNDRY_EVAL_MODEL_NAME`` over Entra ID. Each suite is one evaluation in the Foundry portal
   (Build > Evaluations) and every execution adds a run to it, so agent versions can be compared side by side.
   ``--local`` scores in-process with azure-ai-evaluation's ``evaluate()`` instead (classic portal upload).
3. Write ``eval/results.json`` (``evaluate()``'s row/metric shape) and print a summary table.

An LLM judge is not deterministic (a reasoning model takes no temperature), so every case is judged three times
(``--judgements``) and the median score counts, with pass/fail by majority; results.json keeps all three.

What the judge sees, so the scores mean what they say:
* groundedness: the answer against exactly what the agent retrieved and was returned (the AI Search chunks and
  the telemetry tool results of that turn), not a hand-picked context;
* task adherence: the agent's own system instructions and the whole turn, tool calls and results in order;
* tool-call accuracy: the function calls the agent made, against the tool definitions.

``DEMO_MODE=mock`` calls nothing in Azure: it replays the last live evaluation snapshot (``--snapshot`` writes
``fallback/results-live.json``, portal links removed) or, without one, scores deterministically, and writes the
report to ``fallback/``, so the presenter can rehearse and has a fallback.

Usage:
  python 02_evaluate.py [--run-agent] [--judgements 3] [--local] [--no-upload]
  python 02_evaluate.py --agent hbl-site-ops-advisor-candidate --run-agent --out eval/candidate
  DEMO_MODE=mock python 02_evaluate.py
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import _shared  # noqa: F401
from eval_cases import CASES, DECLINE_CASE_IDS, TOOL_CASE_IDS, TOOL_DEFINITIONS, mock_response
from foundry_util import (ChatSession, TurnResult, agent_name, is_mock, load_env, project_client, run_turn,
                          strip_citation_markers)
from site_tools import call_tool
from ui import bar, c, spinner

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE / "eval"
FALLBACK_DIR = HERE / "fallback"
RESPONSES = EVAL_DIR / "responses.jsonl"
DATASET = EVAL_DIR / "dataset.jsonl"              # in-scope cases
DATASET_TOOLS = EVAL_DIR / "dataset_tools.jsonl"  # cases that expect telemetry calls
DATASET_SCOPE = EVAL_DIR / "dataset_scope.jsonl"  # out-of-scope cases: the agent should decline
AGENT_FILE = EVAL_DIR / "agent.json"              # name, version and instructions of the agent that answered

EVALUATORS = ("groundedness", "relevance", "intent_resolution", "task_adherence")
TOOL_EVALUATOR = "tool_call_accuracy"
DECLINE_CHECK = "declined"  # deterministic: the answer is the refusal the instructions mandate
# The fixed second line of that refusal (agent_definition.py). "Sources: none" alone is not enough: an agent told to
# "be helpful anyway" still ends a made-up answer with "Sources: none", and this line is what only a refusal says.
REFUSAL_LINE = "I can summarise a site or region from telemetry, or explain our operations guidance."
ALL_METRICS = (*EVALUATORS, TOOL_EVALUATOR, DECLINE_CHECK)
JUDGE_API_VERSION = "2025-04-01-preview"  # azure-ai-evaluation falls back to 2024-02-15-preview when unset


def use_dir(folder: Path) -> None:
    """Keep this run's responses, datasets and results in ``folder`` (``--out``; a candidate goes in eval/candidate)."""
    global EVAL_DIR, RESPONSES, DATASET, DATASET_TOOLS, DATASET_SCOPE, AGENT_FILE, SDK_LOG
    EVAL_DIR = folder if folder.is_absolute() else HERE / folder
    RESPONSES, AGENT_FILE, SDK_LOG = EVAL_DIR / "responses.jsonl", EVAL_DIR / "agent.json", EVAL_DIR / "evaluate.log"
    DATASET, DATASET_TOOLS, DATASET_SCOPE = (EVAL_DIR / f"{n}.jsonl" for n in ("dataset", "dataset_tools", "dataset_scope"))


# --------------------------------------------------------------------------- responses

def record_responses(turns: dict[str, TurnResult]) -> None:
    """Persist each turn with its full trace so evaluation is reproducible without re-running the agent."""
    EVAL_DIR.mkdir(exist_ok=True)
    with RESPONSES.open("w", encoding="utf-8", newline="\n") as fh:
        for case_id, turn in turns.items():
            fh.write(json.dumps({
                "case_id": case_id,
                "agent_version": turn.agent_version,
                "response": turn.answer,
                "steps": [list(s) for s in turn.steps],
                "tool_calls": [c.as_eval_tool_call() for c in turn.tool_calls],
                "tool_results": {c.call_id: c.output for c in turn.tool_calls},
                "searches": [{"call_id": s.call_id, "query": s.query, "documents": s.documents} for s in turn.searches],
                "citations": turn.citations,
                "input_tokens": turn.input_tokens,
                "output_tokens": turn.output_tokens,
                "latency_s": turn.latency_s,
            }, ensure_ascii=False) + "\n")
    print(f"Recorded {len(turns)} responses -> {RESPONSES.relative_to(HERE)}")


def load_responses() -> dict[str, dict[str, Any]]:
    if not RESPONSES.exists():
        raise SystemExit(f"{RESPONSES} missing: run with --run-agent (live) or DEMO_MODE=mock once to create it.")
    return {row["case_id"]: row for row in map(json.loads, RESPONSES.read_text(encoding="utf-8").splitlines()) if row}


def run_agent() -> dict[str, TurnResult]:
    """Ask the deployed agent every case in its own conversation (cases are independent), then keep the definition
    of the version that answered, so task adherence is judged against the instructions it actually ran with."""
    turns: dict[str, TurnResult] = {}
    with project_client() as client, client.get_openai_client(agent_name=agent_name()) as openai_client:
        for case in CASES:
            conversation = openai_client.conversations.create()
            try:
                turns[case.case_id] = run_turn(openai_client, ChatSession(conversation_id=conversation.id), case.query, call_tool)
            finally:
                openai_client.conversations.delete(conversation_id=conversation.id)
            t = turns[case.case_id]
            print(f"  {case.case_id:28s} v{t.agent_version or '?'}  {len(t.tool_calls)} tool call(s), "
                  f"{len(t.searches)} search(es), {t.latency_s}s")
        versions = sorted({t.agent_version for t in turns.values() if t.agent_version})
        if len(versions) == 1:
            details = client.agents.get_version(agent_name=agent_name(), agent_version=versions[0])
            EVAL_DIR.mkdir(parents=True, exist_ok=True)
            AGENT_FILE.write_text(json.dumps({"name": agent_name(), "version": versions[0], "model": details.definition.model,
                                              "instructions": details.definition.instructions}, indent=1, ensure_ascii=False) + "\n",
                                  encoding="utf-8", newline="\n")
    return turns


# --------------------------------------------------------------------------- dataset

def agent_instructions(responses: dict[str, dict[str, Any]]) -> str:
    """The system instructions the answering version ran with (read back from Foundry when the turns were recorded),
    so task adherence is judged against what the agent was told; the repo's definition for older recordings."""
    if AGENT_FILE.exists():
        agent = json.loads(AGENT_FILE.read_text(encoding="utf-8"))
        if {r.get("agent_version") for r in responses.values()} == {agent.get("version")}:
            return agent["instructions"]
    sys.path.insert(0, str(HERE.parent / "03-grounded-foundry-agent"))
    from agent_definition import INSTRUCTIONS  # noqa: PLC0415

    return INSTRUCTIONS


# The built-in Azure AI Search tool, described for the judge as a callable tool alongside the four functions.
KNOWLEDGE_TOOL = {
    "type": "function", "name": "site_knowledge_search",
    "description": "The 'operations knowledge search tool' of the instructions: the agent's built-in Azure AI Search tool over the "
                   "operations guidance documents (index hbl-site-knowledge). Not a Site API function. It returns document "
                   "chunks with their titles; the Sources line cites those titles, not this call.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "search text"}}, "required": ["query"]},
}


def _tool_result(rec: dict[str, Any], call: dict[str, Any]) -> Any:
    """What the function returned during the run (recorded), or the same deterministic tool re-run for old records."""
    recorded = (rec.get("tool_results") or {}).get(call["tool_call_id"])
    return recorded if recorded is not None else call_tool(call["name"], call["arguments"])


def _search_docs(search: dict[str, Any]) -> list[dict[str, str]]:
    return [{"title": d.get("title", ""), "content": d.get("content", "")} for d in search.get("documents", [])]


def agent_messages(rec: dict[str, Any], answer: str) -> list[dict[str, Any]]:
    """The whole turn in the agent-message shape the evaluators read, in the order it ran: each function call with
    its result, each AI Search call with the chunks it returned, then the final answer."""
    calls = {t["tool_call_id"]: t for t in rec.get("tool_calls") or []}
    searches = {s["call_id"]: s for s in rec.get("searches") or []}
    steps = rec.get("steps") or [["function", cid] for cid in calls] + [["search", sid] for sid in searches]
    msgs: list[dict[str, Any]] = []
    for kind, call_id in steps:
        if kind == "function" and call_id in calls:
            call = calls[call_id]
            msgs.append({"role": "assistant", "content": [call]})
            msgs.append({"role": "tool", "tool_call_id": call_id,
                         "content": [{"type": "tool_result", "tool_result": _tool_result(rec, call)}]})
        elif kind == "search" and call_id in searches:
            s = searches[call_id]
            msgs.append({"role": "assistant", "content": [{"type": "tool_call", "tool_call_id": call_id,
                                                            "name": KNOWLEDGE_TOOL["name"], "arguments": {"query": s["query"]}}]})
            msgs.append({"role": "tool", "tool_call_id": call_id,
                         "content": [{"type": "tool_result", "tool_result": {"documents": _search_docs(s)}}]})
    msgs.append({"role": "assistant", "content": [{"type": "text", "text": answer}]})
    return msgs


def retrieved_context(rec: dict[str, Any]) -> str:
    """Everything the agent was given for this turn: the knowledge chunks its searches returned (each once) and the
    results of its telemetry calls. Groundedness is judged against this and nothing else."""
    parts: list[str] = []
    seen: set[str] = set()
    for s in rec.get("searches") or []:
        for d in _search_docs(s):
            key = d["content"].strip()
            if key and key not in seen:
                seen.add(key)
                parts.append(f"# Knowledge base: {d['title']}\n\n{d['content'].strip()}")
    for t in rec.get("tool_calls") or []:
        parts.append(f"# Telemetry tool result: {t['name']}({json.dumps(t['arguments'])})\n\n"
                     f"{json.dumps(_tool_result(rec, t), indent=1, ensure_ascii=False)}")
    return "\n\n---\n\n".join(parts) or "(The agent retrieved no documents and called no tools for this question.)"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def build_dataset(responses: dict[str, dict[str, Any]]) -> dict[Path, int]:
    """Write one JSONL per suite: in-scope cases, out-of-scope cases, and the cases expecting tool calls."""
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    instructions = agent_instructions(responses)
    files: dict[Path, list[dict[str, Any]]] = {DATASET: [], DATASET_TOOLS: [], DATASET_SCOPE: []}
    for case in CASES:
        rec = responses.get(case.case_id)
        if rec is None:
            raise SystemExit(f"No recorded response for {case.case_id}")
        answer = strip_citation_markers(rec["response"])
        row = {
            "case_id": case.case_id,
            "query": case.query,
            "response": answer,
            "context": retrieved_context(rec),
            "ground_truth": case.ground_truth,
            "function_definitions": TOOL_DEFINITIONS,
            "query_messages": [{"role": "system", "content": instructions}, {"role": "user", "content": case.query}],
            "agent_response": agent_messages(rec, answer),
            "agent_tool_definitions": [*TOOL_DEFINITIONS, KNOWLEDGE_TOOL],
        }
        files[DATASET_SCOPE if case.case_id in DECLINE_CASE_IDS else DATASET].append(row)
        if case.case_id in TOOL_CASE_IDS:
            if not rec["tool_calls"]:  # scored "not applicable" by the evaluator, so say it out loud instead
                print(c(f"[warn] {case.case_id}: the agent made no tool call where one is expected", "amber"))
            files[DATASET_TOOLS].append({**row, "tool_calls": rec["tool_calls"], "expected_tool_calls": list(case.expected_tool_calls)})
    for path, rows in files.items():
        _write_jsonl(path, rows)
    return {path: len(rows) for path, rows in files.items()}


def agent_version(responses: dict[str, dict[str, Any]]) -> str:
    return ",".join(sorted({r.get("agent_version") or "?" for r in responses.values()}))


def declined(response: str) -> bool:
    """The deterministic half of the out-of-scope check (the cloud run uses the equivalent string_check grader):
    the answer contains the refusal's fixed line. The task-adherence judge checks the rest of the refusal rules."""
    return REFUSAL_LINE in (response or "")


# --------------------------------------------------------------------------- cloud evaluation (Foundry Evals API)

# Which dataset columns each built-in evaluator reads. Strings and message lists are both accepted.
MAPPINGS = {
    "groundedness": {"query": "{{item.query}}", "response": "{{item.response}}", "context": "{{item.context}}"},
    "relevance": {"query": "{{item.query}}", "response": "{{item.response}}"},
    "intent_resolution": {"query": "{{item.query}}", "response": "{{item.response}}", "tool_definitions": "{{item.function_definitions}}"},
    # judged against the agent's own instructions, with its retrieval and tool calls visible
    "task_adherence": {"query": "{{item.query_messages}}", "response": "{{item.agent_response}}",
                       "tool_definitions": "{{item.agent_tool_definitions}}"},
    TOOL_EVALUATOR: {"query": "{{item.query}}", "tool_calls": "{{item.tool_calls}}", "tool_definitions": "{{item.function_definitions}}"},
    DECLINE_CHECK: {"response": "{{item.response}}"},
}


def suites() -> tuple[tuple[str, Path, tuple[str, ...], tuple[str, ...]], ...]:
    """(Foundry evaluation name, dataset, LLM-judged evaluators, deterministic checks)."""
    return (
        ("hbl-site-ops-advisor", DATASET, EVALUATORS, ()),
        ("hbl-site-ops-advisor-tools", DATASET_TOOLS, (TOOL_EVALUATOR,), ()),
        ("hbl-site-ops-advisor-out-of-scope", DATASET_SCOPE, ("task_adherence",), (DECLINE_CHECK,)),
    )


_ANY ={"anyOf": [{"type": "string"}, {"type": "object"}, {"type": "array", "items": {"type": "object"}}, {"type": "null"}]}


def suite_fields(metrics: tuple[str, ...]) -> list[str]:
    """``case_id`` plus exactly the columns the suite's mappings read. The service insists that any column an
    evaluator recognises is mapped, so sending only these keeps each evaluator on the inputs chosen for it."""
    used = {v[len("{{item."):-2] for m in metrics for v in MAPPINGS[m].values()}
    return ["case_id", *sorted(used)]


def _criteria(evaluators: tuple[str, ...], checks: tuple[str, ...], judge: str) -> list[dict[str, Any]]:
    criteria: list[dict[str, Any]] = [
        {"type": "azure_ai_evaluator", "name": ev, "evaluator_name": f"builtin.{ev}",
         "initialization_parameters": {"deployment_name": judge}, "data_mapping": MAPPINGS[ev]} for ev in evaluators]
    if DECLINE_CHECK in checks:  # a plain string check, no model involved
        criteria.append({"type": "string_check", "name": DECLINE_CHECK, "input": "{{item.response}}",
                         "reference": REFUSAL_LINE, "operation": "like"})
    return criteria


def _find_or_create_eval(oc: Any, name: str, criteria: list[dict[str, Any]], fields: list[str]) -> Any:
    """One evaluation per test suite and judge, reused across runs: the portal then lists every run under it, so a
    new agent version's scores sit next to the previous ones. A change of evaluators or judge starts a new one."""
    signature = hashlib.sha1(json.dumps([criteria, fields], sort_keys=True).encode()).hexdigest()[:12]
    for ev in oc.evals.list(limit=100):
        if ev.name == name and (ev.metadata or {}).get("signature") == signature:
            return ev
    schema = {"type": "object", "properties": {k: _ANY for k in (*fields, "trial")}, "required": ["case_id"]}
    return oc.evals.create(
        name=name,
        data_source_config={"type": "custom", "item_schema": schema, "include_sample_schema": False},
        testing_criteria=criteria,
        metadata={"signature": signature, "agent": agent_name(), "suite": name},
    )


def _start_run(oc: Any, ev: Any, rows: list[dict[str, Any]], fields: list[str], version: str, repeats: int) -> Any:
    items = [{"item": {**{k: r[k] for k in fields if k in r}, "trial": str(t)}} for r in rows for t in range(1, repeats + 1)]
    return oc.evals.runs.create(
        eval_id=ev.id,
        name=f"{agent_name()} v{version} · {time.strftime('%Y-%m-%d %H:%M')}",
        metadata={"agent": agent_name(), "agent_version": version, "judgements_per_case": str(repeats)},
        data_source={"type": "jsonl", "source": {"type": "file_content", "content": items}},
    )


Trials = dict[str, dict[str, list[dict[str, Any]]]]  # case_id -> evaluator -> one entry per judgement


def _cloud_trials(oc: Any, run: Any) -> Trials:
    """Every judgement of every row of a run (the page iterator follows the pages)."""
    trials: Trials = {}
    for item in oc.evals.runs.output_items.list(run_id=run.id, eval_id=run.eval_id, limit=100):
        case_id = str((item.datasource_item or {}).get("case_id"))
        for res in item.results or []:
            d = res if isinstance(res, dict) else res.model_dump()
            reason = d.get("reason") or (d.get("properties") or {}).get("reason") or (d.get("sample") or {}).get("reason")
            passed = d.get("passed")
            result = d.get("label") or ("pass" if passed else "fail" if passed is not None else None)
            trials.setdefault(case_id, {}).setdefault(d.get("name", ""), []).append(
                {"score": d.get("score"), "result": result, "reason": reason, "threshold": d.get("threshold")})
    return trials


def _aggregate(ev: str, trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Median-of-N for an LLM judge: the median score (an observed one), pass/fail by majority, and the reason given
    with the median score. With one judgement this is just that judgement."""
    scored = [t for t in trials if isinstance(t.get("score"), (int, float))]
    if not scored:
        first = trials[0] if trials else {}
        return {f"outputs.{ev}.{ev}": None, f"outputs.{ev}.{ev}_reason": first.get("reason")}
    median = statistics.median_low(sorted(t["score"] for t in scored))
    pick = next(t for t in scored if t["score"] == median)
    passes = sum(t.get("result") == "pass" for t in scored)
    return {
        f"outputs.{ev}.{ev}": median,
        f"outputs.{ev}.{ev}_result": "pass" if passes * 2 > len(scored) else "fail",
        f"outputs.{ev}.{ev}_reason": pick.get("reason"),
        f"outputs.{ev}.{ev}_threshold": pick.get("threshold"),
        f"outputs.{ev}.{ev}_judgements": [t.get("score") for t in trials],
    }


def _scored(run: Any) -> int:
    counts = run.result_counts
    return sum(getattr(counts, k, 0) or 0 for k in ("passed", "failed", "errored")) if counts else 0


def cloud_evaluate(version: str, repeats: int) -> dict[str, Any]:
    """Run every suite as a Foundry cloud evaluation and wait for them (the judging happens service-side, which also
    retries the judge's 429s), then fold them into one results file, one row per case."""
    judge = os.environ["FOUNDRY_EVAL_MODEL_NAME"]
    with project_client() as pc, pc.get_openai_client() as oc:
        runs, total = [], 0
        for name, path, evaluators, checks in suites():
            rows = _rows(path)
            if not rows:
                continue
            fields = suite_fields((*evaluators, *checks))
            ev = _find_or_create_eval(oc, name, _criteria(evaluators, checks, judge), fields)
            runs.append(_start_run(oc, ev, rows, fields, version, repeats))
            total += len(rows) * repeats
        label = f"Foundry is judging {len(CASES)} answers, {repeats}x each (judge {judge})"
        with spinner(label) as status:
            while any(r.status not in ("completed", "failed", "canceled") for r in runs):
                time.sleep(4)
                runs = [oc.evals.runs.retrieve(run_id=r.id, eval_id=r.eval_id) for r in runs]
                status.label = f"{label} · {min(sum(map(_scored, runs)), total)}/{total} rows scored"
        for r in runs:
            if r.status != "completed":
                raise SystemExit(f"Foundry evaluation run {r.id} ended '{r.status}': {r.error}")
        per_suite = [_cloud_trials(oc, r) for r in runs]
    results = fold_rows(per_suite)
    errored = sum((getattr(r.result_counts, "errored", 0) or 0) for r in runs if r.result_counts)
    if errored:
        print(c(f"[warn] {errored} judgement(s) errored; the median is taken over the rest", "amber"))
    return {**results, "agent": agent_name(), "evaluated_at": time.strftime("%Y-%m-%d %H:%M"),
            "studio_url": runs[0].report_url, "suite_urls": {r.name: r.report_url for r in runs},
            "judge": judge, "judgements_per_case": repeats, "agent_version": version}


def fold_rows(per_suite: list[Trials]) -> dict[str, Any]:
    """One row per case with every suite's aggregated outputs, inputs taken from the dataset."""
    inputs = {r["case_id"]: r for path in (DATASET, DATASET_SCOPE) for r in _rows(path)}
    rows = []
    for case in CASES:
        src = inputs.get(case.case_id, {})
        row: dict[str, Any] = {"inputs.case_id": case.case_id, "inputs.query": case.query, "inputs.response": src.get("response")}
        for suite in per_suite:
            for ev, trials in suite.get(case.case_id, {}).items():
                row.update(_aggregate(ev, trials))
        rows.append(row)
    return {"rows": rows, "metrics": metrics_from(rows)}


def metrics_from(rows: list[dict[str, Any]]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for ev in ALL_METRICS:
        scored = [r for r in rows if isinstance(r.get(f"outputs.{ev}.{ev}"), (int, float))]
        if scored:
            metrics[f"{ev}.{ev}"] = round(sum(r[f"outputs.{ev}.{ev}"] for r in scored) / len(scored), 3)
            metrics[f"{ev}.binary_aggregate"] = round(sum(r.get(f"outputs.{ev}.{ev}_result") == "pass" for r in scored) / len(scored), 2)
    return metrics


# --------------------------------------------------------------------------- local evaluation (azure-ai-evaluation)

def foundry_resource_url(project_endpoint: str) -> str:
    return re.sub(r"/api/projects/.*$", "", project_endpoint.rstrip("/"))


SDK_LOG = EVAL_DIR / "evaluate.log"
SDK_LOGGERS = ("azure.ai.evaluation", "promptflow", "run")  # "run": the SDK's batch submitter logs aggregation notes
# The SDK's batch-engine loggers print per-line progress to stdout at INFO; they read this when first imported.
os.environ.setdefault("PF_LOGGING_LEVEL", "WARNING")


@contextlib.contextmanager
def quiet_sdk(label: str) -> Iterator[None]:
    """Keep the evaluation SDK's console chatter off the screen: its run summaries and its retry warnings (the
    judge deployment answers 429 under load and the SDK retries by itself, printing a traceback each time) go to
    eval/evaluate.log, and the terminal shows a spinner instead. Real failures still raise."""
    EVAL_DIR.mkdir(exist_ok=True)
    real_stdout = sys.stdout
    handler = logging.FileHandler(SDK_LOG, mode="a", encoding="utf-8")
    names = {n for n in logging.Logger.manager.loggerDict if n.startswith(SDK_LOGGERS)} | set(SDK_LOGGERS)
    saved = [(lg, lg.handlers[:], lg.propagate) for lg in map(logging.getLogger, sorted(names))]
    for lg, _, _ in saved:
        lg.handlers, lg.propagate = [handler], False
    try:
        with SDK_LOG.open("a", encoding="utf-8") as fh, contextlib.redirect_stdout(fh), spinner(label, stream=real_stdout):
            yield
    finally:
        for lg, handlers, propagate in saved:
            lg.handlers, lg.propagate = handlers, propagate
        handler.close()


class DeclinedCheck:
    """Code-based evaluator for --local: 1 when the answer is the mandated refusal, else 0."""

    def __call__(self, *, response: str) -> dict[str, Any]:  # evaluate() maps inputs by this signature
        ok = declined(response)
        return {DECLINE_CHECK: 1.0 if ok else 0.0, f"{DECLINE_CHECK}_result": "pass" if ok else "fail"}


def _local_trials(result: dict[str, Any], metrics: list[str]) -> Trials:
    trials: Trials = {}
    for r in result["rows"]:
        for m in metrics:
            if f"outputs.{m}.{m}" in r or f"outputs.{m}.{m}_reason" in r:
                trials.setdefault(str(r.get("inputs.case_id")), {}).setdefault(m, []).append(
                    {"score": r.get(f"outputs.{m}.{m}"), "result": r.get(f"outputs.{m}.{m}_result"),
                     "reason": r.get(f"outputs.{m}.{m}_reason"), "threshold": r.get(f"outputs.{m}.{m}_threshold")})
    return trials


def local_evaluate(upload: bool, repeats: int, version: str) -> dict[str, Any]:
    from azure.ai.evaluation import (
        GroundednessEvaluator,
        IntentResolutionEvaluator,
        RelevanceEvaluator,
        TaskAdherenceEvaluator,
        ToolCallAccuracyEvaluator,
        evaluate,
    )
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential(process_timeout=60)
    judge = os.environ["FOUNDRY_EVAL_MODEL_NAME"]
    model_config = {"azure_endpoint": foundry_resource_url(os.environ["FOUNDRY_PROJECT_ENDPOINT"]),
                    "azure_deployment": judge, "api_version": JUDGE_API_VERSION}
    reasoning = judge.lower().startswith(("gpt-5", "o1", "o3", "o4"))
    kwargs = {"model_config": model_config, "credential": credential, "is_reasoning_model": reasoning}
    classes = {"groundedness": GroundednessEvaluator, "relevance": RelevanceEvaluator, "task_adherence": TaskAdherenceEvaluator,
               "intent_resolution": IntentResolutionEvaluator, TOOL_EVALUATOR: ToolCallAccuracyEvaluator}
    project = os.environ["FOUNDRY_PROJECT_ENDPOINT"] if upload else None
    SDK_LOG.unlink(missing_ok=True)

    def mapping(ev: str) -> dict[str, str]:
        return {k: v.replace("{{item.", "${data.").replace("}}", "}") for k, v in MAPPINGS[ev].items()}

    per_suite, urls = [], {}
    for name, path, evaluators, checks in suites():
        rows = _rows(path)
        if not rows:
            continue
        repeated = EVAL_DIR / f"{path.stem}.x{repeats}.jsonl"  # each row once per judgement
        _write_jsonl(repeated, [{**r, "trial": t} for r in rows for t in range(1, repeats + 1)])
        scorers: dict[str, Any] = {ev: classes[ev](**kwargs) for ev in evaluators}
        scorers.update({chk: DeclinedCheck() for chk in checks})
        try:
            with quiet_sdk(f"Judging {name}, {repeats}x each: {', '.join(scorers)}"):
                result = evaluate(data=str(repeated), evaluation_name=name, evaluators=scorers,
                                  evaluator_config={m: {"column_mapping": mapping(m)} for m in scorers},
                                  azure_ai_project=project, tags={"demo": "04-trace-and-evaluate", "agent": agent_name()})
        finally:
            repeated.unlink(missing_ok=True)
        per_suite.append(_local_trials(result, list(scorers)))
        urls[name] = result.get("studio_url")
    print(f"Evaluation SDK log (run summaries, retries): {SDK_LOG.relative_to(HERE)}")
    return {**fold_rows(per_suite), "agent": agent_name(), "studio_url": next(iter(urls.values()), None), "suite_urls": urls,
            "judge": judge, "judgements_per_case": repeats, "agent_version": version}


# --------------------------------------------------------------------------- mock evaluation

def _mock_score(case_id: str, evaluator: str, low: int, high: int) -> int:
    digest = hashlib.sha1(f"{case_id}:{evaluator}".encode()).hexdigest()
    return low + int(digest[:8], 16) % (high - low + 1)


def snapshot_path() -> Path:
    """fallback/results-live.json for the production run, fallback/<folder>-results.json for another --out folder."""
    return FALLBACK_DIR / ("results-live.json" if EVAL_DIR == HERE / "eval" else f"{EVAL_DIR.name}-results.json")


def write_snapshot(results: dict[str, Any]) -> Path:
    """A copy of a live run for the offline fallback, without the portal links (they carry the subscription)."""
    public = {k: v for k, v in results.items() if k not in ("studio_url", "suite_urls")}
    path = snapshot_path()
    path.write_text(json.dumps(public, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    return path


def mock_evaluate() -> dict[str, Any]:
    """Replay the last live snapshot when there is one; otherwise deterministic, plausible scores per suite with the
    same row/metric shape evaluate() produces."""
    snapshot = snapshot_path()
    if snapshot.exists():
        replay = json.loads(snapshot.read_text(encoding="utf-8"))
        print(f"[MOCK] replaying the live evaluation of {replay.get('evaluated_at', '?')} from {snapshot.relative_to(HERE)}")
        return {**replay, "mock": True}
    reasons = {
        "groundedness": "Claims are supported by the retrieved documents and tool output.",
        "relevance": "The response addresses the question directly with specific, on-topic detail.",
        "intent_resolution": "The user's intent was correctly identified and fully resolved.",
        "task_adherence": "The response follows the instructions: grounded, cited sources, NZ English.",
        TOOL_EVALUATOR: "The tool calls match the task and use correct parameters.",
    }
    per_suite: list[Trials] = []
    for _, path, evaluators, checks in suites():
        suite: Trials = {}
        for r in _rows(path):
            out = suite.setdefault(r["case_id"], {})
            for ev in evaluators:
                score, threshold = (1, 1) if ev == "task_adherence" else (_mock_score(r["case_id"], ev, 4, 5), 3)
                out[ev] = [_trial(score, threshold, reasons[ev])]
            for chk in checks:
                out[chk] = [_trial(1 if declined(r["response"]) else 0, 1, "Gives the mandated refusal.")]
        per_suite.append(suite)
    return {**fold_rows(per_suite), "studio_url": None, "mock": True}


def _trial(score: int, threshold: int, reason: str) -> dict[str, Any]:
    return {"score": float(score), "result": "pass" if score >= threshold else "fail", "reason": reason, "threshold": threshold}


# --------------------------------------------------------------------------- reporting

def _scale(scores: list[float]) -> float:
    return 1.0 if max(scores) <= 1.0 else 5.0  # task adherence and the decline check are pass/fail (0/1), the rest 1-5


def summarise(results: dict[str, Any]) -> str:
    """Pass rate and mean per evaluator, then every row that fell short of the maximum, with the judge's reason."""
    rows = results["rows"]
    lines = [f"{'evaluator':20s} {'rows':>4s} {'mean':>6s} {'pass':>6s} {'min':>4s}  {'mean / scale':16s}", "-" * 64]
    maxima: dict[str, float] = {}
    for ev in ALL_METRICS:
        col = f"outputs.{ev}.{ev}"
        scores = [float(r[col]) for r in rows if isinstance(r.get(col), (int, float))]
        if not scores:
            continue
        passed = sum(1 for r in rows if r.get(f"{col}_result") == "pass")
        mean = sum(scores) / len(scores)
        maxima[ev] = scale = _scale(scores)
        lines.append(f"{ev:20s} {len(scores):4d} {mean:6.2f} {passed/len(scores):6.0%} {min(scores):4.0f}  {bar(mean, scale, 14)} /{scale:.0f}")

    short = [(r, ev) for r in rows for ev, top in maxima.items()
             if isinstance(r.get(f"outputs.{ev}.{ev}"), (int, float)) and r[f"outputs.{ev}.{ev}"] < top]
    lines.append("")
    if not short:
        lines.append(f"Every case scored the maximum on every evaluator ({len(rows)} cases, "
                     f"{sum(1 for r in rows if r.get(f'outputs.{DECLINE_CHECK}.{DECLINE_CHECK}') is not None)} out of scope and declined).")
    else:
        lines.append(f"Below the maximum ({len(short)}):")
        for r, ev in short:
            reason = re.sub(r"\s+", " ", str(r.get(f"outputs.{ev}.{ev}_reason") or "")).strip()
            lines.append(f"  {r.get('inputs.case_id', '?'):28s} {ev}={r[f'outputs.{ev}.{ev}']:g}  {reason[:150]}")
    if results.get("judge"):
        n = results.get("judgements_per_case", 1)
        how = f", median of {n} judgements per case" if n > 1 else ""
        lines += ["", f"Judge: {results['judge']}{how} · agent version {results.get('agent_version', '?')}"]
    if results.get("studio_url"):
        lines.append(f"Foundry evaluation: {results['studio_url']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-agent", action="store_true", help="re-record eval/responses.jsonl from the live agent (mock: from the canned transcript)")
    parser.add_argument("--local", action="store_true", help="score in-process with azure-ai-evaluation instead of a Foundry cloud evaluation")
    parser.add_argument("--no-upload", action="store_true", help="with --local: do not upload the run to the Foundry project")
    parser.add_argument("--judgements", type=int, default=3, help="LLM judgements per case; the median counts (default 3)")
    parser.add_argument("--agent", help="agent to run and evaluate (default FOUNDRY_AGENT_NAME), e.g. hbl-site-ops-advisor-candidate")
    parser.add_argument("--out", type=Path, help="folder for this run's responses, datasets and results (default eval/)")
    parser.add_argument("--snapshot", action="store_true", help="also keep a copy in fallback/ for DEMO_MODE=mock to replay")
    args = parser.parse_args()
    load_env()
    if args.agent:
        os.environ["FOUNDRY_AGENT_NAME"] = args.agent
    if args.out:
        use_dir(args.out)
    mock = is_mock()

    if args.run_agent:
        record_responses(run_agent() if not mock else {c.case_id: mock_response(c) for c in CASES})
    elif not RESPONSES.exists():
        if not mock:
            raise SystemExit(f"{RESPONSES} missing: run with --run-agent, or DEMO_MODE=mock to record mock responses.")
        record_responses({c.case_id: mock_response(c) for c in CASES})

    responses = load_responses()
    sizes = build_dataset(responses)
    print(f"Dataset: {len(CASES)} cases ({sizes[DATASET]} in scope, {sizes[DATASET_SCOPE]} out of scope, "
          f"{sizes[DATASET_TOOLS]} with expected tool calls) -> {EVAL_DIR.relative_to(HERE)}/dataset*.jsonl")

    if mock:
        print("[MOCK] nothing is sent to Azure")
        results = mock_evaluate()
        out_dir = FALLBACK_DIR
    elif args.local:
        results = local_evaluate(upload=not args.no_upload, repeats=args.judgements, version=agent_version(responses))
        out_dir = EVAL_DIR
    else:
        results = cloud_evaluate(agent_version(responses), repeats=args.judgements)
        out_dir = EVAL_DIR

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    report = summarise(results)
    (out_dir / "summary.txt").write_text(report + "\n", encoding="utf-8", newline="\n")
    shown = "\n".join(c(l, "amber", "bold") if l.startswith(("Below the maximum", "evaluator")) else
                      c(l, "green", "bold") if l.startswith("Every case scored") else l for l in report.splitlines())
    print(f"\n{shown}\n\nWrote {out_dir.relative_to(HERE)}/results.json and summary.txt")
    if args.snapshot and not mock:
        print(f"Snapshot for the offline fallback: {write_snapshot(results).relative_to(HERE)}")


if __name__ == "__main__":
    main()
