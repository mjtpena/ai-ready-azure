"""Make ``demos/00-shared`` importable from this demo folder (``import _shared`` first in each script)."""

import sys
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[1] / "00-shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

# Windows consoles default to a legacy code page; model answers contain non-ASCII punctuation (verified 16 Oct 2026:
# UnicodeEncodeError on a non-breaking hyphen). Force UTF-8 so the demos print the same everywhere.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
