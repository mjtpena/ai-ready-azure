"""Deterministic synthetic facilities data for the AI-Ready Azure course.

Harbourline Facilities is a fictional smart-building operator. Nothing here describes a real company, building,
contractor or regulator. Produces, under ``demos/00-shared/data``:

* ``sites.json``          - 120 commercial sites across Auckland, Wellington, Sydney and Melbourne
* ``assets.json``         - chillers, air handlers, lifts, fire panels, access controllers and meters per site
* ``site_events.jsonl``   - building telemetry events over 14 days ending 2026-11-15 (faults, incidents, alarms, energy)
* ``work_orders.jsonl``   - the work orders those events raised, with priorities and SLAs
* ``inspections.json``    - statutory inspection schedule (fire, lift, sprinkler) per site
* ``knowledge/*.md``      - eight short grounding documents (course material, not legal or engineering advice)

Everything is seeded (seed 2026) and a handful of anchors are injected deterministically so every rehearsal and
every demo recording shows the same numbers (see ``docs/EXPECTED.md`` and ``tests/test_data.py``).
Run: ``python generate_data.py``
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from knowledge_docs import KNOWLEDGE_DOCS

SEED = 2026
DATA_DIR = Path(__file__).resolve().parent / "data"
PERIOD_END = datetime(2026, 11, 15, 23, 59, 59, tzinfo=timezone.utc)
PERIOD_DAYS = 14
PERIOD_START = (PERIOD_END - timedelta(days=PERIOD_DAYS - 1)).replace(hour=0, minute=0, second=0)
LAST_7_START = (PERIOD_END - timedelta(days=6)).replace(hour=0, minute=0, second=0)

SLA_HOURS = {"P1": 4, "P2": 24, "P3": 72}


@dataclass(frozen=True)
class Region:
    code: str
    country: str
    city: str
    count: int
    lat: float
    lon: float
    hvac_factor: float  # summer in the Australian cities: more HVAC faults
    streets: tuple[str, ...]


REGIONS = [
    Region("AKL", "NZ", "Auckland", 40, -36.8485, 174.7633, 1.0,
           ("Quay Street", "Fanshawe Street", "Albert Street", "Victoria Street", "Wynyard", "Newmarket", "Penrose", "Takapuna", "Manukau", "Greenlane")),
    Region("WLG", "NZ", "Wellington", 25, -41.2865, 174.7762, 0.9,
           ("Lambton", "Featherston Street", "The Terrace", "Willis Street", "Thorndon", "Te Aro", "Petone", "Johnsonville")),
    Region("SYD", "AU", "Sydney", 30, -33.8688, 151.2093, 1.6,
           ("Pitt Street", "George Street", "Kent Street", "Macquarie Park", "Parramatta", "Chatswood", "Mascot", "Homebush")),
    Region("MEL", "AU", "Melbourne", 25, -37.8136, 144.9631, 1.6,
           ("Collins Street", "Bourke Street", "Docklands", "Southbank", "Richmond", "Dandenong", "Tullamarine", "Box Hill")),
]

BUILDING_TYPES = ["office_tower", "office_tower", "office_tower", "retail", "logistics", "medical", "mixed_use"]
SUFFIX = {
    "office_tower": ("Tower", "House", "Centre"),
    "retail": ("Arcade", "Plaza", "Mall"),
    "logistics": ("Logistics Hub", "Distribution Centre"),
    "medical": ("Medical Centre", "Health Hub"),
    "mixed_use": ("Quarter", "Exchange"),
}
CONTRACTORS_HVAC = ("Tidewater Mechanical", "Northgate Building Services", "Harbourline Field Team")
CONTRACTORS_LIFT = ("Vertex Lift Services", "Southern Vertical", "Harbourline Field Team")
CONTRACTORS_FIRE = ("Beacon Fire Systems", "Harbourline Field Team")
FIRE_INSPECTORS = ("Beacon Fire Systems", "Coastline Compliance Inspectors")

HVAC_FAULTS = ["chiller_trip", "ahu_fan_fault", "high_zone_temp", "low_refrigerant"]
LIFT_INCIDENTS = ["door_fault", "door_fault", "levelling_fault", "out_of_service", "entrapment"]

# ---- Anchors: the numbers every demo relies on (asserted at the end of main()) -------------------------------------
# Exactly six HVAC work orders are open for more than 48 hours at PERIOD_END. Three of those sites also have a fire-system
# certificate due in November 2026, which is what the hero question ("faults open > 48 h AND inspection due this month")
# returns.
ANCHOR_HVAC_OPEN = [
    # site, fault, hours open at PERIOD_END, priority
    ("HBL-AKL-017", "ahu_fan_fault", 71, "P2"),
    ("HBL-AKL-033", "ahu_fan_fault", 54, "P2"),
    ("HBL-WLG-011", "low_refrigerant", 63, "P2"),
    ("HBL-SYD-008", "chiller_trip", 58, "P1"),  # the double trip of 13 November, see ANCHOR_DOUBLE_TRIP
    ("HBL-SYD-021", "high_zone_temp", 49, "P2"),
    ("HBL-MEL-006", "ahu_fan_fault", 96, "P2"),
]
ANCHOR_FIRE_CERT_DUE = {
    "HBL-AKL-017": date(2026, 11, 24),
    "HBL-WLG-011": date(2026, 11, 28),
    "HBL-SYD-008": date(2026, 11, 30),
    # the other three anchored HVAC sites are deliberately NOT due in November
    "HBL-AKL-033": date(2027, 2, 9),
    "HBL-SYD-021": date(2027, 1, 21),
    "HBL-MEL-006": date(2026, 12, 17),
}
ANCHOR_DOUBLE_TRIP = ("HBL-SYD-008", datetime(2026, 11, 13, 1, 40, tzinfo=timezone.utc))
# Wellington lift incidents in the last 7 days: exactly five, at three sites, one entrapment.
ANCHOR_WLG_LIFTS = [
    ("HBL-WLG-009", "out_of_service", datetime(2026, 11, 10, 2, 15, tzinfo=timezone.utc)),
    ("HBL-WLG-018", "door_fault", datetime(2026, 11, 11, 20, 5, tzinfo=timezone.utc)),
    ("HBL-WLG-004", "entrapment", datetime(2026, 11, 12, 3, 48, tzinfo=timezone.utc)),
    ("HBL-WLG-009", "levelling_fault", datetime(2026, 11, 13, 22, 30, tzinfo=timezone.utc)),
    ("HBL-WLG-004", "door_fault", datetime(2026, 11, 14, 1, 12, tzinfo=timezone.utc)),
]
ANCHOR_SITES = {s for s, *_ in ANCHOR_HVAC_OPEN} | {s for s, *_ in ANCHOR_WLG_LIFTS}
OVERDUE_CERT_SITES = {"HBL-AKL-029", "HBL-SYD-014", "HBL-MEL-019"}


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_sites(rng: random.Random) -> list[dict]:
    sites: list[dict] = []
    for region in REGIONS:
        for n in range(1, region.count + 1):
            site_id = f"HBL-{region.code}-{n:03d}"
            btype = rng.choice(BUILDING_TYPES)
            street = region.streets[(n - 1) % len(region.streets)]
            suffix = rng.choice(SUFFIX[btype])
            floors = {"office_tower": rng.randint(8, 32), "retail": rng.randint(2, 4), "logistics": 1,
                      "medical": rng.randint(3, 7), "mixed_use": rng.randint(6, 18)}[btype]
            lifts = {"logistics": rng.randint(1, 2), "retail": rng.randint(2, 4)}.get(btype, max(1, floors // 4))
            chillers = 0 if btype == "logistics" and rng.random() < 0.5 else rng.randint(1, 3 if floors > 12 else 2)
            sprinkler = btype != "retail" or rng.random() < 0.7
            sites.append({
                "site_id": site_id,
                "region": region.code,
                "country": region.country,
                "city": region.city,
                "site_name": f"{street} {suffix}",
                "building_type": btype,
                "floors": floors,
                "nla_sqm": int(floors * rng.uniform(900, 1600)) if btype != "logistics" else int(rng.uniform(8000, 24000)),
                "lifts": lifts,
                "chillers": chillers,
                "fire_system": "sprinkler_and_detection" if sprinkler else "detection_only",
                "contractor_hvac": rng.choice(CONTRACTORS_HVAC),
                "contractor_lift": rng.choice(CONTRACTORS_LIFT),
                "contractor_fire": rng.choice(CONTRACTORS_FIRE),
                "opened_year": rng.randint(1988, 2023),
                "lat": round(region.lat + rng.uniform(-0.06, 0.06), 5),
                "lon": round(region.lon + rng.uniform(-0.06, 0.06), 5),
            })
    # The anchored sites need the plant their stories rely on
    by_id = {s["site_id"]: s for s in sites}
    for sid, *_ in ANCHOR_HVAC_OPEN:
        by_id[sid]["chillers"] = max(1, by_id[sid]["chillers"])
    by_id["HBL-SYD-008"].update(site_name="Homebush Tower", building_type="office_tower", floors=max(12, by_id["HBL-SYD-008"]["floors"]), chillers=2)
    by_id["HBL-AKL-017"].update(building_type="office_tower", floors=max(10, by_id["HBL-AKL-017"]["floors"]))
    for sid, *_ in ANCHOR_WLG_LIFTS:
        by_id[sid]["lifts"] = max(2, by_id[sid]["lifts"])
    return sites


def build_assets(rng: random.Random, sites: list[dict]) -> list[dict]:
    assets: list[dict] = []
    for s in sites:
        sid = s["site_id"].removeprefix("HBL-")
        year = s["opened_year"]

        def add(prefix: str, n: int, system: str, kind: str) -> None:
            for i in range(1, n + 1):
                assets.append({
                    "asset_id": f"{prefix}-{sid}-{i}",
                    "site_id": s["site_id"],
                    "system": system,
                    "type": kind,
                    "installed_year": rng.randint(year, 2024),
                    "last_service": (PERIOD_END - timedelta(days=rng.randint(5, 180))).strftime("%Y-%m-%d"),
                })

        add("CH", s["chillers"], "hvac", "chiller")
        add("AHU", max(2, s["floors"] // 5), "hvac", "air_handling_unit")
        add("LIFT", s["lifts"], "lift", "passenger_lift")
        add("FIP", 1, "fire", "fire_indicator_panel")
        add("ACS", 1, "access", "access_controller")
        add("MTR", 1, "energy", "smart_meter")
    return assets


class EventLog:
    """Collects events and work orders; chronological ids are assigned in ``finalise``."""

    def __init__(self, rng: random.Random, sites: list[dict], assets: list[dict]):
        self.rng = rng
        self.sites = {s["site_id"]: s for s in sites}
        self.assets_by_site: dict[str, list[dict]] = {}
        for a in assets:
            self.assets_by_site.setdefault(a["site_id"], []).append(a)
        self.events: list[dict] = []
        self.work_orders: list[dict] = []

    def asset(self, site_id: str, system: str, kind: str | None = None) -> dict:
        pool = [a for a in self.assets_by_site[site_id] if a["system"] == system and (kind is None or a["type"] == kind)]
        return self.rng.choice(pool)

    def event(self, when: datetime, site_id: str, asset: dict | None, system: str, event_type: str, severity: str,
              detail: str, value: float | None = None) -> dict:
        e = {
            "event_id": None,
            "ts": ts(when),
            "site_id": site_id,
            "region": self.sites[site_id]["region"],
            "asset_id": asset["asset_id"] if asset else None,
            "system": system,
            "event_type": event_type,
            "severity": severity,
            "value": value,
            "detail": detail,
        }
        self.events.append(e)
        return e

    def work_order(self, opened: datetime, site_id: str, system: str, priority: str, summary: str, contractor: str,
                   closed: datetime | None, source: dict | None) -> dict:
        wo = {
            "wo_id": None,
            "site_id": site_id,
            "region": self.sites[site_id]["region"],
            "system": system,
            "priority": priority,
            "sla_hours": SLA_HOURS[priority],
            "opened_at": ts(opened),
            "closed_at": ts(closed) if closed else None,
            "status": "closed" if closed else "open",
            "source_event_id": None,
            "contractor": contractor,
            "summary": summary,
            "_source": source,
        }
        self.work_orders.append(wo)
        return wo

    def finalise(self) -> None:
        self.events.sort(key=lambda e: e["ts"])
        for i, e in enumerate(self.events, start=1):
            e["event_id"] = f"EV-{i:06d}"
        for wo in self.work_orders:
            src = wo.pop("_source")
            wo["source_event_id"] = src["event_id"] if src else None
        self.work_orders.sort(key=lambda w: w["opened_at"])
        for i, wo in enumerate(self.work_orders, start=24001):
            wo["wo_id"] = f"WO-{i}"


def hvac_fault(log: EventLog, site_id: str, when: datetime, fault: str, *, priority: str | None = None,
               clear_after_h: float | None = None, keep_open: bool = False) -> None:
    site = log.sites[site_id]
    kind = "chiller" if fault in ("chiller_trip", "low_refrigerant") else "air_handling_unit"
    if kind == "chiller" and site["chillers"] == 0:
        kind, fault = "air_handling_unit", "ahu_fan_fault"
    asset = log.asset(site_id, "hvac", kind)
    business_hours = when.hour >= 21 or when.hour < 7  # roughly 08:00-18:00 local for NZ/AU in November, in UTC
    if priority is None:
        priority = "P1" if fault == "chiller_trip" and site["building_type"] in ("medical", "office_tower") and business_hours else "P2"
    severity = "critical" if priority == "P1" else "warning"
    detail = {"chiller_trip": "chiller tripped on high condenser pressure", "ahu_fan_fault": "supply fan VSD fault",
              "high_zone_temp": "zone temperature above 26 C for 60 minutes", "low_refrigerant": "low refrigerant pressure alarm"}[fault]
    value = round(log.rng.uniform(26.3, 28.9), 1) if fault == "high_zone_temp" else None
    opened = log.event(when, site_id, asset, "hvac", "hvac_fault", severity, f"{fault}: {detail}", value)
    closed_at: datetime | None = None
    if not keep_open:
        if clear_after_h is None:
            roll = log.rng.random()
            clear_after_h = log.rng.uniform(1, 24) if roll < 0.7 else log.rng.uniform(24, 47) if roll < 0.9 else None
        if clear_after_h is None and when < PERIOD_END - timedelta(hours=48):
            clear_after_h = log.rng.uniform(24, 47)  # only the anchored faults stay open past 48 hours
        if clear_after_h is not None:
            cleared = when + timedelta(hours=clear_after_h)
            if cleared <= PERIOD_END:
                log.event(cleared, site_id, asset, "hvac", "hvac_fault_cleared", "info", f"{fault} cleared by {site['contractor_hvac']}")
                closed_at = cleared
    log.work_order(when, site_id, "hvac", priority, f"{asset['asset_id']}: {detail}", site["contractor_hvac"], closed_at, opened)


def lift_incident(log: EventLog, site_id: str, when: datetime, kind: str) -> None:
    site = log.sites[site_id]
    asset = log.asset(site_id, "lift")
    severity = {"entrapment": "critical", "out_of_service": "warning"}.get(kind, "info")
    detail = {"entrapment": "passenger entrapment between floors, voice contact established",
              "door_fault": "door failed to close, repeated reopen cycle", "levelling_fault": "car stopped 40 mm above floor level",
              "out_of_service": "lift out of service on controller fault"}[kind]
    opened = log.event(when, site_id, asset, "lift", "lift_incident", severity, f"{kind}: {detail}")
    priority = {"entrapment": "P1", "out_of_service": "P2"}.get(kind, "P3")
    hours = {"P1": log.rng.uniform(0.4, 3.5), "P2": log.rng.uniform(3, 30), "P3": log.rng.uniform(10, 90)}[priority]
    closed = when + timedelta(hours=hours)
    log.work_order(when, site_id, "lift", priority, f"{asset['asset_id']}: {detail}", site["contractor_lift"],
                   closed if closed <= PERIOD_END else None, opened)


def build_events(rng: random.Random, sites: list[dict], assets: list[dict]) -> EventLog:
    log = EventLog(rng, sites, assets)
    by_region = {r.code: r for r in REGIONS}
    for idx, site in enumerate(sites):
        sid = site["site_id"]
        region = by_region[site["region"]]
        baseline_kwh = site["nla_sqm"] * {"office_tower": 0.55, "retail": 0.7, "logistics": 0.25, "medical": 0.9, "mixed_use": 0.5}[site["building_type"]]
        test_day = (idx % 26) + 1  # day of month of the monthly fire test
        for day in range(PERIOD_DAYS):
            day_start = PERIOD_START + timedelta(days=day)
            local_date = (day_start + timedelta(hours=13)).date()  # NZ/AU local date for the day's events

            def at(hour_lo: float = 0, hour_hi: float = 24) -> datetime:
                return day_start + timedelta(hours=rng.uniform(hour_lo, hour_hi))

            # HVAC faults (the anchored sites get theirs below)
            if rng.random() < 0.12 * region.hvac_factor and sid not in ANCHOR_SITES:
                hvac_fault(log, sid, at(), rng.choice(HVAC_FAULTS))
            # Lift incidents (random Wellington ones in the last 7 days are suppressed; the anchors replace them)
            for _ in range(site["lifts"]):
                if rng.random() < 0.03:
                    when = at()
                    if site["region"] == "WLG" and when >= LAST_7_START:
                        continue
                    lift_incident(log, sid, when, rng.choice(LIFT_INCIDENTS))
            # Fire system: monthly test, alarms, faults
            fip = log.asset(sid, "fire")
            if local_date.day == test_day:
                passed = rng.random() > 0.05
                when = at(21, 23)
                opened = log.event(when, sid, fip, "fire", "fire_test", "info" if passed else "warning",
                                   "monthly fire system test " + ("passed" if passed else "FAILED: detector loop 2 open circuit"))
                if not passed:
                    log.work_order(when, sid, "fire", "P2", f"{fip['asset_id']}: monthly test failed, detector loop 2", site["contractor_fire"], None, opened)
            if rng.random() < 0.04:
                when = at()
                genuine = rng.random() < 0.02 and when < LAST_7_START
                log.event(when, sid, fip, "fire", "fire_alarm", "critical" if genuine else "warning",
                          "genuine alarm: smoke in plant room, brigade attended" if genuine
                          else "false alarm: " + rng.choice(["detector dust", "contractor hot work", "burnt toast in tenancy kitchen"]))
            if rng.random() < 0.02:
                when = at()
                opened = log.event(when, sid, fip, "fire", "fire_system_fault", "warning",
                                   rng.choice(["detector_fault: loop 1 detector 14 isolated", "sprinkler_pressure_low: jacking pump cycling"]))
                closed = when + timedelta(hours=rng.uniform(4, 40))
                log.work_order(when, sid, "fire", "P2", f"{fip['asset_id']}: {opened['detail']}", site["contractor_fire"], closed if closed <= PERIOD_END else None, opened)
            # Access control
            acs = log.asset(sid, "access")
            if rng.random() < 0.05:
                when = at()
                opened = log.event(when, sid, acs, "access", "door_forced", "warning",
                                   rng.choice(["loading dock door forced", "plant room door held open 10 minutes", "fire stair door forced"]))
                closed = when + timedelta(hours=rng.uniform(8, 70))
                log.work_order(when, sid, "access", "P3", f"{acs['asset_id']}: {opened['detail']}", "Harbourline Field Team", closed if closed <= PERIOD_END else None, opened)
            if rng.random() < 0.10:
                log.event(at(), sid, acs, "access", "access_denied_burst", "info", f"{rng.randint(5, 14)} denied badge reads in 2 minutes at one reader")
            if rng.random() < 0.40:
                permit = rng.random() < 0.85
                log.event(at(8, 17), sid, acs, "access", "after_hours_access", "info" if permit else "warning",
                          "after-hours contractor access " + ("with approved permit" if permit else "WITHOUT a permit on file"))
            if rng.random() < 0.30:
                log.event(at(19, 23.5), sid, acs, "access", "contractor_sign_in", "info",
                          f"{rng.choice(CONTRACTORS_HVAC + CONTRACTORS_LIFT + CONTRACTORS_FIRE)} signed in for a work order")
            # Energy
            mtr = log.asset(sid, "energy")
            weekend = local_date.weekday() >= 5
            base_today = baseline_kwh * (0.55 if weekend else 1.0)
            kwh = base_today * rng.uniform(0.92, 1.08)
            anomaly = rng.random() < 0.03
            if anomaly:
                kwh *= rng.uniform(1.25, 1.42)
            log.event(day_start + timedelta(hours=11), sid, mtr, "energy", "energy_daily", "info", f"daily consumption; baseline {round(base_today)} kWh", round(kwh))
            if anomaly:
                log.event(day_start + timedelta(hours=11, minutes=5), sid, mtr, "energy", "energy_anomaly", "warning",
                          f"consumption {round((kwh / base_today - 1) * 100)} % above baseline", round(kwh))
            # Planned preventive work
            if rng.random() < 0.05:
                when = at(19, 23)
                system = rng.choice(["hvac", "lift", "fire"])
                closed = when + timedelta(hours=rng.uniform(2, 60))
                log.work_order(when, sid, system, "P3", f"planned {system} preventive maintenance visit", site[f"contractor_{system}"],
                               closed if closed <= PERIOD_END else None, None)

    # ---- anchors --------------------------------------------------------------------------------------------------
    for site_id, fault, hours, priority in ANCHOR_HVAC_OPEN:
        hvac_fault(log, site_id, PERIOD_END - timedelta(hours=hours, minutes=rng.randint(3, 50)), fault, priority=priority, keep_open=True)
    for site_id, *_ in ANCHOR_HVAC_OPEN:  # a few cleared faults at the anchor sites so they are not otherwise silent
        hvac_fault(log, site_id, PERIOD_START + timedelta(days=rng.randint(1, 8), hours=rng.uniform(0, 24)), rng.choice(HVAC_FAULTS), clear_after_h=rng.uniform(2, 20))
    # HBL-SYD-008: the chiller trips twice on 13 November. The first trip was reset; the second is the open P1 above (58 h).
    site_id, first = ANCHOR_DOUBLE_TRIP
    hvac_fault(log, site_id, first, "chiller_trip", priority="P2", clear_after_h=1.5)
    for site_id, kind, when in ANCHOR_WLG_LIFTS:
        lift_incident(log, site_id, when, kind)

    log.finalise()
    return log


def build_inspections(rng: random.Random, sites: list[dict]) -> list[dict]:
    as_of = PERIOD_END.date()
    rows: list[dict] = []

    def status(due: date) -> str:
        if due < as_of:
            return "expired"
        if due <= as_of + timedelta(days=30):
            return "expiring"
        return "current"

    for idx, s in enumerate(sites):
        sid = s["site_id"]
        test_day = (idx % 26) + 1
        next_test = date(2026, 11, test_day) if test_day > 15 else date(2026, 12, test_day)
        rows.append({"site_id": sid, "system": "fire", "kind": "monthly_test", "last_completed": (next_test - timedelta(days=30)).isoformat(),
                     "next_due": next_test.isoformat(), "certificate_status": "current", "inspector_firm": s["contractor_fire"]})
        if sid in ANCHOR_FIRE_CERT_DUE:
            due = ANCHOR_FIRE_CERT_DUE[sid]
        elif sid in OVERDUE_CERT_SITES:
            due = as_of - timedelta(days=rng.randint(4, 21))
        else:
            due = as_of + timedelta(days=rng.randint(31, 360))
            if rng.random() < 0.08:  # a handful of other sites are due this month too
                due = date(2026, 11, rng.randint(16, 30))
        rows.append({"site_id": sid, "system": "fire", "kind": "annual_certificate", "last_completed": (due - timedelta(days=365)).isoformat(),
                     "next_due": due.isoformat(), "certificate_status": status(due), "inspector_firm": rng.choice(FIRE_INSPECTORS)})
        if s["fire_system"] == "sprinkler_and_detection":
            due5 = as_of + timedelta(days=rng.randint(40, 1700))
            rows.append({"site_id": sid, "system": "fire", "kind": "five_yearly_sprinkler_test", "last_completed": (due5 - timedelta(days=5 * 365)).isoformat(),
                         "next_due": due5.isoformat(), "certificate_status": status(due5), "inspector_firm": rng.choice(FIRE_INSPECTORS)})
        if s["lifts"]:
            due = as_of + timedelta(days=rng.randint(10, 360))
            rows.append({"site_id": sid, "system": "lift", "kind": "annual_certificate", "last_completed": (due - timedelta(days=365)).isoformat(),
                         "next_due": due.isoformat(), "certificate_status": status(due), "inspector_firm": s["contractor_lift"]})
    rows.sort(key=lambda r: (r["next_due"], r["site_id"], r["kind"]))
    return rows


def write_knowledge_docs() -> list[Path]:
    paths: list[Path] = []
    for filename, text in KNOWLEDGE_DOCS.items():
        path = DATA_DIR / "knowledge" / filename
        path.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def check_anchors(log: EventLog, inspections: list[dict]) -> dict:
    """The numbers docs/EXPECTED.md and tests/test_data.py rely on; raises if the data drifted."""
    def age(w: dict) -> timedelta:
        return PERIOD_END - datetime.strptime(w["opened_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    open_hvac_48 = [w for w in log.work_orders if w["system"] == "hvac" and w["status"] == "open" and age(w) > timedelta(hours=48)]
    assert sorted(w["site_id"] for w in open_hvac_48) == sorted(s for s, *_ in ANCHOR_HVAC_OPEN), sorted(w["site_id"] for w in open_hvac_48)
    assert sum(w["priority"] == "P1" for w in open_hvac_48) == 1
    wlg_lifts = [e for e in log.events if e["region"] == "WLG" and e["event_type"] == "lift_incident" and e["ts"] >= ts(LAST_7_START)]
    assert len(wlg_lifts) == 5 and len({e["site_id"] for e in wlg_lifts}) == 3 and sum(e["detail"].startswith("entrapment") for e in wlg_lifts) == 1
    assert not [e for e in log.events if e["event_type"] == "fire_alarm" and e["severity"] == "critical" and e["ts"] >= ts(LAST_7_START)]
    trips = [e for e in log.events if e["site_id"] == "HBL-SYD-008" and e["event_type"] == "hvac_fault" and e["detail"].startswith("chiller_trip") and e["ts"].startswith("2026-11-13")]
    assert len(trips) == 2, trips
    due_nov = {r["site_id"] for r in inspections if r["kind"] == "annual_certificate" and r["system"] == "fire" and r["next_due"].startswith("2026-11")}
    assert {w["site_id"] for w in open_hvac_48} & due_nov == {"HBL-AKL-017", "HBL-WLG-011", "HBL-SYD-008"}
    akl017 = next(r for r in inspections if r["site_id"] == "HBL-AKL-017" and r["kind"] == "annual_certificate" and r["system"] == "fire")
    assert akl017["next_due"] == "2026-11-24" and akl017["certificate_status"] == "expiring"
    return {
        "hvac_open_over_48h": sorted(w["site_id"] for w in open_hvac_48),
        "wlg_lift_incidents_7d": len(wlg_lifts),
        "fire_certificates_due_2026_11": sorted(due_nov),
        "overdue_fire_certificates": sorted(r["site_id"] for r in inspections if r["kind"] == "annual_certificate" and r["system"] == "fire" and r["certificate_status"] == "expired"),
    }


def main() -> None:
    rng = random.Random(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "knowledge").mkdir(exist_ok=True)

    sites = build_sites(rng)
    assets = build_assets(rng, sites)
    log = build_events(rng, sites, assets)
    inspections = build_inspections(rng, sites)
    anchors = check_anchors(log, inspections)

    (DATA_DIR / "sites.json").write_text(json.dumps(sites, indent=2) + "\n", encoding="utf-8", newline="\n")
    (DATA_DIR / "assets.json").write_text(json.dumps(assets, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (DATA_DIR / "site_events.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for e in log.events:
            fh.write(json.dumps(e) + "\n")
    with (DATA_DIR / "work_orders.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for wo in log.work_orders:
            fh.write(json.dumps(wo) + "\n")
    (DATA_DIR / "inspections.json").write_text(json.dumps(inspections, indent=2) + "\n", encoding="utf-8", newline="\n")
    docs = write_knowledge_docs()

    print(f"sites.json          {len(sites)} sites")
    print(f"assets.json         {len(assets)} assets")
    print(f"site_events.jsonl   {len(log.events)} events ({log.events[0]['ts']} .. {log.events[-1]['ts']})")
    print(f"work_orders.jsonl   {len(log.work_orders)} work orders ({sum(w['status'] == 'open' for w in log.work_orders)} open)")
    print(f"inspections.json    {len(inspections)} inspection records")
    print(f"knowledge/          {len(docs)} documents")
    for doc in docs:
        print(f"  {doc.name:48s} {len(doc.read_text(encoding='utf-8').split()):4d} words")
    print("anchors             " + json.dumps(anchors))


if __name__ == "__main__":
    main()
