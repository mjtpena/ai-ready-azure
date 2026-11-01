"""Small terminal presentation helpers shared by the demos (colour, spinner, typewriter, bars).

Everything degrades to plain text automatically when stdout is not a terminal (captures, CI, ``> file``),
when ``NO_COLOR`` is set, or when ``DEMO_PLAIN=1``. The ``slides/src/shots.js`` colouriser works on the plain
text, so captured output stays byte-for-byte what it was before these helpers existed.

Palette mirrors the slide theme: amber for emphasis, teal for the user, violet for the agent, green for
success, red for failures, dim grey for metadata.
"""

from __future__ import annotations

import os
import sys
import threading
from types import SimpleNamespace
import time
from contextlib import contextmanager
from typing import Iterator

_CODES = {
    "reset": "0",
    "bold": "1",
    "dim": "2",
    "italic": "3",
    "amber": "38;2;245;166;35",
    "teal": "38;2;18;165;160",
    "violet": "38;2;124;92;255",
    "green": "38;2;61;190;107",
    "red": "38;2;214;69;69",
    "grey": "38;2;138;148;160",
    "white": "97",
}


def enabled(stream=None) -> bool:
    """True when styling should be emitted (interactive terminal, not opted out)."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("DEMO_PLAIN", "").lower() in {"1", "true", "yes"}:
        return False
    if os.environ.get("DEMO_FORCE_TTY", "").lower() in {"1", "true", "yes"}:  # slides/video/record.py captures styled output
        return True
    return bool(getattr(stream, "isatty", lambda: False)())


def c(text: object, *styles: str) -> str:
    """Wrap ``text`` in ANSI styles (names from the palette). No-op when styling is disabled."""
    if not enabled() or not styles:
        return str(text)
    codes = ";".join(_CODES[s] for s in styles)
    return f"\033[{codes}m{text}\033[0m"


def bar(value: float, total: float, width: int = 24, fill: str = "█", empty: str = "░") -> str:
    """A fixed-width progress bar: ``bar(128, 500)`` -> ``██████░░░░░░░░░░░░░░░░░░``."""
    if total <= 0:
        return empty * width
    filled = max(0, min(width, round(width * value / total)))
    return fill * filled + empty * (width - filled)


def coloured_bar(value: float, total: float, width: int = 24) -> str:
    """Bar whose colour follows how much is left: green above 50%, amber above 20%, red below."""
    ratio = value / total if total else 0
    tone = "green" if ratio > 0.5 else "amber" if ratio > 0.2 else "red"
    return c(bar(value, total, width), tone)


def typewriter(text: str, cps: float = 240.0, stream=None) -> None:
    """Print ``text`` with a typing effect (characters per second). Instant when styling is disabled or
    ``DEMO_TYPEWRITER=0``. Pauses briefly at line ends so paragraphs land as units."""
    stream = stream or sys.stdout
    if not enabled(stream) or os.environ.get("DEMO_TYPEWRITER", "1") in {"0", "false", "no"} or cps <= 0:
        stream.write(text + "\n")
        stream.flush()
        return
    delay = 1.0 / cps
    for line in text.split("\n"):
        for ch in line:
            stream.write(ch)
            stream.flush()
            time.sleep(delay)
        stream.write("\n")
        stream.flush()
        time.sleep(delay * 12)


@contextmanager
def spinner(label: str, stream=None) -> Iterator[SimpleNamespace]:
    """Animated one-line status with an elapsed-time counter while a slow call runs.

    ``with spinner("the advisor is thinking"): result = call()``
    The context value's ``label`` can be changed while it spins (progress of a long job).
    Prints nothing when styling is disabled (so captured output is unchanged)."""
    stream = stream or sys.stdout
    status = SimpleNamespace(label=label)
    if not enabled(stream):
        yield status
        return
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    stop = threading.Event()
    started = time.perf_counter()

    def spin() -> None:
        i, widest = 0, 0
        while not stop.is_set():
            elapsed = time.perf_counter() - started
            text = status.label
            pad = " " * max(0, widest - len(text))
            widest = max(widest, len(text))
            stream.write(f"\r{c(frames[i % len(frames)], 'amber')} {c(text, 'dim')} {c(f'{elapsed:4.1f}s', 'grey')}{pad}")
            stream.flush()
            i += 1
            time.sleep(0.08)
        stream.write("\r" + " " * (widest + 14) + "\r")
        stream.flush()

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    try:
        yield status
    finally:
        stop.set()
        thread.join()


def banner(title: str, subtitle: str = "") -> None:
    """A two-line amber banner for the start of a demo act."""
    print(c("▶ " + title, "amber", "bold") + (("  " + c(subtitle, "grey")) if subtitle else ""))


def status_line(code: int, text: str) -> str:
    """``HTTP    : 200`` in green, 4xx in red, keeping the exact plain text."""
    tone = "green" if 200 <= code < 300 else "red" if code >= 400 else "amber"
    return c(text, tone, "bold")
