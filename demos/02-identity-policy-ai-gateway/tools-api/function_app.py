"""The Site APIs as an HTTP backend: the four tools from demos/00-shared/site_tools.py behind Azure Functions.

API Management fronts this app (REST API ``site-ops-api``) and exports the same four operations as the MCP server
``hbl-site-tools``, so an agent reaches the tools through the gateway's identity, budget and logs. ``deploy.sh``
copies ``site_tools.py`` and ``data/`` into ``shared/`` before zip-deploying this folder.

Routes (all GET; the function key is held by the gateway as a named value, never by a client):
  /api/health
  /api/sites/{site_id}/summary
  /api/work-orders?region=ALL&system=hvac&open_longer_than_hours=48
  /api/incidents?region=WLG&system=lift&days=7
  /api/inspections?scope=HBL-AKL-017&system=fire&month=2026-11
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import azure.functions as func

sys.path.insert(0, str(Path(__file__).resolve().parent / "shared"))
from site_tools import call_tool  # noqa: E402

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _json(payload: dict, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(payload), status_code=status, mimetype="application/json")


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return _json({"status": "ok", "tools": ["get_site_summary", "get_open_work_orders", "get_incidents", "get_inspection_schedule"]})


@app.route(route="sites/{site_id}/summary", methods=["GET"])
def site_summary(req: func.HttpRequest) -> func.HttpResponse:
    return _json(call_tool("get_site_summary", {"site_id": req.route_params.get("site_id", "")}))


@app.route(route="work-orders", methods=["GET"])
def work_orders(req: func.HttpRequest) -> func.HttpResponse:
    p = req.params
    return _json(call_tool("get_open_work_orders", {"region": p.get("region", "ALL"), "system": p.get("system", "any"),
                                                    "open_longer_than_hours": _int(p.get("open_longer_than_hours"), 0)}))


@app.route(route="incidents", methods=["GET"])
def incidents(req: func.HttpRequest) -> func.HttpResponse:
    p = req.params
    return _json(call_tool("get_incidents", {"region": p.get("region", "ALL"), "system": p.get("system", "any"), "days": _int(p.get("days"), 7)}))


@app.route(route="inspections", methods=["GET"])
def inspections(req: func.HttpRequest) -> func.HttpResponse:
    p = req.params
    return _json(call_tool("get_inspection_schedule", {"scope": p.get("scope", "ALL"), "system": p.get("system", "all"), "month": p.get("month", "2026-11")}))
