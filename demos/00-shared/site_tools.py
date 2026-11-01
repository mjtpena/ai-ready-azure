"""Pure-Python "Site APIs" over the synthetic Harbourline data.

These are the Site Operations Advisor's function tools. They have no Azure dependency, so the same code backs the live
agent (as function tools or behind the API Management MCP server), the mock transcript, the Functions tools API and the
evaluation dataset. Each function returns a JSON-serialisable dict, starts with ``needs_attention`` where it applies, and
never raises for unknown ids (it returns an ``error`` key instead) so the agent can explain the problem rather than crash.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

DATA_DIR = Path(__file__).resolve().parent / "data"
REGIONS = ("AKL", "WLG", "SYD", "MEL")
SYSTEMS = ("hvac", "lift", "fire", "access", "energy")
INCIDENT_TYPES = ("lift_incident", "fire_alarm", "fire_system_fault", "door_forced", "energy_anomaly", "hvac_fault")
MAX_LIST = 25


@lru_cache(maxsize=1)
def load_sites() -> dict[str, dict[str, Any]]:
    with (DATA_DIR / "sites.json").open(encoding="utf-8") as fh:
        return {s["site_id"]: s for s in json.load(fh)}


@lru_cache(maxsize=1)
def load_events() -> list[dict[str, Any]]:
    with (DATA_DIR / "site_events.jsonl").open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@lru_cache(maxsize=1)
def load_work_orders() -> list[dict[str, Any]]:
    with (DATA_DIR / "work_orders.jsonl").open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@lru_cache(maxsize=1)
def load_inspections() -> list[dict[str, Any]]:
    with (DATA_DIR / "inspections.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def as_of() -> datetime:
    """The dataset's "now": the end of the recorded period (last daily energy reading plus the rest of that day)."""
    last = max(_parse_ts(e["ts"]) for e in load_events())
    return last.replace(hour=23, minute=59, second=59)


def _parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _age_hours(opened_at: str, now: datetime) -> float:
    return round((now - _parse_ts(opened_at)).total_seconds() / 3600, 1)


def _site_ids_in(scope: str) -> list[str] | None:
    """Site ids for a region code or ALL; None when the scope is not a region."""
    scope = (scope or "ALL").strip().upper()
    if scope == "ALL":
        return list(load_sites())
    if scope in REGIONS:
        return [sid for sid, s in load_sites().items() if s["region"] == scope]
    return None


def _system(value: str, allow_any: str) -> str | None:
    value = (value or allow_any).strip().lower()
    return value if value in SYSTEMS or value == allow_any else None


def _wo_row(w: dict[str, Any], now: datetime) -> dict[str, Any]:
    age = _age_hours(w["opened_at"], now)
    return {
        "wo_id": w["wo_id"],
        "site_id": w["site_id"],
        "site_name": load_sites()[w["site_id"]]["site_name"],
        "region": w["region"],
        "system": w["system"],
        "priority": w["priority"],
        "opened_at": w["opened_at"],
        "age_hours": age,
        "sla_hours": w["sla_hours"],
        "sla_breached": age > w["sla_hours"],
        "summary": w["summary"],
        "contractor": w["contractor"],
    }


