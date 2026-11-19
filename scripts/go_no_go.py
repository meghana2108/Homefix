"""Go/no-go smoke test: can this machine run every model HomeFix needs?

    uv run python scripts/go_no_go.py                  # profile from $PROFILE (default full)
    uv run python scripts/go_no_go.py --profile lite
    uv run python scripts/go_no_go.py --only vision,whisper

Uses one practice-pack item per modality when PRACTICE_PACK_DIR is set (reads items.json
only - never answers.json). Otherwise falls back to synthetic samples generated locally,
so it can run before the pack is downloaded.

Checks: vision (1 image Q), multi-image (video frames in one request), Whisper ASR,
CLAP sound label, coder (writes a function that must pass its doctest), structured JSON.
Prints a pass/fail table with wall time and memory. Exit code 1 if anything fails.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

import psutil
import yaml

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="homefix_gonogo_"))


# ---------------------------------------------------------------- helpers
@dataclass
class Result:
    name: str
    model: str
    ok: bool
    seconds: float
    detail: str
    ollama_gb: float = 0.0
    rss_gb: float = 0.0


def load_profile(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / "profiles" / f"{name}.yaml").read_text())


def ollama_client():
    import ollama

    return ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))


def ollama_loaded_gb() -> float:
    try:
        return sum(m.size for m in ollama_client().ps().models) / 1e9
    except Exception:  # noqa: BLE001 - diagnostics must never crash
        return 0.0


def rss_gb() -> float:
    return psutil.Process().memory_info().rss / 1e9


def chat(model: str, messages: list[dict], keep_alive=None, **kw) -> str:
    """Ollama chat with thinking disabled when the model supports it."""
    c = ollama_client()
    try:
        r = c.chat(model=model, messages=messages, think=False, keep_alive=keep_alive, **kw)
    except Exception as e:  # non-thinking models reject think=...
        if "think" not in str(e).lower():
            raise
        r = c.chat(model=model, messages=messages, keep_alive=keep_alive, **kw)
    return r.message.content or ""


def pack_items() -> dict[str, dict]:
    """First item per modality from items.json (never touches answers.json)."""
    d = os.environ.get("PRACTICE_PACK_DIR")
    if not d or not (Path(d) / "items.json").exists():
        return {}
    items = json.loads((Path(d) / "items.json").read_text())
    if isinstance(items, dict):
        items = items.get("items", list(items.values()))
    first: dict[str, dict] = {}
    for it in items:
        m = str(it.get("modality", "")).lower()
        first.setdefault(m, it)
    for it in first.values():
        if it.get("file"):
            it["path"] = str(Path(d) / it["file"])
    return first


# ---------------------------------------------------------------- synthetic fallbacks
def synth_image() -> tuple[str, str]:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 500), "white")
    d = ImageDraw.Draw(img)
    for x in (120, 360, 600):
        d.ellipse([x, 80, x + 110, 190], fill="red")
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 110)
    except OSError:
        font = ImageFont.load_default()
    d.rectangle([220, 260, 580, 440], fill="black")
    d.text((270, 290), "E21", fill="lime", font=font)
    p = TMP / "synth.jpg"
    img.save(p, quality=92)
    return str(p), "How many red circles are there, and what text is on the display?"


def synth_frames(n: int = 4) -> tuple[list[str], str]:
    from PIL import Image, ImageDraw

    paths = []
    for i in range(n):
        img = Image.new("RGB", (448, 252), "white")
        x = 30 + i * 110
        ImageDraw.Draw(img).rectangle([x, 100, x + 60, 160], fill="blue")
        p = TMP / f"frame_{i}.jpg"
        img.save(p)
        paths.append(str(p))
    return paths, "These are frames of a video in time order. Which direction does the blue square move?"


def video_frames(path: str, n: int = 4) -> list[str]:
    import cv2

    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    out = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((i + 0.5) * total / n))
        ok, frame = cap.read()
        if ok:
            h, w = frame.shape[:2]
            s = 448 / max(h, w)
            frame = cv2.resize(frame, (int(w * s), int(h * s)))
            p = TMP / f"vframe_{i}.jpg"
            cv2.imwrite(str(p), frame)
            out.append(str(p))
    cap.release()
    return out


def synth_speech() -> str:
    """macOS `say` -> 16 kHz mono WAV via built-in afconvert (no ffmpeg needed)."""
    aiff, wav = TMP / "speech.aiff", TMP / "speech.wav"
    subprocess.run(["say", "-o", str(aiff), "The washing machine shows error E twenty one."], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
    return str(wav)


def synth_beep() -> str:
    import numpy as np
    import soundfile as sf

    sr = 48000
    t = np.arange(int(sr * 0.25)) / sr
    tone = 0.5 * np.sin(2 * np.pi * 2800 * t)
    gap = np.zeros(int(sr * 0.2))
    sig = np.concatenate([tone, gap] * 4)
    p = TMP / "beep.wav"
    sf.write(p, sig, sr)
    return str(p)


# ---------------------------------------------------------------- checks
def check_vision(prof, items):
    model = prof["models"]["brain"]
    it = items.get("image")
    path, q = (it["path"], it["question"]) if it else synth_image()
    ans = chat(model, [{"role": "user", "content": q, "images": [path]}], keep_alive=prof["keep_alive"]["brain"])
    ok = bool(ans.strip()) if it else ("3" in ans or "three" in ans.lower())
    return model, ok, f"Q: {q[:50]} -> {ans.strip()[:70]}"


def check_multi_image(prof, items):
    model = prof["models"]["brain"]
    it = items.get("video")
    if it:
        frames, q = video_frames(it["path"]), it["question"]
    else:
        frames, q = synth_frames()
    content = "\n".join(f"Frame {i + 1} of {len(frames)}." for i in range(len(frames))) + "\n" + q
    ans = chat(model, [{"role": "user", "content": content, "images": frames}], keep_alive=prof["keep_alive"]["brain"])
    ok = bool(ans.strip()) if it else "right" in ans.lower()
    return model, ok and len(frames) >= 2, f"{len(frames)} frames -> {ans.strip()[:70]}"


def check_whisper(prof, items):
    import mlx_whisper

    model = prof["models"]["whisper_file"]
    it = items.get("audio")
    path = it["path"] if it else synth_speech()
    r = mlx_whisper.transcribe(path, path_or_hf_repo=model)
    text = r.get("text", "").strip()
    nsp = max((s.get("no_speech_prob", 0) for s in r.get("segments", [])), default=None)
    ok = bool(text) if it else ("washing" in text.lower() or "error" in text.lower())
    return model, ok, f"'{text[:60]}' no_speech_prob={nsp if nsp is None else round(nsp, 2)}"


def check_clap(prof, items):
    from transformers import pipeline

    model = prof["models"]["clap"]
    labels = [ln.strip() for f in ("general.txt", "appliances.txt")
              for ln in (ROOT / "config" / "sound_labels" / f).read_text().splitlines()
              if ln.strip() and not ln.startswith("#")]
    clf = pipeline("zero-shot-audio-classification", model=model)
    path = synth_beep()  # always test on a known sound so pass/fail is meaningful
    out = clf(path, candidate_labels=labels, hypothesis_template="This is a sound of {}.")
    top = [o["label"] for o in out[:3]]
    ok = any(k in " ".join(top) for k in ("beep", "bleep", "tone", "alarm", "chirp", "buzzer", "ding", "sine"))
    return model, ok, f"{len(labels)} labels, top3 for synthetic beep: {top}"


CODE_PROMPT = '''def count_long_runs(watts: list[float], threshold: float, min_len: int) -> int:
    """Count runs of consecutive readings strictly above `threshold` that last at least `min_len` readings.

    >>> count_long_runs([0, 120, 130, 0, 125, 0], 100, 2)
    1
    >>> count_long_runs([150, 150, 150], 100, 3)
    1
    >>> count_long_runs([], 100, 1)
    0
    """
'''


def check_coder(prof, items):
    model = prof["models"]["coder"]
    t0 = time.time()
    ans = chat(model, [{"role": "user", "content":
                        "Complete this Python function. Reply with only the full function in one ```python code block.\n\n"
                        + CODE_PROMPT}], keep_alive=prof["keep_alive"]["coder"])
    load_and_gen = time.time() - t0
    m = re.search(r"```(?:python)?\n(.*?)```", ans, re.DOTALL)
    code = (m.group(1) if m else ans).strip()
    if '"""' not in code:  # model dropped the docstring: re-attach the prompt's doctests
        code = CODE_PROMPT + "\n" + code.split("\n", 1)[1] if code.startswith("def ") else code
    f = TMP / "cand.py"
    f.write_text(code + "\n")
    p = subprocess.run([sys.executable, "-m", "doctest", str(f)], capture_output=True, text=True, check=False,
                       timeout=prof["code"]["selfcheck_timeout_s"], cwd=TMP)
    ok = p.returncode == 0
    return model, ok, f"doctest {'passed' if ok else 'FAILED'} (gen incl. load {load_and_gen:.1f}s)"


