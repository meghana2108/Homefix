"""Run practice items through the real app flow (handle()) and write results/raw/<run_id>.jsonl.

    uv run python -m eval.run --profile lite --modality all
    uv run python -m eval.run --profile full --modality image --limit 2 --set models.brain=gemma4:e4b
    uv run python -m eval.report --run <run_id>          # then: results/summary_<profile>.md

The pack folder comes from --pack, else PRACTICE_PACK_DIR (.env). When the pack's reference
answers exist (and no --no-grade), eval/grade.py grades the run into <run_id>_graded.jsonl and
<run_id>_review.csv. Everything under results/raw/ is gitignored: it holds our answers.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.contracts import CodeResult, Ctx, Error, Final, Refusal, SoundLabels, Transcript
from app.models.memory import MemoryManager, measure_gb
from app.models.ollama_client import OllamaBackend
from app.orchestrate import handle
from app.settings import ROOT, Profile, load_env, load_profile
from eval.grade import grade_run, load_refs, refs_available
from eval.pack import load_items, to_attachments
from eval.types import REF_KEYS, PackItem, RunRecord

RESULTS = ROOT / "results"
MODALITIES = ("image", "audio", "text", "code", "video")
MEM_SAMPLE_S = 0.5


def make_run_id(profile: str, modality: str) -> str:
    return f"{datetime.now():%Y%m%d-%H%M}-{profile}-{modality}"


def apply_overrides(profile: Profile, sets: list[str]) -> Profile:
    """Return a copy of `profile` with "section.key=value" settings applied (values parsed as YAML)."""
    data = profile.model_dump()
    for s in sets or []:
        if "=" not in s:
            raise SystemExit(f"Use key.path=value, got: {s}")
        key, raw = s.split("=", 1)
        *path, last = key.strip().split(".")
        node = data
        for part in path:
            if not isinstance(node, dict) or not isinstance(node.get(part), dict):
                raise SystemExit(f"Unknown setting: {key}")
            node = node[part]
        if not isinstance(node, dict) or last not in node or isinstance(node[last], dict):
            raise SystemExit(f"Unknown setting: {key}")
        node[last] = yaml.safe_load(raw) if raw.strip() else ""
        try:
            Profile(**data)
        except ValidationError as e:
            raise SystemExit(f"Bad value for {key}: {raw!r}") from e
    return Profile(**data)


class _PeakMemory:
    """Samples measure_gb() in the background while one item runs."""

    def __init__(self):
        self.peak = 0.0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, measure_gb())
            self._stop.wait(MEM_SAMPLE_S)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join(timeout=2)
        self.peak = max(self.peak, measure_gb())


def _run_one(item: PackItem, ctx: Ctx, run_id: str) -> RunRecord:
    attachments = to_attachments(item)
    files = [] if attachments is not None or item.path is None else [item.path]
    names = [f.name for f in files]
    final: Final | None = None
    refusal: str | None = None
    code = transcript = None
    labels: list[str] = []
    t0 = time.perf_counter()
    with _PeakMemory() as mem:
        try:
            for ev in handle(item.question, files, item.meta.get("manual_id"), ctx,
                             original_names=names, attachments=attachments):
                if isinstance(ev, Final):
                    final = ev
                elif isinstance(ev, Refusal):
                    refusal = ev.reason
                elif isinstance(ev, Error):
                    refusal = "error"
                elif isinstance(ev, CodeResult):
                    code = ev.code
                elif isinstance(ev, Transcript):
                    transcript = ev.text
                elif isinstance(ev, SoundLabels):
                    labels = [s.label for s in ev.labels]
        except Exception:  # noqa: BLE001 - one broken item must not stop the run
            refusal = "error"
    return RunRecord(
        run_id=run_id, item_id=item.id, modality=item.modality,
        question_type=final.question_type if final else "none",
        answer=final.answer if final else "", refusal_reason=refusal, code=code, sound_labels=labels,
        latency_ms=final.latency_ms if final else int((time.perf_counter() - t0) * 1000),
        peak_mem_gb=round(mem.peak, 2), profile=ctx.profile.name, model=final.model if final else None,
        transcript=transcript,
    )


def run_items(items: list[PackItem], ctx: Ctx, run_id: str, sink: Path | None = None) -> list[RunRecord]:
    """Every item through handle(), never a pipeline directly. With `sink`, each record is appended
    as soon as it's done, so an interrupted run keeps its results."""
    out: list[RunRecord] = []
    for i, item in enumerate(items, 1):
        r = _run_one(item, ctx, run_id)
        out.append(r)
        if sink:
            with sink.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(r)) + "\n")
        flag = f" [{r.refusal_reason}]" if r.refusal_reason else ""
        print(f"[{i}/{len(items)}] {item.id} {item.modality}/{r.question_type} {r.latency_ms / 1000:.1f} s{flag}",
              flush=True)
    return out


