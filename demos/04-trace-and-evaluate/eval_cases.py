"""Twelve Site Operations Advisor test cases and their mock (recorded) responses.

Each case has: ``case_id``, ``query``, ``ground_truth`` (what a correct answer must say), ``context`` (the knowledge
documents a grounded answer should rest on), for the tool cases the ``expected_tool_calls``, and for the out-of-scope
case ``declines=True``: the right answer there is a clean refusal, so it is scored on its own. ``mock_response()``
produces a realistic agent answer whose figures come from the Site API tools, used to seed ``eval/responses.jsonl`` so
the evaluation can be rehearsed without the live agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import _shared  # noqa: F401
from foundry_util import TurnResult
from mock_transcript import (
    T_CONTRACTOR, T_ENERGY, T_FIRE, T_HVAC, T_LIFT, T_PLATFORM, T_SLA, CAVEAT,
    hvac48_turn, inspection_turn, lifts_turn, mock_search, refusal_turn, sop_turn, summary_turn,
)
from site_tools import TOOL_SCHEMAS

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "00-shared" / "data" / "knowledge"
MONTH = "2026-11"

# Shape expected by azure-ai-evaluation's agent evaluators (tool_definitions column).
TOOL_DEFINITIONS: list[dict[str, Any]] = [{"type": "function", **schema} for schema in TOOL_SCHEMAS]


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    query: str
    ground_truth: str
    context_docs: tuple[str, ...]
    expected_tool_calls: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    declines: bool = False  # out of scope by design: a correct answer declines instead of resolving the request

    @property
    def context(self) -> str:
        return "\n\n---\n\n".join((KNOWLEDGE_DIR / doc).read_text(encoding="utf-8") for doc in self.context_docs)


def _tc(call_id: str, name: str, **arguments: Any) -> dict[str, Any]:
    return {"type": "tool_call", "tool_call_id": call_id, "name": name, "arguments": arguments}


CASES: list[EvalCase] = [
    EvalCase(
        "C01-chiller-trip-sop",
        "What is the SOP when a chiller trips twice in a day?",
        "Lock the chiller out after the second trip in a day and do not attempt a third reset; call the mechanical contractor to "
        "attend within 2 hours; P1 if the site is a medical centre or an office tower in business hours, otherwise P2; notify the "
        "site manager and record the lockout; cites the HVAC fault response SOP.",
        ("hvac-fault-response-sop.md",),
    ),
    EvalCase(
        "C02-fire-inspection-akl-017",
        "Is Site HBL-AKL-017 due a fire-system inspection this month?",
        "Uses get_inspection_schedule for HBL-AKL-017, system fire, month 2026-11 and answers yes: the fire annual certificate "
        "inspection is due on 2026-11-24 and the certificate is expiring, so the approved inspector should be booked at least "
        "2 weeks ahead; mentions no overdue inspections at the site.",
        ("fire-system-inspection-schedule.md",),
        (_tc("call_c02_1", "get_inspection_schedule", scope="HBL-AKL-017", system="fire", month=MONTH),),
    ),
    EvalCase(
        "C03-hvac-48h-and-fire-due",
        "Which sites have HVAC faults open more than 48 hours and are due a fire-system inspection this month?",
        "Calls get_open_work_orders(ALL, hvac, 48) and get_inspection_schedule(ALL, fire, 2026-11); reports that six sites have HVAC "
        "work open over 48 hours (HBL-AKL-017, HBL-AKL-033, HBL-WLG-011, HBL-SYD-008 which is the only P1, HBL-SYD-021, HBL-MEL-006) "
        "and that three of them also have a fire certificate due in November: HBL-AKL-017 (24 Nov), HBL-WLG-011 (28 Nov) and "
        "HBL-SYD-008 (30 Nov); states the 48-hour escalation to the regional facilities manager with a contractor recovery plan, and "
        "that no fire inspection is carried out on a floor with an active HVAC fault until the fault owner signs it off.",
        ("work-order-priorities-and-sla.md", "hvac-fault-response-sop.md", "fire-system-inspection-schedule.md"),
        (
            _tc("call_c03_1", "get_open_work_orders", region="ALL", system="hvac", open_longer_than_hours=48),
            _tc("call_c03_2", "get_inspection_schedule", scope="ALL", system="fire", month=MONTH),
        ),
    ),
    EvalCase(
        "C04-wlg-lift-incidents-7d",
        "Summarise lift incidents at the Wellington sites in the last 7 days.",
        "Calls get_incidents(WLG, lift, 7) and reports 5 lift incidents at 3 sites between 2026-11-09 and 2026-11-15, including 1 "
        "entrapment at HBL-WLG-004 on 2026-11-12; per site: HBL-WLG-004 2 (door fault, entrapment), HBL-WLG-009 2 (levelling fault, "
        "out of service), HBL-WLG-018 1 (door fault); states that an entrapment is P1, the contractor attends within 30 minutes, staff "
        "never release a trapped person, and it is reported to the Vertical Transport Safety Register within 24 hours.",
        ("lift-incident-and-entrapment-procedure.md",),
        (_tc("call_c04_1", "get_incidents", region="WLG", system="lift", days=7),),
    ),
    EvalCase(
        "C05-eviction-refusal",
        "Can we evict a tenant for late rent?",
        "Declines in the mandated three lines: evictions are outside the site operations guidance and telemetry; offers to "
        "summarise a site or region or explain the operations guidance; gives no legal view, timeframe or outside source, and ends "
        "with Sources: none.",
        ("tenant-communications-and-scope.md",),
        declines=True,
    ),
    EvalCase(
        "C06-entrapment-procedure",
        "What do we do when someone is trapped in a lift?",
        "An entrapment is a P1 incident: establish voice contact through the car intercom within 2 minutes and keep it; the lift "
        "contractor attends within 30 minutes; call emergency services if anyone is unwell or distressed or the contractor cannot "
        "meet 30 minutes; staff never attempt a release; report to the Vertical Transport Safety Register within 24 hours and send a "
        "tenant notice the same day.",
        ("lift-incident-and-entrapment-procedure.md",),
    ),
    EvalCase(
        "C07-site-summary-syd-008",
        "Give me a summary of HBL-SYD-008 and anything that needs attention.",
        "Uses get_site_summary for HBL-SYD-008 (Homebush Tower) and reports the open P1 chiller work order open about 58 hours and "
        "past its 4-hour SLA, the chiller's two trips on 2026-11-13 and the SOP lockout response (no third reset, contractor within "
        "2 hours), the fire certificate due 2026-11-30 and expiring, and the energy position against baseline.",
        ("hvac-fault-response-sop.md", "work-order-priorities-and-sla.md"),
        (_tc("call_c07_1", "get_site_summary", site_id="HBL-SYD-008"),),
    ),
    EvalCase(
        "C08-sla-hours",
        "What are the work order priorities and their SLA hours?",
        "P1 within 4 hours, P2 within 24 hours, P3 within 72 hours, measured from opening to cleared or made safe; a breach is "
        "recorded against the contractor at the monthly review; any HVAC work order open longer than 48 hours is reviewed by the "
        "regional facilities manager regardless of SLA.",
        ("work-order-priorities-and-sla.md",),
    ),
    EvalCase(
        "C09-after-hours-contractor",
        "Can a contractor work on site after hours without a permit?",
        "No: contractor access outside 07:00 to 18:00 needs an approved after-hours permit and a named Harbourline site contact "
        "reachable by phone for the whole visit; access without a permit is logged as a warning and reviewed by the site manager "
        "the next working day.",
        ("contractor-safety-and-access.md",),
    ),
    EvalCase(
        "C10-platform-data-source",
        "Where does the Site Operations Advisor get its telemetry from?",
        "From the Site APIs exposed as four tools (get_site_summary, get_open_work_orders, get_incidents, get_inspection_schedule), "
        "which sit on the lakehouse and real-time store fed by ingestion and stream processing from BMS, lift, fire, access and "
        "meter telemetry; the tools are published through the AI gateway; rules come from the knowledge index.",
        ("site-operations-platform-overview.md",),
    ),
    EvalCase(
        "C11-false-alarm-reduction",
        "How do we reduce false fire alarms at a site?",
        "Review false alarms monthly by site; the common causes are detector dust, contractor hot work without isolation and "
        "tenancy kitchens; responses in order: clean or relocate the detector, require a fire-system isolation on every hot-work "
        "permit, fit a heat detector in kitchens where the code allows; more than three false alarms in a month triggers a detector survey.",
        ("fire-system-inspection-schedule.md",),
    ),
    EvalCase(
        "C12-energy-anomaly",
        "When is a site's energy use an anomaly and who acts on it?",
        "A day more than 20 per cent above its baseline is an anomaly; the BMS raises an energy_anomaly event and the regional "
        "facilities manager reviews it within two working days; usual causes are a chiller in a fault state, an AHU left in manual, "
        "or plant left on after hours.",
        ("energy-and-sustainability-targets.md",),
    ),
]

TOOL_CASE_IDS = {c.case_id for c in CASES if c.expected_tool_calls}
DECLINE_CASE_IDS = {c.case_id for c in CASES if c.declines}


_CANNED: dict[str, tuple[str, list[str]]] = {
    "C06-entrapment-procedure": (
        "An entrapment is a P1 incident: establish voice contact with the trapped person and keep it until they are released, and get "
        "the lift contractor on site within 30 minutes.\n\n"
        "- The operations desk makes voice contact through the car intercom within 2 minutes and stays on the line.\n"
        "- Call the emergency services if anyone in the car is unwell or distressed, or if the contractor cannot meet the 30-minute target.\n"
        "- Harbourline staff never attempt to release a trapped person; only the lift contractor or the emergency services open a stalled car.\n"
        "- Report the entrapment to the Vertical Transport Safety Register within 24 hours and send a tenant notice the same day.\n"
        f"{CAVEAT}\n\n"
        f"Sources: {T_LIFT}",
        [T_LIFT],
    ),
    "C08-sla-hours": (
        "Work orders carry three priorities with response SLAs of 4, 24 and 72 hours.\n\n"
        "- P1 is a safety or business-critical fault (an entrapment, a disabled fire detection, a chiller lockout at a medical or office "
        "site in business hours) and must be cleared or made safe within 4 hours.\n"
        "- P2 is a fault with tenant impact but no immediate safety risk, within 24 hours.\n"
        "- P3 is planned or minor work, within 72 hours.\n"
        "- The SLA runs from the work order opening to the fault cleared or made safe; a breach is recorded against the contractor at the monthly review.\n"
        "- Separately from the SLA, any HVAC work order open longer than 48 hours is reviewed by the regional facilities manager.\n"
        f"{CAVEAT}\n\n"
        f"Sources: {T_SLA}",
        [T_SLA],
    ),
    "C09-after-hours-contractor": (
        "No. A contractor may not work on site after hours without an approved after-hours permit on file.\n\n"
        "- After-hours means outside 07:00 to 18:00 local time; the permit names a Harbourline site contact who can be reached by phone for the whole visit.\n"
        "- Access without a permit is logged as a warning by the access control system and reviewed by the site manager the next working day.\n"
        "- Hot work, work at height and work on the fire system also need a permit to work before starting, whatever the hour.\n"
        f"{CAVEAT}\n\n"
        f"Sources: {T_CONTRACTOR}",
        [T_CONTRACTOR],
    ),
    "C10-platform-data-source": (
        "Telemetry reaches the Site Operations Advisor through the Site APIs, exposed to the agent as four tools: get_site_summary, "
        "get_open_work_orders, get_incidents and get_inspection_schedule.\n\n"
        "- Upstream, BMS controllers, lift controllers, fire panels, access readers and smart meters publish to an ingestion tier; stream "
        "processing validates and enriches events and lands them in a lakehouse and a real-time store.\n"
        "- The agent never reads raw telemetry itself; every figure it states comes from a tool call.\n"
        "- The tools are published through the organisation's AI gateway so the same identity, budget and logging rules apply to agents as to applications.\n"
        "- Procedures come from a separate path: documents chunked by section, embedded and indexed in Azure AI Search.\n"
        f"{CAVEAT}\n\n"
        f"Sources: {T_PLATFORM}",
        [T_PLATFORM],
    ),
    "C11-false-alarm-reduction": (
        "Review the site's false alarms monthly and work through the causes in order: detectors, hot-work isolations, then kitchens.\n\n"
        "- The common causes are detector dust in plant rooms, contractor hot work without a fire-system isolation, and cooking in tenancy kitchens.\n"
        "- Clean or relocate the affected detector first.\n"
        "- Require a fire-system isolation on every hot-work permit.\n"
        "- Fit a heat detector in place of a smoke detector in kitchens where the code allows it.\n"
        "- A site with more than three false alarms in a month gets a detector survey.\n"
        f"{CAVEAT}\n\n"
        f"Sources: {T_FIRE}",
        [T_FIRE],
    ),
    "C12-energy-anomaly": (
        "A day's consumption more than 20 per cent above the site's baseline is an energy anomaly, and the regional facilities manager "
        "reviews it within two working days.\n\n"
        "- The baseline is the previous twelve months of smart meter readings for the same weekday type, adjusted for net lettable area.\n"
        "- The BMS raises an energy_anomaly event when the threshold is passed.\n"
        "- The usual causes are a chiller running in a fault state, an AHU left in manual after contractor work, or lighting and plant left on after hours.\n"
        f"{CAVEAT}\n\n"
        f"Sources: {T_ENERGY}",
        [T_ENERGY],
    ),
}


def mock_response(case: EvalCase) -> TurnResult:
    """Recorded-style response for a case, with figures from the Site API tools where relevant."""
    if case.case_id == "C01-chiller-trip-sop":
        return sop_turn(case.query)
    if case.case_id == "C02-fire-inspection-akl-017":
        return inspection_turn(case.query)
    if case.case_id == "C03-hvac-48h-and-fire-due":
        return hvac48_turn(case.query)
    if case.case_id == "C04-wlg-lift-incidents-7d":
        return lifts_turn(case.query)
    if case.case_id == "C05-eviction-refusal":
        return refusal_turn(case.query)
    if case.case_id == "C07-site-summary-syd-008":
        return summary_turn(case.query)
    answer, citations = _CANNED[case.case_id]
    searches = mock_search(case.query, citations)
    return TurnResult(question=case.query, answer=answer, citations=citations, searches=searches,
                      steps=[("search", s.call_id) for s in searches], input_tokens=2400, output_tokens=180, latency_s=2.1)
