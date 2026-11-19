"""Video pipeline: describe a short clip, count, follow motion or read signs from sampled frames.

Frames (16 on full, 8 on lite) are listed as "Frame k at t=...s" and sent in one brain call:
- describe / qa / motion / read: tiled 2x2 into grids with gutters (app/video/grid.py), since
  each image costs ~1,050 tokens at any size. Read adds the 2 sharpest frames at native size.
- count: one whole frame (in grids the model counted the tiles as objects), the one with the most
  edges (app/video/pick.py), so things that appear one at a time are all on screen. Limit: counting
  events over time ("how many bounces") can't be done from one frame.
- When code measures a clear direction (app/video/motion.py), the prompt says so; the 2B model
  misreads motion from grids without it.
The audio track is not transcribed or safety-checked (a named limit).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from app.contracts import (
    MESSAGES,
    Ctx,
    Event,
    Frames,
    PipelineRequest,
    Refusal,
    Status,
    UnsupportedFile,
    final_for,
)
from app.numbers import first_int  # noqa: F401 - re-export only for tests/test_image.py::test_matches_video_copies
from app.pipelines.common import collect, stream_brain
from app.prompts import READ_PROMPT, count_prompt, force_number_first
from app.settings import ROOT
from app.video import motion
from app.video.frames import extract_frames
from app.video.grid import make_grids
from app.video.pick import busiest_frame

MOTION_WORDS = ("left", "right", "up", "down", "toward", "away", "clockwise", "counterclockwise")
MOTION_PROMPT = ("Answer with one direction word from: left, right, up, down, toward, away, clockwise, "
                 "counterclockwise, then one sentence.")
COUNT_IN_FRAME = " Count what is visible in this one frame."



DESCRIBE_PROMPT = ("Describe what happens in the video in one paragraph of at most 80 words. "
                   "Refer to moments by their time, for example 'at t=3.0s'.")


def frame_labels(timestamps: list[float]) -> str:
    """One line per frame, k from 1: 'Frame 1 at t=0.0s'. Half-way values round up (1.95 -> 2.0)."""
    return "\n".join(f"Frame {k} at t={round(t + 1e-9, 1):.1f}s" for k, t in enumerate(timestamps, 1))


def _question(req: PipelineRequest) -> str:
    q = req.question_type
    if q == "count":
        return count_prompt(req.message)
    if q == "read":
        return READ_PROMPT
    if q == "motion":
        return f"{req.message}\n{MOTION_PROMPT}"
    if q == "describe" or not req.message:
        return DESCRIBE_PROMPT
    return (f"{req.message}\nAnswer in one short paragraph of at most 80 words. "
            f"If the frames don't show it, reply exactly: {MESSAGES['cant_tell']}")


def _grid_prompt(req: PipelineRequest, timestamps: list[float], n_grids: int, n_sharp: int,
                 direction: str | None) -> str:
    intro = (f"These are {len(timestamps)} frames from one video, in time order, shown as {n_grids} "
             f"image{'s' if n_grids != 1 else ''}. Each image is a 2x2 grid of 4 separate frames (panels) read "
             "top-left, top-right, bottom-left, bottom-right; each frame's number is in its top-left corner. "
             "The grey lines separate the panels. Each panel shows the whole scene at one moment: compare where "
             "things are inside each panel, not where the panel is in the grid.")
    parts = [intro, frame_labels(timestamps)]
    if n_sharp:
        parts.append(f"The last {n_sharp} images are the sharpest frames at full resolution, for reading text.")
    if direction:
        parts.append(f"Measured from the frames by code: the moving object goes {direction}.")
    parts.append(_question(req))
    return "\n\n".join(parts)


def _count_prompt(req: PipelineRequest, t: float) -> str:
    return f"This is one frame from a video, at t={t:.1f}s.\n\n" + count_prompt(req.message) + COUNT_IN_FRAME


def _cache_dir(ctx: Ctx) -> Path:
    p = Path(ctx.profile.cache_dir)
    return p if p.is_absolute() else ROOT / p


def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]:
    att = next((a for a in req.attachments if a.kind == "video" and a.path), None)
    if att is None:
        yield Refusal(reason="empty_input", message=MESSAGES["empty_input"])
        yield final_for(ctx, "video", req.question_type)
        return

    cfg = ctx.profile.video
    sharp = cfg.read_extra_frames if req.question_type == "read" else 0
    yield Status(stage="extracting_frames")
    try:
        fs = extract_frames(att.path, cfg.frames, cfg.frame_side, sharp, _cache_dir(ctx))
    except UnsupportedFile as e:
        yield Refusal(reason="unsupported_file", message=str(e))
        yield final_for(ctx, "video", req.question_type)
        return
    if fs.cached:
        yield Status(stage="extracting_frames", detail="cached")
    yield Frames(timestamps=fs.timestamps)

    if req.question_type == "count":
        pick = busiest_frame(fs.paths)
        images = [fs.paths[pick]]
        content = _count_prompt(req, fs.timestamps[pick])
    else:
        grids = make_grids(fs.paths, fs.paths[0].parent / f"grids_{len(fs.paths)}")
        images = grids + fs.sharp_paths
        content = _grid_prompt(req, fs.timestamps, len(grids), len(fs.sharp_paths),
                               motion.measure_motion(fs.paths))
    messages = [{"role": "user", "content": content}]

    answer: list[str] = []
    was_refused = False
    for ev in collect(stream_brain(ctx, messages, images), answer):  # pass tokens on as they arrive
        was_refused = was_refused or isinstance(ev, Refusal)
        yield ev
    if was_refused:
        yield final_for(ctx, "video", req.question_type)
        return
    text = "".join(answer).strip()
    if req.question_type == "count":
        text = force_number_first(text)
    yield final_for(ctx, "video", req.question_type, answer=text, model=ctx.memory.tag("brain"))
