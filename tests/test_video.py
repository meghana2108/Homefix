"""Video pipeline: timestamped frames in one brain call. Each image costs qwen3-vl ~1,050 tokens
at any size, so frames are tiled 2x2 into grids with gutters; counts use one full middle frame;
motion gets a direction measured by plain code (the 2B model misreads motion from grids)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.contracts import Attachment, Final, Frames, PipelineRequest, Refusal, Status, Token
from app.pipelines import video
from app.pipelines.video import MOTION_WORDS, frame_labels
from app.video.grid import make_grids
from app.video.motion import measure_motion
from tests import media_fixtures as mf


@pytest.fixture
def clip(tmp_path):
    return mf.make_video(tmp_path / "drum.mp4", seconds=4.0, fps=10, size=(640, 360))


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, profile_full, profile_lite, monkeypatch):
    for p in (profile_full, profile_lite):
        monkeypatch.setattr(p, "cache_dir", str(tmp_path / "cache"))


def run(ctx, clip, message="", qtype="describe"):
    req = PipelineRequest(message, [Attachment(clip, "video", clip.name)], qtype)
    return list(video.run(req, ctx))


def of(events, cls):
    return [e for e in events if isinstance(e, cls)]


def test_frame_labels():
    assert frame_labels([0.0, 1.95]) == "Frame 1 at t=0.0s\nFrame 2 at t=2.0s"


def test_full_sends_16_frames_as_4_grids(ctx_full, clip, fake_brain):
    fake_brain("The drum turns.")
    ev = run(ctx_full, clip)
    assert len(of(ev, Frames)[0].timestamps) == 16
    images = fake_brain.calls[0]["images"]
    assert len(images) == 4
    with Image.open(images[0]) as im:
        assert im.size == (896 + 12, 504 + 12)  # 2x2 tiles of 448x252 plus a 12 px gutter


def test_lite_sends_8_frames_as_2_grids(ctx_lite, clip, fake_brain):
    fake_brain("ok")
    ev = run(ctx_lite, clip)
    assert len(of(ev, Frames)[0].timestamps) == 8
    assert len(fake_brain.calls[0]["images"]) == 2


def test_read_adds_two_sharp_frames(ctx_full, clip, fake_brain):
    fake_brain("EXIT")
    run(ctx_full, clip, "What does the sign say?", "read")
    images = fake_brain.calls[0]["images"]
    assert len(images) == 4 + 2
    with Image.open(images[-1]) as im:
        assert im.size == (640, 360)  # native resolution
    prompt = fake_brain.calls[0]["messages"][-1]["content"]
    assert "sharpest frames" in prompt and "Read the text exactly as written." in prompt


def test_prompt_lists_every_frame_and_the_grid(ctx_lite, clip, fake_brain):
    fake_brain("ok")
    ev = run(ctx_lite, clip, "What happens?", "qa")
    prompt = fake_brain.calls[0]["messages"][-1]["content"]
    ts = of(ev, Frames)[0].timestamps
    assert frame_labels(ts) in prompt
    assert "2x2 grid" in prompt and "What happens?" in prompt


def test_frames_event_before_tokens(ctx_lite, clip, fake_brain):
    fake_brain("The drum does not turn.")
    ev = run(ctx_lite, clip)
    assert ev.index(of(ev, Frames)[0]) < ev.index(of(ev, Token)[0])
    assert ev[0] == Status(stage="extracting_frames")
    assert isinstance(ev[-1], Final) and ev[-1].modality == "video" and ev[-1].answer == "The drum does not turn."
    assert ev[-1].model == ctx_lite.profile.models.brain


def test_second_run_says_cached(ctx_lite, clip, fake_brain):
    fake_brain("a", "b")
    run(ctx_lite, clip)
    ev = run(ctx_lite, clip)
    assert Status(stage="extracting_frames", detail="cached") in ev


def test_motion_prompt(ctx_lite, clip, fake_brain):
    fake_brain("Right. The square moves right.")
    ev = run(ctx_lite, clip, "Which direction does the square move?", "motion")
    prompt = fake_brain.calls[0]["messages"][-1]["content"]
    assert "clockwise, counterclockwise" in prompt
    assert "Measured from the frames by code: the moving object goes right." in prompt
    assert ev[-1].answer == "Right. The square moves right."
    assert set(MOTION_WORDS) == {"left", "right", "up", "down", "toward", "away", "clockwise", "counterclockwise"}


def test_count_number_first(ctx_lite, clip, fake_brain):
    fake_brain("three people")
    ev = run(ctx_lite, clip, "How many people are in the room?", "count")
    assert ev[-1].answer == "3. three people"
    assert "Count the people" in fake_brain.calls[0]["messages"][-1]["content"]


def test_count_uses_one_full_middle_frame(ctx_full, clip, fake_brain):
    """Grids made the model count tiles as objects; a count looks at one whole frame."""
    fake_brain("1. One square.")
    ev = run(ctx_full, clip, "How many squares?", "count")
    images = fake_brain.calls[0]["images"]
    ts = of(ev, Frames)[0].timestamps
    assert len(images) == 1
    with Image.open(images[0]) as im:
        assert max(im.size) == 448
    assert f"t={ts[len(ts) // 2]:.1f}s" in fake_brain.calls[0]["messages"][-1]["content"]


def test_count_cant_tell_kept(ctx_lite, clip, fake_brain):
    fake_brain("I can't tell.")
    assert run(ctx_lite, clip, "how many cats?", "count")[-1].answer == "I can't tell."


def test_unreadable_video_refuses(ctx_lite, tmp_path, fake_brain):
    bad = tmp_path / "x.mp4"
    bad.write_bytes(b"\x00junk" * 100)
    fake_brain()
    ev = run(ctx_lite, bad)
    assert ev[-2].type == "refusal" and ev[-2].reason == "unsupported_file" and isinstance(ev[-1], Final)
    assert fake_brain.calls == []


def test_brain_down_refuses(ctx_lite, clip, monkeypatch):
    from app.contracts import MESSAGES, ModelUnavailable
    from app.models import ollama_client

    def down(*a, **kw):
        raise ModelUnavailable(MESSAGES["ollama_down"])
        yield  # pragma: no cover
    monkeypatch.setattr(ollama_client, "chat_stream", down)
    ev = run(ctx_lite, clip)
    assert of(ev, Frames) and ev[-2] == Refusal(reason="model_unavailable", message=MESSAGES["ollama_down"])
    assert ev[-1].answer == ""


def test_no_video_attachment(ctx_lite):
    ev = list(video.run(PipelineRequest("hi", [], "qa"), ctx_lite))
    assert ev[-2].type == "refusal" and isinstance(ev[-1], Final)


# ---------------------------------------------------------------- grids
def frames(tmp_path, n, size=(448, 252)):
    out = []
    for i in range(n):
        p = tmp_path / f"f{i}.jpg"
        Image.new("RGB", size, (40 * i % 255, 200, 100)).save(p)
        out.append(p)
    return out


def test_grid_layout_and_numbers(tmp_path):
    grids = make_grids(frames(tmp_path, 5), tmp_path / "g")
    assert len(grids) == 2
    a = np.asarray(Image.open(grids[0]).convert("RGB"))
    assert a.shape == (504 + 12, 896 + 12, 3)
    assert np.abs(a[100, 450].astype(int) - 128).max() <= 6  # grey gutter between the panels (JPEG)
    b = np.asarray(Image.open(grids[1]).convert("RGB"))
    assert b[420:, 620:].max() < 20  # unused tiles stay black
    # tile numbers are drawn in each top-left corner (white text on a dark box)
    assert a[2:30, 2:40].max() > 200


def test_grid_portrait_frames(tmp_path):
    grids = make_grids(frames(tmp_path, 4, size=(252, 448)), tmp_path / "g")
    with Image.open(grids[0]) as im:
        assert im.size == (504 + 12, 896 + 12)


def test_grid_numbers_continue_across_grids(tmp_path):
    """Tile labels are the frame numbers (5-8 in the second grid), matching 'Frame k at t=...'."""
    out = tmp_path / "g"
    make_grids(frames(tmp_path, 8), out, first_number=1)
    assert sorted(p.name for p in out.iterdir()) == ["grid_01-04.jpg", "grid_05-08.jpg"]


# ---------------------------------------------------------------- measured motion
def moving_frames(tmp_path, direction, n=8, size=(448, 252), grow=False):
    w, h = size
    out = []
    for i in range(n):
        a = i / (n - 1)
        side = int(30 + 60 * a) if grow else 40
        x, y = {"right": (10 + a * (w - 60), h / 2), "left": (w - 50 - a * (w - 60), h / 2),
                "down": (w / 2, 10 + a * (h - 60)), "up": (w / 2, h - 50 - a * (h - 60)),
                "still": (w / 2, h / 2)}[direction]
        if grow:
            x, y = w / 2 - side / 2, h / 2 - side / 2
        im = Image.new("RGB", size, "black")
        im.paste((255, 255, 255), (int(x), int(y), int(x) + side, int(y) + side))
        p = tmp_path / f"{direction}{i}.jpg"
        im.save(p)
        out.append(p)
    return out


@pytest.mark.parametrize("direction", ["right", "left", "down", "up"])
def test_measure_motion(tmp_path, direction):
    assert measure_motion(moving_frames(tmp_path, direction)) == direction


def test_measure_motion_toward(tmp_path):
    assert measure_motion(moving_frames(tmp_path, "right", grow=True)) == "toward"


def test_measure_motion_still_is_none(tmp_path):
    assert measure_motion(moving_frames(tmp_path, "still")) is None


def test_no_hint_when_nothing_moves(ctx_lite, tmp_path, fake_brain):
    still = mf.make_video(tmp_path / "still.mp4", seconds=2.0, fps=10)
    from app.video import motion
    fake_brain("ok")
    from unittest.mock import patch
    with patch.object(motion, "measure_motion", return_value=None):
        run(ctx_lite, still, "Which way does it move?", "motion")
    assert "Measured from the frames" not in fake_brain.calls[0]["messages"][-1]["content"]


def test_video_uses_the_shared_m6_helpers():
    """video.py imports app.prompts (no local copies left), so image and video count the same way."""
    from app import prompts

    assert video.count_prompt is prompts.count_prompt
    assert video.force_number_first is prompts.force_number_first
    assert video.READ_PROMPT is prompts.READ_PROMPT


@pytest.mark.model
def test_real_direction_on_lite(tmp_path, profile_lite, monkeypatch):
    from app.contracts import Ctx
    from app.models.memory import MemoryManager
    from app.models.ollama_client import OllamaBackend

    monkeypatch.setattr(profile_lite, "cache_dir", str(tmp_path / "cache"))
    ctx = Ctx(profile_lite, MemoryManager(profile_lite, OllamaBackend()), deadline_s=90)
    clip = mf.make_video(tmp_path / "move.mp4", seconds=4.0, fps=10)
    ev = run(ctx, Path(clip), "Which direction does the square move?", "motion")
    assert "right" in ev[-1].answer.lower()


def test_tokens_stream_live(ctx_lite, clip, monkeypatch):
    """The first token must reach the UI while the brain is still generating."""
    from app.models import ollama_client

    progress = {"done": False}

    def slow_brain(*a, **kw):
        yield "The "
        yield "drum "
        progress["done"] = True
        yield "stops."
    monkeypatch.setattr(ollama_client, "chat_stream", slow_brain)
    req = PipelineRequest("", [Attachment(clip, "video", clip.name)], "describe")
    for ev in video.run(req, ctx_lite):
        if isinstance(ev, Token):
            assert progress["done"] is False
            break
    else:
        pytest.fail("no token")
