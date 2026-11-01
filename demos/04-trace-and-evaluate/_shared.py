"""Make ``demos/00-shared`` and ``demos/03-grounded-foundry-agent`` importable (``import _shared`` first)."""

import sys
from pathlib import Path

DEMOS = Path(__file__).resolve().parents[1]
for folder in (DEMOS / "00-shared", DEMOS / "03-grounded-foundry-agent"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

# Windows consoles default to a legacy code page; model answers contain non-ASCII punctuation (verified 16 Oct 2026:
# UnicodeEncodeError on a non-breaking hyphen). Force UTF-8 so the demos print the same everywhere.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