DOC = ("The Model WX-200 washer displays E21 when the drain pump cannot empty the drum within "
       "8 minutes. Clean the pump filter behind the lower-right panel. The warranty lasts 2 years.")


def check_json(prof, items):
    model = prof["models"]["brain"]
    schema = {"type": "object", "properties": {
        "answerable": {"type": "boolean"}, "answer": {"type": "string"},
        "quote": {"type": "string"}, "page": {"type": ["integer", "null"]}},
        "required": ["answerable", "answer", "quote", "page"]}
    out = {}
    for q, expect in (("How long does the drain pump have before E21 shows?", True),
                      ("What is the spin speed of the WX-200?", False)):
        raw = chat(model, [{"role": "user", "content":
                            f"Document:\n{DOC}\n\nQuestion: {q}\nAnswer only from the document. "
                            "Copy `quote` word for word from it. If the document does not contain the answer, "
                            "set answerable=false."}],
                   format=schema, options={"temperature": 0}, keep_alive=prof["keep_alive"]["brain"])
        d = json.loads(raw)
        out[q] = d
        if set(d) < {"answerable", "answer", "quote"}:
            return model, False, f"missing keys: {d}"
        if d["answerable"] != expect:
            return model, False, f"answerable={d['answerable']} for '{q[:30]}'"
    q1 = next(iter(out.values()))
    return model, q1["quote"].lower()[:20] in DOC.lower(), f"valid JSON; quote='{q1['quote'][:50]}'"


