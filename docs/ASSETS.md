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
| `washer_end_of_cycle_beep_synthetic.wav` | `data/assets/private/` | Made by us: `scripts/make_demo_assets.py` (five 2.4 kHz beeps over a drum hum, 16 kHz mono, 4.8 s) | MIT | No (media); the script is committed |
| `washer_display_e21_synthetic.jpg`, `washer_display_e21_closeup_synthetic.jpg` | `data/assets/private/` | Made by us: `scripts/make_demo_assets.py` (washer panel with a 7-segment "E21", phone-photo blur and noise; `--code` for others) | MIT | No (media); the script is committed |
| `apartment_guide_unit_4b.pdf` (title "Unit 4B apartment guide: washer, heat and who to call") | `data/manuals/` | Written by us: `scripts/make_demo_assets.py`. A sample landlord's guide, 4 pages: who to call, washer BW-200 beeps and error codes (E10, E21, E40, E52, E90) as text, cleaning the drain filter, heat, breakers, smoke alarm. Fictional appliance and building, no real brand | MIT | No (gitignored folder); the script is committed |
| Example gallery samples (`frontend/public/samples/`): 4 photos (washer E21, dishwasher E24, thermostat 68, cooktop), 3 sounds (washer beeps, smoke alarm chirp, dripping), 2 voicemails, 2 clips (dripping pipe, warning lights), a sample lease PDF, a smart-plug CSV | `frontend/public/samples/` | Made by us: `scripts/make_samples.py` (synthetic drawings and tones; voicemails with macOS `say`, offline; fictional names and building) | MIT | No (gitignored: the hard-rule test bans tracked .wav/.mp4/.pdf); run the script on each Mac |
| Real gallery photos: `real_thermostat_80_cool.jpg`, `real_thermostat_66.jpg` (Ente75, CC0), `real_burner_glowing.jpg` (A.Savin, CC BY-SA 3.0), `real_breaker_panel.jpg` (BrokenSphere, CC BY-SA 3.0), `real_microwave.jpg` (Raimond Spekking, CC BY-SA 4.0), `real_water_heater_label.jpg` (Jason Woodhead, CC BY 2.0) | `frontend/public/samples/` | Wikimedia Commons, by file title in `scripts/fetch_real_samples.py` (resized to 1280 px) | As listed; credit shown under each example in the gallery | No (gitignored); `uv run python scripts/fetch_real_samples.py` on each Mac |
| Real demo files for `#/demo` (also fetched by the same script): `real_leaking_pipe.jpg` ("Leaking pipe by Saltash Field - geograph.org.uk - 7324720.jpg", Mr Ignavy, CC BY-SA 2.0), `real_smoke_detector.jpg` ("Smoke detector (1).JPG", Georg Pik, public domain), `real_smoke_alarm_chirp.wav` (adapted from "Smoke detector alarm battery beep.webm", JoBrodie, CC BY-SA 4.0; changes: cut to 9 s from 38 s, +20 dB with a limiter, 16 kHz mono). With `real_breaker_panel.jpg` and `real_thermostat_66.jpg` above these are `DEMO_MEDIA` | `frontend/public/samples/` | Wikimedia Commons, by file title in `scripts/fetch_real_samples.py`; license and author checked through the Commons API on 2026-11-20 | As listed; credit shown in the demo | No (gitignored); same script |
| Real documents: `epa_mold_guide.pdf` (US EPA 402-K-02-003, "A Brief Guide to Mold, Moisture, and Your Home"), `cpsc_carbon_monoxide.pdf` (US CPSC 464, "Carbon Monoxide: The Invisible Killer"); also on the manual shelf as `epa_mold_moisture_guide` and `cpsc_carbon_monoxide` with short titles | `frontend/public/samples/`, `data/manuals/` | epa.gov, cpsc.gov | Public domain (US government works) | No (gitignored); same script |
| Real data: `real_home_power_week.csv`, hourly mean watts for 2007-01-08 to 2007-01-14 | `frontend/public/samples/` | UCI "Individual household electric power consumption" (G. Hébrail, A. Bérard), sliced by the same script | CC BY 4.0 | No (gitignored); same script |
| Sample guides: `dishwasher_dw50.pdf`, `thermostat_t100.pdf`, `smoke_co_alarm.pdf` (plus the Unit 4B guide) | `data/manuals/` | Written by us: `scripts/make_samples.py`. Fictional appliances, codes typed out as text | MIT | No (gitignored folder); run the script on each Mac |
| Error-display photos (real) | `data/assets/private/` | Photographed by us | Ours | No (media) |
| PWA icons | `frontend/public/icons/` | Made by us | MIT | Yes |

