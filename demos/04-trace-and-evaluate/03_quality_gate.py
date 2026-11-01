"""CI-style quality gate over an evaluation results file.

Exit code 0 when every rule passes, 1 otherwise. The release bar (defaults):
  * groundedness: mean >= 4.5 and every case >= 4
  * relevance, intent resolution, tool-call accuracy: every case >= 4
  * task adherence: every case passes
  * out of scope: every out-of-scope case declines
A rule whose evaluator has no rows in the file is skipped. Mirrors the step in
``.github/workflows/agent-eval.yml.example``.

Usage: python 03_quality_gate.py [eval/results.json] [--min-groundedness 4.5] [--min-score 4]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_RESULTS = Path(__file__).resolve().parent / "eval" / "results.json"

try:  # colour on a terminal, plain in CI; the gate must never depend on the shared helper being present
    import _shared  # noqa: F401
    from ui import c
except Exception:  # noqa: BLE001
    def c(text, *_styles):  # type: ignore[misc]
        return str(text)


def verdict(status: str, text: str) -> str:
    """``[PASS] ...`` green, ``[FAIL] ...`` red, ``[info]`` dim; the plain text is unchanged."""
    return c(text, "green" if status == "PASS" else "red" if status == "FAIL" else "grey", "bold")


def scores(rows: list[dict[str, Any]], evaluator: str) -> list[tuple[str, float]]:
    col = f"outputs.{evaluator}.{evaluator}"
    return [(r.get("inputs.case_id", f"row {i}"), float(r[col])) for i, r in enumerate(rows) if isinstance(r.get(col), (int, float))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", nargs="?", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--min-groundedness", type=float, default=4.5, help="minimum mean groundedness (1-5)")
    parser.add_argument("--min-score", type=float, default=4.0, help="minimum on every case for the 1-5 evaluators")
    args = parser.parse_args()

    if not args.results.exists():
        print(f"GATE ERROR: {args.results} not found (run 02_evaluate.py first)")
        return 2
    results = json.loads(args.results.read_text(encoding="utf-8"))
    rows = results.get("rows", [])
    agent = f"{results.get('agent', 'agent')} v{results.get('agent_version', '?')}"
    print(c(f"Quality gate: {agent}, judged by {results.get('judge', '?')}", "grey"))
    failures: list[str] = []

    def rule(name: str, ok: bool, text: str, offenders: list[str]) -> None:
        status = "PASS" if ok else "FAIL"
        detail = f"  -> {', '.join(offenders)}" if offenders else ""
        print(verdict(status, f"[{status}] {name:19s} {text}{detail}"))
        if not ok:
            failures.append(name)

    g = scores(rows, "groundedness")
    if g:
        mean, low = sum(s for _, s in g) / len(g), [f"{cid}={s:g}" for cid, s in g if s < args.min_score]
        rule("groundedness", mean >= args.min_groundedness and not low,
             f"mean {mean:.2f} (min {args.min_groundedness:g}), lowest {min(s for _, s in g):g} (min {args.min_score:g}), {len(g)} cases", low)
    for ev in ("relevance", "intent_resolution", "tool_call_accuracy"):
        vals = scores(rows, ev)
        if vals:
            low = [f"{cid}={s:g}" for cid, s in vals if s < args.min_score]
            rule(ev, not low, f"lowest {min(s for _, s in vals):g} (min {args.min_score:g}), {len(vals)} cases", low)
    ta = scores(rows, "task_adherence")
    if ta:
        failed = [cid for cid, s in ta if s < 1]
        rule("task_adherence", not failed, f"{len(ta) - len(failed)}/{len(ta)} cases follow the agent's instructions", failed)
    dc = scores(rows, "declined")
    if dc:
        answered = [cid for cid, s in dc if s < 1]
        rule("out_of_scope", not answered, f"{len(dc) - len(answered)}/{len(dc)} out-of-scope cases declined",
             [f"{cid} answered" for cid in answered])
        for r in rows:  # show what it said instead of declining: that is the regression a reviewer needs to see
            if r.get("inputs.case_id") in answered and r.get("inputs.response"):
                said = " ".join(str(r["inputs.response"]).split())
                print(c(f"       {r.get('inputs.query', '')}", "grey"))
                print(c(f"       agent: {said[:150]}{'...' if len(said) > 150 else ''}", "amber"))

    if results.get("mock"):
        print(verdict("info", "[info] results were produced in DEMO_MODE=mock"))
    if failures:
        print("\n" + c(f"QUALITY GATE FAILED: {', '.join(failures)}. Do not promote {agent}.", "red", "bold"))
        return 1
    print("\n" + c(f"QUALITY GATE PASSED: {agent} can be promoted.", "green", "bold"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