CHECKS = {
    "vision": ("Vision: image question", check_vision),
    "multi_image": ("Vision: multi-image (video)", check_multi_image),
    "whisper": ("Whisper transcription", check_whisper),
    "clap": ("CLAP sound label", check_clap),
    "coder": ("Coder writes a function", check_coder),
    "json": ("Structured JSON output", check_json),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.environ.get("PROFILE", "full"))
    ap.add_argument("--only", default="", help="comma list of: " + ",".join(CHECKS))
    a = ap.parse_args()
    prof = load_profile(a.profile)
    items = pack_items()
    selected = [k for k in CHECKS if not a.only or k in a.only.split(",")]

    from rich.console import Console
    from rich.table import Table

    con = Console()
    con.print(f"[bold]HomeFix go/no-go[/] profile=[cyan]{a.profile}[/] "
              f"samples=[cyan]{'practice pack' if items else 'synthetic (PRACTICE_PACK_DIR not set)'}[/] "
              f"RAM={psutil.virtual_memory().total / 1e9:.0f} GB")

    try:
        own = subprocess.run(["lsof", "-nP", "-iTCP:11434", "-sTCP:LISTEN"], capture_output=True, text=True, check=False).stdout
        if "docker" in own.lower():
            con.print("[bold yellow]WARNING:[/] Ollama on :11434 is running in Docker -> no Metal GPU, "
                      "latency will be far off. Use native Ollama.")
    except FileNotFoundError:
        pass

    results: list[Result] = []
    for key in selected:
        label, fn = CHECKS[key]
        con.print(f"  running {label} ...")
        t0 = time.time()
        try:
            model, ok, detail = fn(prof, items)
        except Exception as e:  # noqa: BLE001 - report, keep going
            model, ok, detail = "-", False, f"{type(e).__name__}: {str(e)[:120]}"
            if os.environ.get("DEBUG"):
                traceback.print_exc()
        results.append(Result(label, model, ok, time.time() - t0, detail, ollama_loaded_gb(), rss_gb()))

    t = Table(title=f"go/no-go ({a.profile})")
    for col in ("Check", "Model", "Result", "Time s", "Ollama GB", "Py RSS GB", "Detail"):
        t.add_column(col, overflow="fold")
    for r in results:
        t.add_row(r.name, r.model, "[green]PASS[/]" if r.ok else "[red]FAIL[/]", f"{r.seconds:.1f}",
                  f"{r.ollama_gb:.1f}", f"{r.rss_gb:.1f}", r.detail)
    con.print(t)
    vm = psutil.virtual_memory()
    con.print(f"System memory used: {(vm.total - vm.available) / 1e9:.1f} / {vm.total / 1e9:.1f} GB")
    failed = [r.name for r in results if not r.ok]
    con.print("[bold green]GO[/]" if not failed else f"[bold red]NO-GO[/]: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
