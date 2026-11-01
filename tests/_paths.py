"""Make the shared demo modules importable from the tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "demos" / "00-shared"
for p in (SHARED, ROOT / "demos" / "03-grounded-foundry-agent", ROOT / "demos" / "04-trace-and-evaluate"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
