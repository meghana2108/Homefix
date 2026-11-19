# Assets and licenses

Nothing copyrighted is committed. Gitignored folders: `practice_pack/`, `data/manuals/`, `data/assets/private/`, all media.

| Asset | Where it lives | Source | License | Committed? |
|---|---|---|---|---|
| Practice pack (100 items) | `$PRACTICE_PACK_DIR` (outside repo) | Hackathon organizers (COCO, VizWiz, LibriSpeech, ESC-10, SQuAD 2.0, HumanEval, synthetic video) | Per source dataset; hackathon use only | **Never** (HARD RULE 1) |
| `config/sound_labels/general.txt` | repo | Category *names* from the [AudioSet ontology](https://github.com/audioset/ontology), via `scripts/build_sound_vocab.py` | CC BY-SA 4.0 (Google) | Yes, with attribution |
| `config/sound_labels/appliances.txt` | repo | Written by us | MIT | Yes |
| `data/smartplug_fridge.csv` | repo | Synthetic, `scripts/make_smartplug_csv.py` | MIT | Yes |
| Appliance manuals (PDF) | `data/manuals/` | Manufacturer support sites; record the exact URL per file below | Manufacturer copyright | **Never** (HARD RULE 6) |
| Appliance beeps / noises | `data/assets/private/` | Recorded by us, or CC0 clips from Freesound (record URL + license) | Ours / CC0 | No (media) |
| Error-display photos | `data/assets/private/` | Photographed by us | Ours | No (media) |
| PWA icons | `frontend/public/icons/` | Made by us | MIT | Yes |

## Manuals to download (fill in)
**File names:** letters, digits, `_`, `.` and `-` only, no spaces, starting with a letter or digit,
e.g. `washer_lg_wm3400.pdf`. The file stem is the `manual_id` the UI sends, and
`app/pipelines/text.py` refuses any other id (it blocks paths like `../`).

| File name in `data/manuals/` | Appliance | Brand / model | Download URL |
|---|---|---|---|
| | Washing machine | | |
| | Dishwasher | | |
| | Refrigerator | | |
| | Microwave | | |

## Models
Downloaded by `scripts/pull_models.sh` into the Ollama and Hugging Face caches (never into the repo). Licenses: Qwen3-VL and Qwen2.5-Coder (Apache 2.0 for the sizes used; check the model card), Gemma 4 (Gemma terms), Whisper (MIT), CLAP (CC0/Apache per model card), bge-small (MIT).
