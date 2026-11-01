"""Prove that no customer, sponsor or private identifier survives anywhere in this repository.

    python scripts/scrub_check.py            # text files tracked by git plus the untracked working tree
    python scripts/scrub_check.py --all      # also: .pptx XML, OCR over PNG/JPG and sampled MP4 frames (needs rapidocr)
    python scripts/scrub_check.py --paths video/casts video/media

Exit code 1 on any hit. Two kinds of check: a banned-word list, and shapes that mean a live identifier leaked (GUIDs
that match the signed-in tenant or subscription, e-mail addresses). The banned list is private, so it is not in the
repository: it is read from `scripts/forbidden.json` when that file exists, else from the SCRUB_FORBIDDEN environment
variable (the same JSON; CI sets it from a repository secret), and without either only the shape checks run. Live
identifiers are read from `az account show` at run time and never written anywhere.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def banned_lists() -> dict[str, list[str]]:
    """The private banned-word list: scripts/forbidden.json, else $SCRUB_FORBIDDEN, else empty (shape checks only)."""
    local = Path(__file__).resolve().parent / "forbidden.json"
    if local.exists():
        raw = json.loads(local.read_text(encoding="utf-8"))
    elif os.environ.get("SCRUB_FORBIDDEN", "").strip():
        raw = json.loads(os.environ["SCRUB_FORBIDDEN"])
    else:
        raw = {}
    return {"words": list(raw.get("words", [])), "domain_words": list(raw.get("domain_words", []))}


_LISTS = banned_lists()
BANNED: list[str] = _LISTS["words"]
# Words that are fine in general English but mark off-scenario material when they appear in demo data or captions
DOMAIN_WORDS: list[str] = _LISTS["domain_words"]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".txt", ".xml", ".kql", ".bicep", ".sh", ".ps1", ".js", ".css", ".yaml", ".yml",
                 ".vtt", ".srt", ".ffmeta", ".ffconcat", ".toml", ".cfg", ".ini", ".example", ".gitignore", ".gitattributes"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "pw-profile"}
ALLOW_EMAILS = {"noreply@anthropic.com", "platform.engineer@harbourline.example"}


def live_identifiers() -> dict[str, str]:
    """Tenant, subscription and user from the signed-in az session (values live in memory only)."""
    try:
        out = subprocess.run(["az", "account", "show", "-o", "json"], capture_output=True, text=True, shell=True, timeout=30)
        acc = json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {}
    except Exception:  # noqa: BLE001
        return {}
    found = {}
    for key, label in (("tenantId", "tenant id"), ("id", "subscription id")):
        if acc.get(key):
            found[acc[key].lower()] = label
    user = (acc.get("user") or {}).get("name")
    if user:
        found[user.lower()] = "signed-in user"
    return found


def norm(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", text.lower())


def scan_text(text: str, where: str, live: dict[str, str], strict_domain: bool) -> list[str]:
    hits: list[str] = []
    low, squashed = text.lower(), norm(text)
    for word in BANNED:
        if word in low or norm(word) in squashed:
            hits.append(f"{where}: banned word '{word}'")
    if strict_domain:
        for word in DOMAIN_WORDS:
            if word in low:
                hits.append(f"{where}: domain word '{word}'")
    for value, label in live.items():
        if value in low:
            hits.append(f"{where}: live {label}")
    for m in EMAIL.findall(text):
        if m.lower() not in ALLOW_EMAILS and not m.lower().endswith((".example", "example.com")):
            hits.append(f"{where}: e-mail address {m}")
    return hits


def iter_files(paths: list[Path]):
    for base in paths:
        if base.is_file():
            yield base
            continue
        for p in base.rglob("*"):
            if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
                continue
            if p.is_file():
                yield p


def check_pptx(path: Path, live: dict[str, str]) -> list[str]:
    hits: list[str] = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith((".xml", ".rels")):
                hits += scan_text(z.read(name).decode("utf-8", "replace"), f"{path.relative_to(ROOT)}!{name}", live, True)
            elif "media/" in name:
                hits += scan_text(name, f"{path.relative_to(ROOT)}!{name}", live, False)
    return hits


def ocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        engine = RapidOCR()

        def run(img_path: Path) -> str:
            result, _ = engine(str(img_path))
            return " ".join(r[1] for r in (result or []))

        return run
    except ImportError:
        return None


def check_image(path: Path, ocr, live: dict[str, str]) -> list[str]:
    text = ocr(path)
    return scan_text(text, f"{path.relative_to(ROOT)} (OCR)", live, True)


def check_video(path: Path, ocr, live: dict[str, str], every_s: float, tmp: Path) -> list[str]:
    tmp.mkdir(parents=True, exist_ok=True)
    for old in tmp.glob("*.png"):
        old.unlink()
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps=1/{every_s}", str(tmp / "f%05d.png")], check=True)
    hits: list[str] = []
    for frame in sorted(tmp.glob("*.png")):
        for h in check_image(frame, ocr, live):
            hits.append(h.replace(str(frame.relative_to(ROOT)), f"{path.relative_to(ROOT)} frame {frame.stem}"))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="also scan .pptx XML, images (OCR) and video frames (OCR)")
    ap.add_argument("--paths", nargs="*", type=Path, help="limit the scan to these paths (default: the whole tree)")
    ap.add_argument("--every", type=float, default=2.0, help="seconds between sampled video frames (default 2)")
    ap.add_argument("--no-live", action="store_true", help="do not read live identifiers from az")
    args = ap.parse_args()
    live = {} if args.no_live else live_identifiers()
    paths = [ROOT / p if not p.is_absolute() else p for p in (args.paths or [ROOT])]
    hits: list[str] = []
    ocr = ocr_engine() if args.all else None
    if args.all and ocr is None:
        print("OCR engine missing: pip install rapidocr-onnxruntime", file=sys.stderr)
        return 1
    scanned = 0
    for p in iter_files(paths):
        rel = p.relative_to(ROOT).as_posix()
        if p.name in ("scrub_check.py", "forbidden.json"):
            continue
        strict = rel.startswith(("demos/", "video/", "narration/", "slides/src", "docs/"))
        if p.suffix.lower() in TEXT_SUFFIXES or p.name in (".env.example",):
            hits += scan_text(p.read_text(encoding="utf-8", errors="replace"), rel, live, strict)
            scanned += 1
        elif args.all and p.suffix.lower() == ".pptx":
            hits += check_pptx(p, live)
            scanned += 1
        elif args.all and p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            hits += check_image(p, ocr, live)
            scanned += 1
        elif args.all and p.suffix.lower() in {".mp4", ".webm"}:
            hits += check_video(p, ocr, live, args.every, ROOT / ".video-tmp" / "scrub")
            scanned += 1
    tracked_env = subprocess.run(["git", "ls-files", "--", "**/.env", "**/.deploy-outputs.json"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    if tracked_env:
        hits.append(f"tracked secrets file(s): {tracked_env}")
    for h in hits:
        print("HIT", h)
    words = f"{len(BANNED)} banned words" if BANNED else "no banned-word list, shape checks only"
    print(f"scanned {scanned} files ({words}), {len(hits)} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
