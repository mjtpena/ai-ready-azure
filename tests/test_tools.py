"""Contracts of the four Site API tools: shapes, needs_attention first, errors instead of exceptions."""

from __future__ import annotations

import json

import _paths  # noqa: F401
import site_tools as t


def test_schemas_match_functions():
    assert [s["name"] for s in t.TOOL_SCHEMAS] == list(t.TOOL_FUNCTIONS)
    for s in t.TOOL_SCHEMAS:
        assert s["parameters"]["additionalProperties"] is False
        assert set(s["parameters"]["required"]) == set(s["parameters"]["properties"])


def test_needs_attention_first_and_serialisable():
    outputs = [
        t.get_site_summary("HBL-AKL-017"),
        t.get_open_work_orders("AKL", "any", 0),
        t.get_incidents("ALL", "any", 14),
        t.get_inspection_schedule("SYD", "all", "2026-12"),
    ]
    for out in outputs:
        assert "needs_attention" in out, out.keys()
        json.dumps(out)


def test_unknown_ids_return_errors():
    assert "error" in t.get_site_summary("HBL-XXX-999")
    assert "error" in t.get_open_work_orders("PAR", "hvac", 0)
    assert "error" in t.get_open_work_orders("ALL", "plumbing", 0)
    assert "error" in t.get_incidents("ALL", "any", "soon")
    assert "error" in t.get_inspection_schedule("ALL", "hvac", "2026-11")
    assert "error" in t.get_inspection_schedule("ALL", "fire", "November")
    assert "error" in t.call_tool("get_weather", {})


def test_call_tool_accepts_json_strings():
    out = t.call_tool("get_open_work_orders", json.dumps({"region": "all", "system": "HVAC", "open_longer_than_hours": "48"}))
    assert out["needs_attention"]["count"] == 6


def test_days_are_clamped():
    assert t.get_incidents("ALL", "any", 99)["window"]["days"] == 14
    assert t.get_incidents("ALL", "any", 0)["window"]["days"] == 1


def test_monthly_tests_are_not_certificate_inspections():
    out = t.get_inspection_schedule("ALL", "fire", "2026-11")
    assert all(r["kind"] != "monthly_test" for r in out["due"])
    assert all(r["kind"] == "monthly_test" for r in out["monthly_tests_due"])
