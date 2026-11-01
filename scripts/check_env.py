"""Pre-flight for the course environment: signed-in subscription, resource providers, quota headroom and tooling.

    python scripts/check_env.py [--location australiaeast]

Prints one line per check and exits 1 when something the deployment needs is missing.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

MODELS = {"gpt-5-mini": 50, "gpt-5": 250, "text-embedding-3-small": 50}  # K TPM each deployment asks for
PROVIDERS = ("Microsoft.CognitiveServices", "Microsoft.ApiManagement", "Microsoft.Search", "Microsoft.ContainerInstance",
             "Microsoft.OperationalInsights", "Microsoft.Insights", "Microsoft.Web")


def az(*args: str):
    out = subprocess.run(["az", *args, "-o", "json"], capture_output=True, text=True, shell=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout) if out.stdout.strip() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--location", default="australiaeast")
    args = ap.parse_args()
    ok = True

    def line(good: bool, text: str) -> None:
        nonlocal ok
        ok = ok and good
        print(("PASS " if good else "FAIL ") + text)

    for tool in ("az", "ffmpeg", "ffprobe", "node", "npm"):
        line(shutil.which(tool) is not None, f"{tool} on PATH")
    acc = az("account", "show")
    line(bool(acc), f"signed in: {acc['name'] if acc else 'no (az login)'}")
    if not acc:
        return 1
    for rp in PROVIDERS:
        state = (az("provider", "show", "-n", rp) or {}).get("registrationState")
        line(state == "Registered", f"provider {rp}: {state}")
    usage = az("cognitiveservices", "usage", "list", "-l", args.location) or []
    for model, need in MODELS.items():
        rows = [u for u in usage if model in (u.get("name", {}).get("value") or "") and "GlobalStandard" in (u.get("name", {}).get("value") or "")]
        if not rows:
            line(False, f"quota {model} GlobalStandard in {args.location}: no usage row (model not offered here?)")
            continue
        u = rows[0]
        free = (u.get("limit") or 0) - (u.get("currentValue") or 0)
        line(free >= need, f"quota {model}: {free:.0f}K TPM free of {u.get('limit', 0):.0f}K, deployment asks {need}K")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
