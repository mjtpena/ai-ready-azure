"""The synthetic data is deterministic and carries the anchors every demo relies on (docs/EXPECTED.md)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import _paths  # noqa: F401

DATA = _paths.SHARED / "data"
FILES = ("sites.json", "assets.json", "site_events.jsonl", "work_orders.jsonl", "inspections.json")


def _digest() -> dict[str, str]:
    return {f: hashlib.sha256((DATA / f).read_bytes()).hexdigest() for f in FILES}


def test_generator_is_deterministic():
    before = _digest()
    subprocess.run([sys.executable, str(_paths.SHARED / "generate_data.py")], check=True, capture_output=True, cwd=_paths.SHARED)
    assert _digest() == before, "generate_data.py changed the data on a re-run"


def test_counts():
    sites = json.loads((DATA / "sites.json").read_text(encoding="utf-8"))
    assert len(sites) == 120
    assert {s["region"] for s in sites} == {"AKL", "WLG", "SYD", "MEL"}
    assert sum(s["region"] == "AKL" for s in sites) == 40
    docs = sorted(p.name for p in (DATA / "knowledge").glob("*.md"))
    assert len(docs) == 8


def test_anchors():
    import site_tools as t

    hvac = t.get_open_work_orders("ALL", "hvac", 48)
    assert hvac["needs_attention"]["sites"] == ["HBL-AKL-017", "HBL-AKL-033", "HBL-MEL-006", "HBL-SYD-008", "HBL-SYD-021", "HBL-WLG-011"]
    assert hvac["needs_attention"]["p1_count"] == 1 and hvac["needs_attention"]["count"] == 6
    fire = t.get_inspection_schedule("ALL", "fire", "2026-11")
    both = set(hvac["needs_attention"]["sites"]) & set(fire["needs_attention"]["sites_due"])
    assert both == {"HBL-AKL-017", "HBL-WLG-011", "HBL-SYD-008"}
    akl = t.get_inspection_schedule("HBL-AKL-017", "fire", "2026-11")
    assert akl["due"][0]["next_due"] == "2026-11-24" and akl["due"][0]["certificate_status"] == "expiring"
    wlg = t.get_incidents("WLG", "lift", 7)
    assert wlg["count"] == 5 and len(wlg["by_site"]) == 3 and wlg["needs_attention"]["entrapments"] == 1
    assert wlg["needs_attention"]["genuine_fire_alarms"] == 0
    syd = t.get_site_summary("HBL-SYD-008")
    assert syd["needs_attention"]["open_p1_work_orders"] == 1 and syd["needs_attention"]["hvac_faults_open_over_48h"] == 1
    trips = [e for e in t.load_events() if e["site_id"] == "HBL-SYD-008" and e["event_type"] == "hvac_fault" and e["detail"].startswith("chiller_trip") and e["ts"].startswith("2026-11-13")]
    assert len(trips) == 2


def test_no_customer_strings_in_data():
    sys.path.insert(0, str(_paths.ROOT / "scripts"))
    from scrub_check import banned_lists  # the private list when present (local file or CI secret)

    banned = (*banned_lists()["words"], "fleet", "vehicle", "ruc ")
    for f in (*FILES, *(f"knowledge/{p.name}" for p in (DATA / "knowledge").glob("*.md"))):
        text = (DATA / f).read_text(encoding="utf-8").lower()
        hits = [b for b in banned if b in text]
        assert not hits, (f, hits)
