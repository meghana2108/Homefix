"""Turn one eval run into results/summary_<profile>.md: numbers only, no questions or answers,
so it can be committed (hard rule 1).

    uv run python -m eval.report --run 20261119-1130-lite-all
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.settings import ROOT
from eval.types import GradeResult, RunRecord

RESULTS = ROOT / "results"
ORDER = ("image", "audio", "text", "code", "video")
# p50 targets from the design spec (Constraints > Latency targets).
TARGETS = {
    "full": {"image": "≤ 8 s", "audio": "sound ≤ 3 s, speech ≤ 8 s", "text": "≤ 12 s", "code": "≤ 20 s",
             "video": "≤ 25 s"},
    "lite": {"image": "≤ 15 s", "audio": "sound ≤ 4 s, speech ≤ 15 s", "text": "≤ 20 s",
             "code": "≤ 35 s (incl. swap)", "video": "≤ 40 s"},
}


def _p50(xs: list[int]) -> float:
    return statistics.median(xs) / 1000


def _p95(xs: list[int]) -> float:
    s = sorted(xs)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)] / 1000  # nearest rank


def _modalities(present) -> list[str]:
    return [m for m in ORDER if m in present] + sorted(set(present) - set(ORDER))


def summarize(graded: list[GradeResult], records: list[RunRecord], run_id: str | None = None,
              meta: dict | None = None) -> str:
    meta = meta or {}
    profile = meta.get("profile") or (records[0].profile if records else "?")
    by_mod: dict[str, list[RunRecord]] = defaultdict(list)
    for r in records:
        by_mod[r.modality].append(r)
    mod_of = {r.item_id: r.modality for r in records}
    rec_of = {r.item_id: r for r in records}

    lines = [f"# HomeFix eval summary: {profile}", ""]
    head = f"Run `{run_id}` · " if run_id else ""
    lines.append(f"{head}{len(records)} items · written {datetime.now():%Y-%m-%d %H:%M}. "
                 "Numbers only: no questions or answers (hard rule 1).")
    if meta.get("brain"):
        sets = ", ".join(f"`{s}`" for s in meta.get("sets") or []) or "none"
        lines.append(f"Brain `{meta['brain']}`, coder `{meta.get('coder', '?')}`; overrides: {sets}.")
    lines += ["", "## Accuracy", ""]

    if not graded:
        lines += ["Accuracy: not graded (no reference answers, or `--no-grade`).", ""]
    else:
        g_by_mod: dict[str, list[GradeResult]] = defaultdict(list)
        for g in graded:
            g_by_mod[mod_of.get(g.item_id, "?")].append(g)
        for m in _modalities(g_by_mod):
            gs = g_by_mod[m]
            lines += [f"### {m}", "", "| metric | hits/total | score |", "|---|---|---|"]
            by_metric: dict[str, list[GradeResult]] = defaultdict(list)
            for g in gs:
                by_metric[g.metric].append(g)
            for metric, rows in by_metric.items():
                score = statistics.fmean(g.score for g in rows)
                lines.append(f"| {metric} | {sum(g.hit for g in rows)}/{len(rows)} | {score:.2f} |")
                if metric == "top1":
                    top3 = sum("top3_hit=true" in g.note for g in rows)
                    lines.append(f"| top3 | {top3}/{len(rows)} | – |")
            if m == "text" and {"refusal", "answer_match"} & set(by_metric):
                unans = {g.item_id for g in gs if g.metric == "refusal"}
                refused = {g.item_id for g in gs if rec_of.get(g.item_id) and
                           rec_of[g.item_id].refusal_reason == "not_in_document"}
                both = len(unans & refused)
                p = f"{both}/{len(refused)}" + (f" ({both / len(refused):.2f})" if refused else "")
                rc = f"{both}/{len(unans)}" + (f" ({both / len(unans):.2f})" if unans else "")
                lines += ["", f"Refusal precision {p}, recall {rc} (positive = refused as not in the document)."]
            if "wer" in by_metric:
                lines += ["", "WER score is the mean word error rate (lower is better; hit at ≤ 0.15)."]
            lines.append("")

    lines += ["## Latency and memory", "", "| modality | items | p50 | p95 | Target p50 |", "|---|---|---|---|---|"]
    targets = TARGETS.get(profile, {})
    for m in _modalities(by_mod):
        lat = [r.latency_ms for r in by_mod[m]]
        lines.append(f"| {m} | {len(lat)} | {_p50(lat):.1f} s | {_p95(lat):.1f} s | {targets.get(m, '–')} |")
    refusals: dict[str, int] = defaultdict(int)
    for r in records:
        if r.refusal_reason:
            refusals[r.refusal_reason] += 1
    peak = max((r.peak_mem_gb for r in records), default=0.0)
    lines += ["", ("Latency is wall time from request to final, and includes loading each model the first "
                   "time it is used in the run."),
              f"Peak memory: {peak:.1f} GB (Ollama's loaded models + the eval process)."]
    if refusals:
        lines.append("Refusals and errors: " + ", ".join(f"{k} {v}" for k, v in sorted(refusals.items())) + ".")
    lines += ["", "Re-run: `uv run python -m eval.run --profile " + profile + " --modality all` then "
              "`uv run python -m eval.report --run <run_id>`.", ""]
    return "\n".join(lines)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(prog="python -m eval.report")
    ap.add_argument("--run", required=True, help="run id printed by eval.run")
    ap.add_argument("--out", default=None, help="default: results/summary_<profile>.md")
    a = ap.parse_args(argv)
    raw = RESULTS / "raw"
    rec_file = raw / f"{a.run}.jsonl"
    if not rec_file.is_file():
        raise SystemExit(f"No run {a.run} in {raw}")
    records = [RunRecord(**d) for d in _read_jsonl(rec_file)]
    graded_file = raw / f"{a.run}_graded.jsonl"
    graded = [GradeResult(**d) for d in _read_jsonl(graded_file)] if graded_file.is_file() else []
    meta_file = raw / f"{a.run}_meta.json"
    meta = json.loads(meta_file.read_text()) if meta_file.is_file() else {}
    md = summarize(graded, records, run_id=a.run, meta=meta)
    profile = meta.get("profile") or (records[0].profile if records else "unknown")
    out = Path(a.out) if a.out else RESULTS / f"summary_{profile}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
