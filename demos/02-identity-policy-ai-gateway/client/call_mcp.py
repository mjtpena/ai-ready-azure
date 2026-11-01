#!/usr/bin/env python3
"""Call the Site API tools through the gateway's MCP server, with an Entra ID token and the team's subscription key.

    python client/call_mcp.py --list                                               # tools/list
    python client/call_mcp.py --call get_open_work_orders --region ALL --system hvac --hours 48
    python client/call_mcp.py --call get_inspection_schedule --scope HBL-AKL-017 --system fire --month 2026-11
    python client/call_mcp.py --repeat 40                                          # trip the per-caller request budget (429)

MCP over streamable HTTP: JSON-RPC POSTs to APIM_GATEWAY_URL/site-tools/mcp. The gateway validates the token, counts
the call against the caller's budget, meters it, and adds the backend credential itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "00-shared", ".env"))

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
_STYLED = (sys.stdout.isatty() or os.environ.get("DEMO_FORCE_TTY", "").lower() in {"1", "true"}) and not os.environ.get("NO_COLOR")
_TONES = {"green": "38;2;61;190;107", "red": "38;2;214;69;69", "amber": "38;2;245;166;35", "grey": "38;2;138;148;160", "teal": "38;2;18;165;160"}

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def tone(text: str, name: str, bold: bool = False) -> str:
    return f"\033[{'1;' if bold else ''}{_TONES[name]}m{text}\033[0m" if _STYLED else text


def log(msg: str = "") -> None:
    print(msg, flush=True)


class Mcp:
    def __init__(self, url: str, token: str, key: str | None, team: str):
        self.url, self.n = url, 0
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream", "x-team": team}
        if key:
            self.headers["api-key"] = key
        self.session_id: str | None = None

    def rpc(self, method: str, params: dict | None = None) -> tuple[int, dict | None, dict]:
        self.n += 1
        body = {"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}
        headers = dict(self.headers)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        r = requests.post(self.url, headers=headers, json=body, timeout=60)
        if r.headers.get("Mcp-Session-Id"):
            self.session_id = r.headers["Mcp-Session-Id"]
        payload = None
        text = r.text or ""
        if r.headers.get("content-type", "").startswith("text/event-stream"):
            for line in text.splitlines():
                if line.startswith("data:"):
                    try:
                        payload = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        pass
        elif text.strip():
            try:
                payload = r.json()
            except ValueError:
                payload = {"raw": text[:300]}
        return r.status_code, payload, dict(r.headers)

    def initialize(self) -> tuple[int, dict | None, dict]:
        status, payload, headers = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                           "clientInfo": {"name": "call_mcp.py", "version": "1.0"}})
        if status < 300:
            self.rpc("notifications/initialized")
        return status, payload, headers


def show_headers(headers: dict) -> None:
    for name in ("x-hbl-gateway", "x-remaining-calls", "retry-after", "apim-request-id"):
        for k, v in headers.items():
            if k.lower() == name:
                log(f"    {tone(k.lower(), 'grey')}: {v}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--call", metavar="TOOL")
    ap.add_argument("--region", default="ALL")
    ap.add_argument("--system", default="hvac")
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--scope", default="ALL")
    ap.add_argument("--month", default="2026-11")
    ap.add_argument("--site-id", default="HBL-SYD-008")
    ap.add_argument("--repeat", type=int, default=0, help="call tools/list this many times quickly to trip the request budget")
    ap.add_argument("--team", default="site-ops-team")
    args = ap.parse_args()

    url = os.environ.get("APIM_MCP_URL") or (os.environ.get("APIM_GATEWAY_URL", "").rstrip("/") + "/site-tools/mcp")
    if not url.startswith("http"):
        sys.exit("APIM_GATEWAY_URL or APIM_MCP_URL is not set (run deploy.sh)")
    from azure.identity import DefaultAzureCredential

    token = DefaultAzureCredential(exclude_interactive_browser_credential=True).get_token(COGNITIVE_SCOPE).token
    mcp = Mcp(url, token, os.environ.get("APIM_SUBSCRIPTION_KEY"), args.team)
    log(f"Target  : {url}")
    log("Token   : Entra ID access token acquired; the subscription key says which team, the token says who")
    status, payload, headers = mcp.initialize()
    log(tone(f"HTTP    : {status}  initialize", "green" if status < 300 else "red", bold=True))
    if status >= 300:
        log(f"Body    : {json.dumps(payload)[:300]}")
        return 1

    if args.list or not (args.call or args.repeat):
        status, payload, headers = mcp.rpc("tools/list")
        tools = (payload or {}).get("result", {}).get("tools", [])
        log(tone(f"HTTP    : {status}  tools/list -> {len(tools)} tools", "green" if status < 300 else "red", bold=True))
        show_headers(headers)
        for t in tools:
            log(f"    {tone(t['name'], 'teal')}  {t.get('description', '')[:90]}")

    if args.call:
        arguments = {
            "get_site_summary": {"site_id": args.site_id},
            "get_open_work_orders": {"region": args.region, "system": args.system, "open_longer_than_hours": args.hours},
            "get_incidents": {"region": args.region, "system": args.system, "days": args.days},
            "get_inspection_schedule": {"scope": args.scope, "system": args.system if args.system in ("fire", "lift", "all") else "fire", "month": args.month},
        }.get(args.call)
        if arguments is None:
            sys.exit(f"unknown tool {args.call}")
        status, payload, headers = mcp.rpc("tools/call", {"name": args.call, "arguments": arguments})
        log(tone(f"HTTP    : {status}  tools/call {args.call}({', '.join(str(v) for v in arguments.values())})", "green" if status < 300 else "red", bold=True))
        show_headers(headers)
        result = (payload or {}).get("result", {})
        content = result.get("content", [])
        text = next((c.get("text") for c in content if c.get("type") == "text"), None)
        try:
            data = json.loads(text) if text else result
        except (TypeError, ValueError):
            data = {"raw": text}
        na = data.get("needs_attention") if isinstance(data, dict) else None
        if na:
            log(f"Result  : needs_attention {json.dumps(na)}")
        if isinstance(data, dict) and "work_orders" in data:
            log(f"          count {data['needs_attention']['count']} work orders; sites {', '.join(data['needs_attention']['sites'])}")
        elif isinstance(data, dict) and "due" in data:
            log(f"          due {len(data['due'])}, overdue {len(data['overdue'])}")
        elif isinstance(data, dict) and "error" in data:
            log(f"          error {data['error']}")

    if args.repeat:
        throttled = 0
        for i in range(1, args.repeat + 1):
            status, payload, headers = mcp.rpc("tools/list")
            if status == 429:
                throttled += 1
                if throttled == 1:
                    log(tone(f"HTTP    : 429 Too Many Requests  <- the request budget for this caller is spent (call {i} of {args.repeat})", "red", bold=True))
                    show_headers(headers)
            elif i % 10 == 0:
                log(f"HTTP    : {status}  call {i}")
        log(f"Summary : {args.repeat - throttled} allowed, {throttled} throttled this minute")
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