def get_site_summary(site_id: str) -> dict[str, Any]:
    """Fourteen-day summary for one site: what needs attention, open work, faults and incidents, inspections, energy."""
    site = load_sites().get((site_id or "").strip().upper())
    if site is None:
        return {"error": f"Unknown site_id '{site_id}'. Known ids look like HBL-AKL-017."}
    sid = site["site_id"]
    now = as_of()
    week_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0)
    events = [e for e in load_events() if e["site_id"] == sid]
    week = [e for e in events if _parse_ts(e["ts"]) >= week_start]
    open_wos = [w for w in load_work_orders() if w["site_id"] == sid and w["status"] == "open"]
    inspections = [r for r in load_inspections() if r["site_id"] == sid]
    overdue = [r for r in inspections if date.fromisoformat(r["next_due"]) < now.date()]
    fire_cert = next((r for r in inspections if r["system"] == "fire" and r["kind"] == "annual_certificate"), None)
    lift_cert = next((r for r in inspections if r["system"] == "lift"), None)
    energy = [e for e in week if e["event_type"] == "energy_daily"]
    baseline = sum(float(e["detail"].split("baseline ")[1].split(" ")[0]) for e in energy) if energy else 0.0
    kwh = sum(e["value"] or 0 for e in energy)
    entrapments = [e for e in week if e["event_type"] == "lift_incident" and e["detail"].startswith("entrapment")]
    return {
        "site": {k: site[k] for k in ("site_id", "site_name", "region", "city", "building_type", "floors", "lifts", "chillers", "fire_system")},
        # first, so the agent cannot miss it: the facts the SOPs act on
        "needs_attention": {
            "open_p1_work_orders": sum(w["priority"] == "P1" for w in open_wos),
            "sla_breached_work_orders": sum(_age_hours(w["opened_at"], now) > w["sla_hours"] for w in open_wos),
            "hvac_faults_open_over_48h": sum(w["system"] == "hvac" and _age_hours(w["opened_at"], now) > 48 for w in open_wos),
            "overdue_inspections": len(overdue),
            "entrapments_last_7_days": len(entrapments),
        },
        "period": {"from": week_start.strftime("%Y-%m-%d"), "to": now.strftime("%Y-%m-%d"), "note": "last 7 days of a 14-day recorded window"},
        "open_work_orders": [_wo_row(w, now) for w in sorted(open_wos, key=lambda w: (w["priority"], w["opened_at"]))],
        "faults_last_7_days_by_system": dict(sorted(Counter(e["system"] for e in week if e["event_type"] in ("hvac_fault", "fire_system_fault", "lift_incident")).items())),
        "incidents_last_7_days": [
            {"ts": e["ts"], "asset_id": e["asset_id"], "type": e["event_type"], "severity": e["severity"], "detail": e["detail"]}
            for e in week if e["event_type"] in INCIDENT_TYPES and e["event_type"] != "hvac_fault"
        ][:MAX_LIST],
        "inspections": {
            "fire_annual_certificate": {k: fire_cert[k] for k in ("next_due", "certificate_status", "inspector_firm")} if fire_cert else None,
            "lift_annual_certificate": {k: lift_cert[k] for k in ("next_due", "certificate_status", "inspector_firm")} if lift_cert else None,
            "overdue": [{"system": r["system"], "kind": r["kind"], "next_due": r["next_due"]} for r in overdue],
        },
        "energy_last_7_days": {
            "kwh": round(kwh),
            "baseline_kwh": round(baseline),
            "vs_baseline_pct": round((kwh / baseline - 1) * 100, 1) if baseline else None,
            "anomaly_days": sum(e["event_type"] == "energy_anomaly" for e in week),
        },
        "contractors": {"hvac": site["contractor_hvac"], "lift": site["contractor_lift"], "fire": site["contractor_fire"]},
    }


def get_open_work_orders(region: str, system: str, open_longer_than_hours: int) -> dict[str, Any]:
    """Open work orders in a region (or ALL) for one system (or any), open for more than N hours, oldest first."""
    sites = _site_ids_in(region)
    if sites is None:
        return {"error": f"Unknown region '{region}'. Use ALL or one of {', '.join(REGIONS)}."}
    sys_filter = _system(system, "any")
    if sys_filter is None:
        return {"error": f"Unknown system '{system}'. Use any or one of {', '.join(SYSTEMS)}."}
    try:
        min_hours = max(0, int(open_longer_than_hours))
    except (TypeError, ValueError):
        return {"error": "open_longer_than_hours must be an integer number of hours (0 for all open work orders)."}
    now = as_of()
    site_set = set(sites)
    rows = [
        _wo_row(w, now)
        for w in load_work_orders()
        if w["status"] == "open" and w["site_id"] in site_set and (sys_filter == "any" or w["system"] == sys_filter)
        and _age_hours(w["opened_at"], now) > min_hours
    ]
    rows.sort(key=lambda r: (-r["age_hours"], r["wo_id"]))
    return {
        "as_of": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "filter": {"region": (region or "ALL").upper(), "system": sys_filter, "open_longer_than_hours": min_hours},
        # first, so the agent cannot miss it
        "needs_attention": {
            "count": len(rows),
            "p1_count": sum(r["priority"] == "P1" for r in rows),
            "sla_breached_count": sum(r["sla_breached"] for r in rows),
            "sites": sorted({r["site_id"] for r in rows}),
        },
        "by_region": dict(sorted(Counter(r["region"] for r in rows).items())),
        "by_priority": dict(sorted(Counter(r["priority"] for r in rows).items())),
        "work_orders": rows[:MAX_LIST],
        "truncated": len(rows) > MAX_LIST,
    }


