"""Canned Site Operations Advisor transcript for ``DEMO_MODE=mock``.

Every number in the answers is computed from the synthetic data through the real Site API tools, so the mock matches
what the live agent would see. Only the prose is pre-written. Used by ``03_chat.py`` (mock mode), ``fallback/transcript.md``
and module 4's recorded responses.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import _shared  # noqa: F401
from foundry_util import SearchRecord, ToolCallRecord, TurnResult
from site_tools import call_tool

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "00-shared" / "data" / "knowledge"

T_HVAC = "HVAC fault response SOP"
T_LIFT = "Lift incident and entrapment procedure"
T_FIRE = "Fire system inspection schedule"
T_SLA = "Work order priorities and SLAs"
T_CONTRACTOR = "Contractor safety and site access"
T_ENERGY = "Energy and sustainability targets"
T_PLATFORM = "Site operations platform: reference architecture overview"
T_TENANT = "Tenant communications and the scope of operations guidance"

MONTH = "2026-11"
WEEK = ("2026-11-09", "2026-11-15")
CAVEAT = "Course guidance, not legal or engineering advice: check the current building code and the real procedure before acting."


def _call(name: str, **arguments) -> ToolCallRecord:
    return ToolCallRecord(name=name, arguments=arguments, output=call_tool(name, arguments), call_id=f"mock_{name}_{len(arguments)}")


def knowledge_text(title: str) -> str:
    """Full text of the knowledge document with this H1 title (what a mock search returns)."""
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if text.startswith(f"# {title}"):
            return text
    return ""


def mock_search(question: str, titles: list[str]) -> list[SearchRecord]:
    """One AI Search call returning the cited documents, shaped like a live ``azure_ai_search_call_output``."""
    if not titles:
        return []
    call_id = f"mock_search_{hashlib.sha1(question.encode()).hexdigest()[:8]}"
    return [SearchRecord(call_id, question, [{"title": t, "content": knowledge_text(t), "score": None} for t in titles])]


def _turn(question: str, answer: str, calls: list[ToolCallRecord], citations: list[str], tokens: tuple[int, int]) -> TurnResult:
    searches = mock_search(question, citations)
    return TurnResult(
        question=question,
        answer=answer.strip(),
        tool_calls=calls,
        citations=citations,
        searches=searches,
        steps=[("function", c.call_id) for c in calls] + [("search", s.call_id) for s in searches],
        response_ids=[f"resp_mock_{hashlib.sha1(question.encode()).hexdigest()[:12]}"],
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        latency_s=round(1.8 + 0.9 * len(calls), 2),
    )


def _args(call: ToolCallRecord) -> str:
    return ", ".join(str(v) for v in call.arguments.values())


def sop_turn(question: str = "What is the SOP when a chiller trips twice in a day?") -> TurnResult:
    answer = f"""
Lock the chiller out after the second trip of the day and do not attempt a third reset; the mechanical contractor attends within 2 hours.

- One trip may be reset once from the BMS after the cause has been checked; the second trip in the same day is the lockout trigger.
- Raise the work order to P1 when the site is a medical centre or an office tower in business hours, otherwise keep it at P2.
- Notify the site manager in both cases and record the lockout in the work order.
- If the work order is still open after 48 hours it is escalated to the regional facilities manager the same day with a written recovery plan from the contractor.
{CAVEAT}

