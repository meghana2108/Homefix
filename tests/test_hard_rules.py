"""Guards for the hackathon HARD RULES. These must always pass."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inference_path_never_reads_answers_json():
    """HARD RULE 4: only eval/ may reference answers.json."""
    offenders = [
        str(p.relative_to(ROOT))
        for p in (ROOT / "app").rglob("*")
        if p.is_file() and p.suffix in {".py", ".yaml", ".yml", ".json", ".txt", ".md"}
        and "answers.json" in p.read_text(errors="ignore")
    ]
    assert offenders == [], f"answers.json referenced in inference path: {offenders}"


def test_no_practice_pack_or_manuals_tracked():
    """HARD RULES 1 and 6: no pack data or manuals in git."""
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    bad = [f for f in tracked if re.search(r"(practice_pack/|data/manuals/|(^|/)answers\.json$|(^|/)items\.json$)", f)
           or re.search(r"\.(wav|mp3|m4a|mp4|mov|webm|pdf)$", f, re.I)]
    assert bad == [], f"forbidden files tracked: {bad}"


def test_sound_vocab_is_not_esc50():
    """HARD RULE 3: vocabulary is broad (hundreds of labels), not a 10/50-class lookup."""
    labels = [ln for ln in (ROOT / "config/sound_labels/general.txt").read_text().splitlines()
              if ln.strip() and not ln.startswith("#")]
    assert len(labels) >= 200
