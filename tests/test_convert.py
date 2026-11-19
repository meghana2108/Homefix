"""Media normalization: every upload becomes a JPEG, 16 kHz WAV, H.264 video, page text or data
file, or a clear UnsupportedFile message. Never another exception."""

import json
import subprocess

import pytest
import soundfile as sf
from PIL import Image

from app.contracts import UnsupportedFile
from app.media.convert import normalize, probe, read_document
from tests import media_fixtures as mf

EXE_MSG = "I can't open .exe files. Try a photo, audio, video, PDF, Word, text or CSV file."


@pytest.fixture
def work(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def ff():
    mf.need_ffmpeg()


def _duration(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json",
                          str(path)], capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def _codec(path) -> str:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=codec_name,height", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return f"{s['codec_name']}:{s['height']}"


# ---------------------------------------------------------------- images
def test_big_png_becomes_small_jpeg(tmp_path, work, profile_lite):
    a = normalize(mf.make_png(tmp_path / "big.png"), "big.png", profile_lite, work)
    assert a.kind == "image" and a.path.suffix == ".jpg" and a.original_name == "big.png"
    with Image.open(a.path) as im:
        assert im.format == "JPEG" and max(im.size) == 1280


def test_small_jpeg_keeps_size(tmp_path, work, profile_lite):
    a = normalize(mf.make_jpeg(tmp_path / "mugs.jpg"), "mugs.jpg", profile_lite, work)
    with Image.open(a.path) as im:
        assert im.size == (800, 500)


def test_exif_rotation_applied(tmp_path, work, profile_lite):
    src = tmp_path / "rot.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW on display
    Image.new("RGB", (400, 200), "white").save(src, exif=exif)
    a = normalize(src, "rot.jpg", profile_lite, work)
    with Image.open(a.path) as im:
        assert im.size == (200, 400)


def test_gif_first_frame(tmp_path, work, profile_lite):
    src = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (50, 40), c) for c in ("red", "blue")]
    frames[0].save(src, save_all=True, append_images=frames[1:])
    a = normalize(src, "anim.gif", profile_lite, work)
    with Image.open(a.path) as im:
        r, _g, b = im.convert("RGB").getpixel((25, 20))
        assert r > 200 and b < 60


def test_heic(tmp_path, work, profile_lite, ff):
    a = normalize(mf.make_heic(tmp_path / "IMG_2041.heic"), "IMG_2041.heic", profile_lite, work)
    assert a.kind == "image" and a.path.suffix == ".jpg" and a.original_name == "IMG_2041.heic"
    with Image.open(a.path) as im:
        assert im.size == (1200, 900)


def test_text_renamed_to_jpg(tmp_path, work, profile_lite, ff):
    src = tmp_path / "fake.jpg"
    src.write_text("this is not a picture")
    with pytest.raises(UnsupportedFile, match=r"I can't open \.jpg files"):
        normalize(src, "fake.jpg", profile_lite, work)


# ---------------------------------------------------------------- audio
def test_stereo_44k_becomes_mono_16k(tmp_path, work, profile_lite, ff):
    src = mf.make_sine_wav(tmp_path / "beep.wav", channels=2)
    a = normalize(src, "beep.wav", profile_lite, work)
    info = sf.info(a.path)
    assert a.kind == "audio" and (info.samplerate, info.channels) == (16000, 1)
    assert a.path != src  # the upload is not overwritten in place


def test_wav_in_workdir_not_clobbered(work, profile_lite, ff):
    src = mf.make_sine_wav(work / "beep.wav", channels=2)
    a = normalize(src, "beep.wav", profile_lite, work)
    assert sf.info(a.path).samplerate == 16000


def test_m4a_voice_note(tmp_path, work, profile_lite, ff):
    wav = mf.make_sine_wav(tmp_path / "v.wav")
    m4a = tmp_path / "Voice 001.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", str(m4a)], check=True)
    a = normalize(m4a, "Voice 001.m4a", profile_lite, work)
    assert a.kind == "audio" and sf.info(a.path).samplerate == 16000


def test_webm_audio_only_is_audio(tmp_path, work, profile_lite, ff):
    a = normalize(mf.make_webm_audio_only(tmp_path / "rec.webm"), "rec.webm", profile_lite, work)
    assert a.kind == "audio" and a.path.suffix == ".wav"


# ---------------------------------------------------------------- video
def test_video_becomes_h264(tmp_path, work, profile_lite, ff):
    a = normalize(mf.make_video(tmp_path / "drum.mov"), "drum.mov", profile_lite, work)
    assert a.kind == "video" and a.path.suffix == ".mp4" and a.notes == []
    assert _codec(a.path) == "h264:360"