Sources: {T_HVAC}
"""
    return _turn(question, answer, [], [T_HVAC], (2190, 210))


def inspection_turn(question: str = "Is Site HBL-AKL-017 due a fire-system inspection this month?", site_id: str = "HBL-AKL-017") -> TurnResult:
    call = _call("get_inspection_schedule", scope=site_id, system="fire", month=MONTH)
    r = call.output
    due = [d for d in r["due"]]
    name = due[0]["site_name"] if due else site_id
    if due:
        d = due[0]
        headline = (f"Yes. {site_id} ({name}) has its fire annual certificate inspection due on {d['next_due']}, and the certificate "
                    f"is {d['certificate_status']}, so the inspector should be booked now.")
        bullets = [
            f"The annual certificate inspection falls inside {MONTH}; the last one was completed on {d['last_completed']}.",
            f"An expiring certificate means it falls due within 30 days: book the approved inspector at least 2 weeks ahead so the inspection happens before the due date.",
            f"The site has {r['needs_attention']['overdue']} overdue inspections, so no escalation applies yet; the inspector firm on the schedule is {d['inspector_firm']}.",
        ]
        if r["monthly_tests_due"]:
            bullets.append(f"Separately, the routine monthly fire test is due on {r['monthly_tests_due'][0]['next_due']} and is carried out by the site's fire contractor.")
    else:
        headline = f"No. {site_id} has no fire certificate inspection due in {MONTH}."
        bullets = [f"Overdue inspections at the site: {r['needs_attention']['overdue']}."]
    answer = headline + "\n\n" + "\n".join(f"- {b}" for b in bullets) + f"\n{CAVEAT}\n\nSources: {T_FIRE}; get_inspection_schedule({_args(call)})"
    return _turn(question, answer, [call], [T_FIRE], (2860, 240))


def hvac48_turn(question: str = "Which sites have HVAC faults open more than 48 hours and are due a fire-system inspection this month?") -> TurnResult:
    wo_call = _call("get_open_work_orders", region="ALL", system="hvac", open_longer_than_hours=48)
    insp_call = _call("get_inspection_schedule", scope="ALL", system="fire", month=MONTH)
    wos = wo_call.output["work_orders"]
    due_by_site: dict[str, dict] = {}
    for d in insp_call.output["due"]:
        due_by_site.setdefault(d["site_id"], d)
    both = [w for w in wos if w["site_id"] in due_by_site]
    only = [w for w in wos if w["site_id"] not in due_by_site]
    p1 = [w for w in wos if w["priority"] == "P1"]
    lines = [
        f"- {w['site_id']} ({w['site_name']}): {w['summary'].split(': ', 1)[1]} open {w['age_hours']:.0f} hours, {w['priority']}"
        f"{' and past its SLA' if w['sla_breached'] else ''}; fire certificate due {due_by_site[w['site_id']]['next_due']}."
        for w in both
    ]
    answer = f"""
{len(both)} of the {len(wos)} sites with an HVAC work order open longer than 48 hours also have a fire certificate inspection due in November 2026: {', '.join(w['site_id'] for w in both)}.

{chr(10).join(lines)}
- The other {len(only)} sites with HVAC work open over 48 hours ({', '.join(w['site_id'] for w in only)}) have no fire certificate due this month{'; ' + p1[0]['site_id'] + ' holds the only P1' if p1 else ''}.
- Every HVAC work order open over 48 hours is escalated to the regional facilities manager the same day, with a written recovery plan from the contractor.
- Do not carry out the fire inspection on a floor with an active HVAC fault until the fault owner has confirmed the floor is safe to work on.
{CAVEAT}

Sources: {T_SLA}; {T_HVAC}; {T_FIRE}; get_open_work_orders({_args(wo_call)}); get_inspection_schedule({_args(insp_call)})
"""
    return _turn(question, answer, [wo_call, insp_call], [T_SLA, T_HVAC, T_FIRE], (5120, 390))


def lifts_turn(question: str = "Summarise lift incidents at the Wellington sites in the last 7 days.") -> TurnResult:
    call = _call("get_incidents", region="WLG", system="lift", days=7)
    r = call.output
    sites = r["by_site"]
    entrap = [i for i in r["incidents"] if i["detail"].startswith("entrapment")]
    site_lines = "\n".join(
        f"- {s['site_id']} ({s['site_name']}): {s['count']} incident{'s' if s['count'] != 1 else ''} ({', '.join(t.replace('_', ' ') for t in s['types'])})."
        for s in sites
    )
    answer = f"""
{r['count']} lift incidents were recorded at {len(sites)} Wellington sites between {r['window']['from']} and {r['window']['to']}, including {r['needs_attention']['entrapments']} entrapment{'s' if r['needs_attention']['entrapments'] != 1 else ''}{' at ' + entrap[0]['site_id'] + ' on ' + entrap[0]['ts'][:10] if entrap else ''}.