def get_incidents(region: str, system: str, days: int) -> dict[str, Any]:
    """Incidents (lift incidents, fire alarms and faults, forced doors, energy anomalies, HVAC faults) over the last N days."""
    sites = _site_ids_in(region)
    if sites is None:
        return {"error": f"Unknown region '{region}'. Use ALL or one of {', '.join(REGIONS)}."}
    sys_filter = _system(system, "any")
    if sys_filter is None:
        return {"error": f"Unknown system '{system}'. Use any or one of {', '.join(SYSTEMS)}."}
    try:
        days = max(1, min(int(days), 14))
    except (TypeError, ValueError):
        return {"error": "days must be an integer from 1 to 14."}
    now = as_of()
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0)
    site_set = set(sites)
    rows = [
        e for e in load_events()
        if e["site_id"] in site_set and e["event_type"] in INCIDENT_TYPES and (sys_filter == "any" or e["system"] == sys_filter)
        and _parse_ts(e["ts"]) >= start
    ]
    by_site: Counter = Counter(e["site_id"] for e in rows)
    return {
        "window": {"from": start.strftime("%Y-%m-%d"), "to": now.strftime("%Y-%m-%d"), "days": days},
        "filter": {"region": (region or "ALL").upper(), "system": sys_filter},
        # first, so the agent cannot miss it
        "needs_attention": {
            "entrapments": sum(e["event_type"] == "lift_incident" and e["detail"].startswith("entrapment") for e in rows),
            "genuine_fire_alarms": sum(e["event_type"] == "fire_alarm" and e["severity"] == "critical" for e in rows),
            "critical": sum(e["severity"] == "critical" for e in rows),
        },
        "count": len(rows),
        "by_type": dict(sorted(Counter(e["detail"].split(":")[0] if e["event_type"] == "lift_incident" else e["event_type"] for e in rows).items())),
        "by_site": [
            {"site_id": sid, "site_name": load_sites()[sid]["site_name"], "count": n,
             "types": sorted({e["detail"].split(":")[0] if e["event_type"] == "lift_incident" else e["event_type"] for e in rows if e["site_id"] == sid})}
            for sid, n in sorted(by_site.items(), key=lambda kv: (-kv[1], kv[0]))
        ][:10],
        "incidents": [
            {"ts": e["ts"], "site_id": e["site_id"], "asset_id": e["asset_id"], "system": e["system"], "type": e["event_type"],
             "severity": e["severity"], "detail": e["detail"]}
            for e in sorted(rows, key=lambda e: e["ts"], reverse=True)
        ][:30],
        "truncated": len(rows) > 30,
    }


def get_inspection_schedule(scope: str, system: str, month: str) -> dict[str, Any]:
    """Statutory inspections due in a calendar month for a site id, a region or ALL; also everything already overdue."""
    scope_norm = (scope or "ALL").strip().upper()
    sites = _site_ids_in(scope_norm)
    if sites is None:
        if scope_norm in load_sites():
            sites = [scope_norm]
        else:
            return {"error": f"Unknown scope '{scope}'. Use a site id like HBL-AKL-017, a region ({', '.join(REGIONS)}) or ALL."}
    sys_filter = _system(system, "all")
    if sys_filter is None or sys_filter in ("hvac", "access", "energy"):
        return {"error": f"Unknown inspection system '{system}'. Use fire, lift or all."}
    try:
        year, mon = (int(x) for x in (month or "").split("-"))
        first = date(year, mon, 1)
    except (TypeError, ValueError):
        return {"error": "month must be YYYY-MM, for example 2026-11."}
    now = as_of().date()
    site_set = set(sites)
    rows = [r for r in load_inspections() if r["site_id"] in site_set and (sys_filter == "all" or r["system"] == sys_filter)]

    def row(r: dict[str, Any]) -> dict[str, Any]:
        return {**r, "site_name": load_sites()[r["site_id"]]["site_name"], "overdue": date.fromisoformat(r["next_due"]) < now}

    in_month = [row(r) for r in rows if date.fromisoformat(r["next_due"]).replace(day=1) == first]
    due = [r for r in in_month if r["kind"] != "monthly_test"]  # certificate inspections by an approved inspector
    tests = [r for r in in_month if r["kind"] == "monthly_test"]  # routine contractor tests, listed apart
    overdue = [row(r) for r in rows if date.fromisoformat(r["next_due"]) < now]
    for lst in (due, tests, overdue):
        lst.sort(key=lambda r: (r["next_due"], r["site_id"]))
    return {
        "scope": scope_norm,
        "system": sys_filter,
        "month": first.strftime("%Y-%m"),
        "as_of": now.isoformat(),
        # first, so the agent cannot miss it
        "needs_attention": {
            "inspections_due_this_month": len(due),
            "overdue": len(overdue),
            "expiring_certificates": sum(r["certificate_status"] == "expiring" for r in due),
            "sites_due": sorted({r["site_id"] for r in due}),
        },
        "due": due[:MAX_LIST],
        "overdue": overdue[:MAX_LIST],
        "monthly_tests_due": tests[:MAX_LIST],
        "truncated": len(due) > MAX_LIST or len(overdue) > MAX_LIST or len(tests) > MAX_LIST,
        "statutory_note": "'due' holds certificate inspections by an approved inspector (annual certificates, five-yearly sprinkler "
                          "tests, lift certificates); routine monthly tests by the site contractor are in monthly_tests_due. Frequencies "
                          "and who may inspect come from the fire-system inspection schedule and lift procedure documents.",
    }