## Manuals to download (fill in)
**File names:** letters, digits, `_`, `.` and `-` only, no spaces, starting with a letter or digit,
e.g. `washer_lg_wm3400.pdf`. The file stem is the `manual_id` the UI sends, and
`app/pipelines/text.py` refuses any other id (it blocks paths like `../`).

| File name in `data/manuals/` | Appliance | Brand / model | Download URL |
|---|---|---|---|
| `washer_aeg_l6fbj741n.pdf` | Washing machine | AEG L6FBJ741N (front loader, 40 pages) | https://www.appliancesdirect.co.uk/PDFs/L6FBJ741N_usermanual1.PDF (retailer copy of AEG's user manual; downloaded 2026-11-19) |
| | Dishwasher | | |
| | Refrigerator | | |
| | Microwave | | |

### What the demo assets do (checked on the M2, `lite`, 2026-11-19)
- **G1, synthetic beep:** `uv run python -m app.cli "what is this sound?" --file data/assets/private/washer_end_of_cycle_beep_synthetic.wav`
  gives `microwave beeping 19%, washing machine beeping 18%, busy signal 11%`: in the top 3, but only
  1 point behind "microwave beeping". Plain beeps without the hum don't reach the top 3. **A real
  recording of a washer finishing is safer for the demo.**
- **E21 photo:** the brain reads `E21` 5/5 times on both photos with the M13 display prompt. An earlier
  version with short, unjoined segments read as "888", "0" or the knob label "Wool"; segments must
  be long and joined, and unlit segments nearly invisible.
- **Manual:** AEG lists E21 as a draining fault (AEG support pages), but in this manual, like the 5
  Electrolux manuals we checked, **alarm codes are drawn as display graphics, not text**: "E21"
  appears nowhere in the PDF's text. What it does say: "Clean the filter regularly and, especially,
  if the alarm code appears on the display" (p. 37) and the drain checklist (p. 32). So:
  - "The washer won't drain. What should I check?" → answer quoted from p. 32.
  - "What is the warranty period for this washer?" → "The document doesn't contain the answer." (G3)
  - "What does error code E21 mean…?" (what G2 asks) can't be matched to a code in the text. On
    2026-11-19 the text pipeline answered "null" with a citation (reported to Meghana).
- Manual file names: letters, digits, `_`, `.`, `-`; the stem is the `manual_id`.

## Models
Downloaded by `scripts/pull_models.sh` into the Ollama and Hugging Face caches (never into the repo). Licenses: Qwen3-VL and Qwen2.5-Coder (Apache 2.0 for the sizes used; check the model card), Gemma 4 (Gemma terms), Whisper (MIT), CLAP (CC0/Apache per model card), bge-small (MIT).

**Why a sample guide (2026-11-19):** the AEG L6FBJ741N, five Electrolux manuals and the LG WM3400CW
manual all draw their error codes as display graphics, so no text search can find "E21" or "OE" in
them. A landlord's guide types the codes out. With it, the E21 photo plus `Manual: automatic` reads
E21, picks the guide and quotes page 2 (15.8 s on lite). Say on stage that the guide is a sample we
wrote; the AEG manual is kept to show a real manufacturer manual (for example "How do I clean the
drain filter?", p. 29).

