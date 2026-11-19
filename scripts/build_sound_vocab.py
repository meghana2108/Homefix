"""Build config/sound_labels/general.txt from the AudioSet ontology (CC BY-SA 4.0).

HARD RULE 3: we do NOT use the ESC-50 class list. This vocabulary comes from a broad,
general ontology of ~630 everyday sound categories, cleaned to a few hundred labels.
Run once at dev time (needs internet); the output file is committed.

    uv run python scripts/build_sound_vocab.py            # downloads ontology.json
    uv run python scripts/build_sound_vocab.py ontology.json  # or use a local copy
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ONTOLOGY_URL = "https://raw.githubusercontent.com/audioset/ontology/master/ontology.json"
OUT = Path(__file__).resolve().parents[1] / "config" / "sound_labels" / "general.txt"

# Abstract grouping nodes / music genres that make poor zero-shot labels.
DROP_IDS_UNDER = {"/m/04rlf"}  # "Music" subtree (genres, instruments) -> keep only a few generic music labels
KEEP_EXTRA = ["music", "singing", "speech", "silence", "noise"]
DROP_NAMES = {
    "channel, environment and background", "acoustic environment", "sound reproduction",
    "source-ambiguous sounds", "generic impact sounds", "surface contact", "deformable shell",
    "onomatopoeia", "human sounds", "human voice", "animal", "natural sounds", "things",
    "miscellaneous sources", "specific impact sounds", "brief tone", "sounds of things",
    "domestic sounds, home sounds", "vehicle", "mechanisms", "tools", "liquid", "glass",
    "wood", "explosion", "alarm", "engine", "other sourcess", "music genre", "musical concepts",
    "music role", "music mood",
}


def clean(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\s*\(.*?\)", "", name)  # drop parentheticals
    return name.strip(" ,")


def main() -> None:
    if len(sys.argv) > 1:
        nodes = json.loads(Path(sys.argv[1]).read_text())
    else:
        with urllib.request.urlopen(ONTOLOGY_URL, timeout=30) as r:
            nodes = json.load(r)
    by_id = {n["id"]: n for n in nodes}

    music_ids: set[str] = set()
    stack = list(DROP_IDS_UNDER)
    while stack:
        nid = stack.pop()
        if nid in music_ids:
            continue
        music_ids.add(nid)
        stack.extend(by_id.get(nid, {}).get("child_ids", []))

    labels: list[str] = []
    for n in nodes:
        if n["id"] in music_ids:
            continue
        if "abstract" in n.get("restrictions", []) or "blacklist" in n.get("restrictions", []):
            continue
        name = clean(n["name"])
        if not name or name in DROP_NAMES or len(name) > 40:
            continue
        # Expand comma lists like "Dog, bark" -> keep the first full phrase only.
        labels.append(name)
    labels.extend(KEEP_EXTRA)

    seen: set[str] = set()
    uniq = [x for x in labels if not (x in seen or seen.add(x))]
    OUT.write_text(
        "# General everyday-sound vocabulary, derived from the AudioSet ontology (CC BY-SA 4.0)\n"
        "# by scripts/build_sound_vocab.py. NOT derived from ESC-50 (HARD RULE 3).\n"
        + "\n".join(sorted(uniq))
        + "\n"
    )
    print(f"wrote {len(uniq)} labels -> {OUT}")


if __name__ == "__main__":
    main()