{site_lines}
- An entrapment is a P1 incident: the lift contractor attends within 30 minutes, staff never attempt a release themselves, and it is reported to the Vertical Transport Safety Register within 24 hours.
- Three door faults on the same lift within a week trigger a contractor inspection of the door operator, so the door faults should be checked against that rule.
{CAVEAT}

Sources: {T_LIFT}; get_incidents({_args(call)})
"""
    return _turn(question, answer, [call], [T_LIFT], (3310, 300))


def summary_turn(question: str = "Give me a summary of HBL-SYD-008 and anything that needs attention.", site_id: str = "HBL-SYD-008") -> TurnResult:
    call = _call("get_site_summary", site_id=site_id)
    s = call.output
    na = s["needs_attention"]
    site = s["site"]
    open_wos = s["open_work_orders"]
    wo_lines = "\n".join(
        f"- Open {w['priority']} work order {w['wo_id']}: {w['summary'].split(': ', 1)[1]}, open {w['age_hours']:.0f} hours against a {w['sla_hours']}-hour SLA{' (breached)' if w['sla_breached'] else ''}; contractor {w['contractor']}."
        for w in open_wos
    )
    fire = s["inspections"]["fire_annual_certificate"]
    answer = f"""
{site_id} ({site['site_name']}) is a {site['floors']}-floor {site['building_type'].replace('_', ' ')} in {site['city']} with {na['open_p1_work_orders']} open P1 work order{'s' if na['open_p1_work_orders'] != 1 else ''}, {na['sla_breached_work_orders']} SLA breach{'es' if na['sla_breached_work_orders'] != 1 else ''} and {na['hvac_faults_open_over_48h']} HVAC fault open over 48 hours.

{wo_lines}
- The chiller tripped twice on 2026-11-13; under the SOP that is a lockout: no third reset, mechanical contractor within 2 hours, P1 at an office tower in business hours.
- The fire annual certificate is due {fire['next_due']} and is {fire['certificate_status']}: book the inspector at least 2 weeks ahead.
- Energy over the last 7 days was {s['energy_last_7_days']['kwh']:,} kWh, {s['energy_last_7_days']['vs_baseline_pct']:+.1f} % against baseline, with {s['energy_last_7_days']['anomaly_days']} anomaly days.
{CAVEAT}

Sources: {T_HVAC}; {T_SLA}; get_site_summary({_args(call)})
"""
    return _turn(question, answer, [call], [T_HVAC, T_SLA], (3980, 330))


def refusal_turn(question: str = "Can we evict a tenant for late rent?") -> TurnResult:
    answer = """
I don't have that information: tenant evictions are outside our site operations guidance and telemetry.
I can summarise a site or region from telemetry, or explain our operations guidance.
Sources: none
"""
    return _turn(question, answer, [], [], (1740, 60))


DEMO_TURNS = {
    "sop": sop_turn,
    "inspection": inspection_turn,
    "hvac48": hvac48_turn,
    "lifts": lifts_turn,
    "refusal": refusal_turn,
}


def mock_answer(question: str) -> TurnResult:
    """Pick the canned turn that best matches a question (keyword routing)."""
    q = question.lower()
    site = next((w.strip("?.,'s()").upper() for w in question.split() if w.upper().startswith("HBL-")), None)
    if any(k in q for k in ("evict", "rent", "lease", "tenant dispute")):
        return refusal_turn(question)
    if "48" in q and ("hvac" in q or "fault" in q):
        return hvac48_turn(question)
    if "lift" in q and ("incident" in q or "wellington" in q or "wlg" in q):
        return lifts_turn(question)
    if site and ("inspection" in q or "due" in q):
        return inspection_turn(question, site[:11])
    if site:
        return summary_turn(question, site[:11])
    if "chiller" in q or "sop" in q or "procedure" in q:
        return sop_turn(question)
    return refusal_turn(question)


def demo_transcript() -> list[TurnResult]:
    """The five demo questions in order."""
    return [fn() for fn in DEMO_TURNS.values()]