TOOL_FUNCTIONS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_site_summary": get_site_summary,
    "get_open_work_orders": get_open_work_orders,
    "get_incidents": get_incidents,
    "get_inspection_schedule": get_inspection_schedule,
}

# JSON schemas shared by the agent definition (FunctionTool), the OpenAPI spec of the tools API (and so the MCP server
# exposed by API Management) and the evaluation dataset (tool_definitions).
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_site_summary",
        "description": "Summary for one site over the last 7 days of the recorded window: what needs attention (open P1 work, SLA "
        "breaches, HVAC faults open over 48 hours, overdue inspections, lift entrapments), open work orders, faults and incidents "
        "by system, the next fire and lift certificates, energy against baseline and the contractors. Use for any question about one site.",
        "parameters": {
            "type": "object",
            "properties": {"site_id": {"type": "string", "description": "Site id, e.g. HBL-AKL-017."}},
            "required": ["site_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_open_work_orders",
        "description": "Open work orders across a region or all sites, for one building system or any, that have been open for more than "
        "N hours (0 for every open work order): count, P1 count, SLA breaches, the sites involved and each work order's age against "
        "its SLA. Use for 'which sites have faults open longer than X hours' and SLA questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "ALL, or a region code: AKL, WLG, SYD or MEL."},
                "system": {"type": "string", "description": "any, hvac, lift, fire, access or energy."},
                "open_longer_than_hours": {"type": "integer", "description": "Only work orders open for more than this many hours; 0 for all open."},
            },
            "required": ["region", "system", "open_longer_than_hours"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_incidents",
        "description": "Incidents over the last N days (1 to 14) for a region or ALL and a system or any: lift incidents (entrapment, "
        "door fault, levelling fault, out of service), fire alarms and fire-system faults, forced doors, energy anomalies and HVAC "
        "faults, with counts by type and by site; needs_attention gives entrapments, genuine fire alarms and critical events.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "ALL, or a region code: AKL, WLG, SYD or MEL."},
                "system": {"type": "string", "description": "any, hvac, lift, fire, access or energy."},
                "days": {"type": "integer", "description": "Look-back window in days, 1 to 14. The recorded window ends 2026-11-15."},
            },
            "required": ["region", "system", "days"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_inspection_schedule",
        "description": "Statutory certificate inspections (fire annual certificates, five-yearly sprinkler tests, lift annual "
        "certificates) due in a calendar month for one site id, a region or ALL, plus everything already overdue, which certificates "
        "are expiring, and the routine monthly fire tests listed separately. Use for 'is site X due an inspection this month' and "
        "'which sites are overdue'.",
        "parameters": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "description": "A site id like HBL-AKL-017, a region code (AKL, WLG, SYD, MEL) or ALL."},
                "system": {"type": "string", "description": "fire, lift or all."},
                "month": {"type": "string", "description": "Calendar month, YYYY-MM. 'This month' in the recorded window is 2026-11."},
            },
            "required": ["scope", "system", "month"],
            "additionalProperties": False,
        },
    },
]


def call_tool(name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call by name with JSON or dict arguments."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Unknown tool '{name}'."}
    args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
    return fn(**args)


if __name__ == "__main__":
    print(json.dumps(get_open_work_orders("ALL", "hvac", 48), indent=2))
    print(json.dumps(get_inspection_schedule("HBL-AKL-017", "fire", "2026-11"), indent=2))
    print(json.dumps(get_incidents("WLG", "lift", 7)["needs_attention"], indent=2))
    print(json.dumps(get_site_summary("HBL-SYD-008")["needs_attention"], indent=2))