def test_tall_video_capped_at_720(tmp_path, work, profile_lite, ff):
    a = normalize(mf.make_video(tmp_path / "tall.mp4", seconds=1, size=(1080, 1920)), "tall.mp4",
                  profile_lite, work)
    assert _codec(a.path) == "h264:720"


def test_long_video_trimmed(tmp_path, work, profile_lite, ff):
    src = mf.make_video(tmp_path / "long.mp4", seconds=130, fps=2, size=(160, 90))
    a = normalize(src, "long.mp4", profile_lite, work)
    assert _duration(a.path) <= 120.5
    assert a.notes == ["Used the first 120 s."]


def test_webm_with_video_is_video(tmp_path, work, profile_lite, ff):
    src = mf.make_video(tmp_path / "clip.webm", seconds=2, audio=True)
    a = normalize(src, "clip.webm", profile_lite, work)
    assert a.kind == "video" and a.path.suffix == ".mp4"


def test_probe(tmp_path, ff):
    p = probe(mf.make_video(tmp_path / "a.mp4", seconds=2, audio=True))
    assert p["has_video"] and p["has_audio"] and 1.5 < p["duration"] < 2.5
    p = probe(mf.make_webm_audio_only(tmp_path / "b.webm"))
    assert not p["has_video"] and p["has_audio"]


# ---------------------------------------------------------------- documents and data
def test_txt_pages(tmp_path, work, profile_lite):
    src = tmp_path / "notes.txt"
    src.write_text("hello")
    a = normalize(src, "notes.txt", profile_lite, work)
    assert a.kind == "document" and a.pages == ["hello"]


def test_md_pages(tmp_path, work, profile_lite):
    src = tmp_path / "readme.md"
    src.write_text("# Washer\n\nClean the filter.\n")
    assert normalize(src, "readme.md", profile_lite, work).pages == ["# Washer\n\nClean the filter."]


def test_pdf_pages(tmp_path, work, profile_lite):
    src = mf.make_pdf(tmp_path / "manual.pdf", ["Error E21 means drain.", "Level the feet."])
    a = normalize(src, "manual.pdf", profile_lite, work)
    assert a.kind == "document" and len(a.pages) == 2
    assert "E21" in a.pages[0] and "Level" in a.pages[1]
    assert read_document(src) == a.pages


def test_docx_pages(tmp_path, work, profile_lite):
    src = mf.make_docx(tmp_path / "lease.docx", ["Rent is due on the 1st.", "No pets."])
    a = normalize(src, "lease.docx", profile_lite, work)
    assert a.pages == ["Rent is due on the 1st.\nNo pets."]


def test_broken_pdf(tmp_path, work, profile_lite):
    src = tmp_path / "broken.pdf"
    src.write_text("not a pdf")
    with pytest.raises(UnsupportedFile, match=r"\.pdf"):
        normalize(src, "broken.pdf", profile_lite, work)


@pytest.mark.parametrize("name", ["fridge.csv", "data.json", "helper.py"])
def test_data_copied_by_name(tmp_path, work, profile_lite, name):
    src = tmp_path / "upload.bin"
    src.write_text("timestamp,watts\n")
    a = normalize(src, name, profile_lite, work)
    assert a.kind == "data" and a.path == work / name and a.path.read_text() == "timestamp,watts\n"


# ---------------------------------------------------------------- refusals
def test_exe_refused(tmp_path, work, profile_lite):
    src = tmp_path / "setup.exe"
    src.write_bytes(b"MZ")
    with pytest.raises(UnsupportedFile) as e:
        normalize(src, "setup.exe", profile_lite, work)
    assert str(e.value) == EXE_MSG


def test_uppercase_ext(tmp_path, work, profile_lite):
    a = normalize(mf.make_jpeg(tmp_path / "x.jpg"), "PHOTO.JPG", profile_lite, work)
    assert a.kind == "image"


def test_no_extension(tmp_path, work, profile_lite):
    src = tmp_path / "README"
    src.write_text("x")
    with pytest.raises(UnsupportedFile, match="I can't open"):
        normalize(src, "README", profile_lite, work)


def test_zero_byte_jpg(tmp_path, work, profile_lite):
    src = tmp_path / "empty.jpg"
    src.write_bytes(b"")
    with pytest.raises(UnsupportedFile) as e:
        normalize(src, "empty.jpg", profile_lite, work)
    assert str(e.value) == "That file is empty."


@pytest.mark.parametrize("name", ["x.wav", "x.mp4", "x.webm"])
def test_garbage_media_is_unsupported(tmp_path, work, profile_lite, ff, name):
    src = tmp_path / name
    src.write_bytes(b"\x00garbage" * 50)
    with pytest.raises(UnsupportedFile):
        normalize(src, name, profile_lite, work)