def _pack_dir(arg: str | None) -> Path:
    raw = arg or os.environ.get("PRACTICE_PACK_DIR") or (str(load_env().practice_pack_dir or "") or None)
    if not raw or not (Path(raw) / "items.json").is_file():
        raise SystemExit("Set PRACTICE_PACK_DIR in .env (or pass --pack) to the unzipped practice pack folder "
                         f"that holds items.json. Got: {raw!r}")
    return Path(raw)


def _select(items: list[PackItem], modality: str, limit: int | None) -> list[PackItem]:
    out, seen = [], dict.fromkeys(MODALITIES, 0)
    for it in items:
        if modality != "all" and it.modality != modality:
            continue
        if limit is not None and seen[it.modality] >= limit:
            continue
        seen[it.modality] += 1
        out.append(it)
    return out


def _write_grades(raw: Path, run_id: str, records: list[RunRecord], items: dict[str, PackItem],
                  refs: dict[str, dict]) -> None:
    graded = grade_run(records, items, refs)
    with (raw / f"{run_id}_graded.jsonl").open("w", encoding="utf-8") as f:
        for g in graded:
            f.write(json.dumps(asdict(g)) + "\n")
    by_id = {r.item_id: r for r in records}
    with (raw / f"{run_id}_review.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "modality", "question_type", "metric", "score", "hit", "note", "ours", "ref"])
        for g in graded:
            r = by_id[g.item_id]
            ref = refs.get(g.item_id, {})
            ours = " | ".join(r.sound_labels) if r.sound_labels else (r.transcript or r.answer)
            w.writerow([g.item_id, r.modality, r.question_type, g.metric, f"{g.score:.2f}", g.hit, g.note,
                        ours, ref.get(REF_KEYS["answer"], ref.get(REF_KEYS["transcript"], ""))])
    hits = sum(g.hit for g in graded)
    print(f"graded {len(graded)} items: {hits} hits -> {raw / f'{run_id}_graded.jsonl'}")


def main(argv: list[str] | None = None) -> str:
    ap = argparse.ArgumentParser(prog="python -m eval.run", description="Run the practice pack through HomeFix.")
    ap.add_argument("--profile", choices=["full", "lite"], default=None, help="default: PROFILE from .env")
    ap.add_argument("--modality", choices=[*MODALITIES, "all"], default="all")
    ap.add_argument("--limit", type=int, default=None, help="at most N items per modality")
    ap.add_argument("--set", action="append", default=[], metavar="KEY.PATH=VALUE",
                    help="override a profile setting, e.g. models.brain=gemma4:e4b (repeatable)")
    ap.add_argument("--no-grade", action="store_true", help="skip grading even if reference answers exist")
    ap.add_argument("--pack", default=None, help="practice pack folder (default: PRACTICE_PACK_DIR)")
    a = ap.parse_args(argv)

    pack_dir = _pack_dir(a.pack)
    profile = apply_overrides(load_profile(a.profile), a.set)
    all_items = load_items(pack_dir)
    items = _select(all_items, a.modality, a.limit)
    if not items:
        raise SystemExit(f"No {a.modality} items in {pack_dir}")

    raw = RESULTS / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    run_id = base = make_run_id(profile.name, a.modality)
    n = 2
    while (raw / f"{run_id}.jsonl").exists():
        run_id, n = f"{base}-{n}", n + 1
    (raw / f"{run_id}_meta.json").write_text(json.dumps({
        "run_id": run_id, "profile": profile.name, "modality": a.modality, "limit": a.limit, "sets": a.set,
        "items": len(items), "brain": profile.models.brain, "coder": profile.models.coder,
        "started": datetime.now().isoformat(timespec="seconds")}))

    ctx = Ctx(profile, MemoryManager(profile, OllamaBackend()), deadline_s=profile.server.model_call_timeout_s)
    print(f"run {run_id}: {len(items)} items, profile {profile.name}, brain {profile.models.brain}", flush=True)
    records = run_items(items, ctx, run_id, sink=raw / f"{run_id}.jsonl")

    if a.no_grade:
        print("not graded (--no-grade)")
    elif refs_available(pack_dir):
        _write_grades(raw, run_id, records, {i.id: i for i in all_items}, load_refs(pack_dir))
    else:
        print("not graded: the pack has no reference answers")
    print(f"next: uv run python -m eval.report --run {run_id}")
    return run_id


if __name__ == "__main__":
    main(sys.argv[1:])
