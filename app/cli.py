"""Run one request from the terminal through the same handle() the API and eval use.

    uv run python -m app.cli "how many mugs?" --file mugs.jpg [--manual ID] [--profile lite] [--json]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.contracts import Event
from app.orchestrate import build_ctx, handle


def _line(ev: Event) -> str:
    t = ev.type
    if t == "status":
        extra = f" · {ev.detail}" if ev.detail else ""
        extra += f" · {ev.ms / 1000:.1f} s" if ev.ms is not None else ""
        return f"[status] {ev.stage}{extra}"
    if t == "transcript":
        return f"[transcript] ({ev.seconds:.1f} s) {ev.text}"
    if t == "sound_labels":
        return "[sound_labels] " + ", ".join(f"{s.label} {s.score:.0%}" for s in ev.labels)
    if t == "frames":
        ts = ev.timestamps
        return f"[frames] {len(ts)} frames" + (f", t={ts[0]:.1f}s to t={ts[-1]:.1f}s" if ts else "")
    if t == "citation":
        where = f"p. {ev.page} · {ev.source}" if ev.page is not None else ev.source
        return f'[citation] {where}: "{ev.quote}"'
    if t == "code_result":
        badge = f"passed {ev.tests_run - ev.failures}/{ev.tests_run}" if ev.passed else \
            f"failed {ev.failures}/{ev.tests_run}"
        return f"[code_result] {badge} (attempt {ev.attempts})\n{ev.code}\n{ev.output_tail}"
    if t == "refusal":
        return f"[refusal] {ev.reason}" + (f" ({ev.category})" if ev.category else "") + f": {ev.message}"
    if t == "error":
        return f"[error] {ev.stage}: {ev.message}"
    if t == "final":
        return f"[final] {ev.answer} ({ev.latency_ms / 1000:.1f} s, {ev.modality}/{ev.question_type})"
    return f"[{t}]"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli", description="Ask HomeFix from the terminal.")
    ap.add_argument("message", help='the question (use "" for none)')
    ap.add_argument("--file", action="append", default=[], help="attach a file (repeatable, up to 4)")
    ap.add_argument("--manual", default=None, help="manual id (file stem in data/manuals/)")
    ap.add_argument("--profile", choices=["full", "lite"], default=None, help="default: PROFILE from .env")
    ap.add_argument("--json", action="store_true", help="print one JSON event per line")
    a = ap.parse_args(argv)

    files = [Path(f) for f in a.file]
    for f in files:
        if not f.is_file():
            print(f"File not found: {f}", file=sys.stderr)
            return 2

    ctx = build_ctx(a.profile)
    streaming = False
    for ev in handle(a.message, files, a.manual, ctx):
        if a.json:
            print(ev.model_dump_json(), flush=True)
            continue
        if ev.type == "token":
            if not streaming:
                sys.stdout.write("[token] ")
                streaming = True
            sys.stdout.write(ev.text)
            sys.stdout.flush()
            continue
        if streaming:
            sys.stdout.write("\n")
            streaming = False
        print(_line(ev), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
