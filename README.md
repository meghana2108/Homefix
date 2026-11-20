# HomeFix 🔧

**A private, fully local multimodal assistant for students renting their first apartment, built for the moment an appliance breaks.**
Play the beep, snap the error code, ask your manual, upload a video of the drum not spinning. HomeFix answers on your own laptop with open-weight models, **with Wi-Fi off**.

> IEEE AI Hackathon 2026, Multimodal LLM Challenge ("Build AI we own"). Team: Meghana R, Akshayaa Mahesh.

## What it does
| Input | Capability |
|---|---|
| 🖼️ Image | Describe a photo, count objects, read text (error codes, labels) |
| 🔊 Audio | Transcribe speech and answer questions; identify sounds (beeps, grinding, alarms) |
| 📄 Text | Answer from a document with a verified word-for-word quote and page, or say it isn't there |
| 💻 Code | Write a Python function, run its examples in a sandbox, retry once on failure |
| 🎬 Video | Describe a short clip: count, follow motion, read signs |
| ⚠️ Safety | Gas, sparks, smoke, exposed wires, water near outlets, shocks → a fixed message for that danger (gas: leave, don't touch a switch), before any model runs |

## Hardware
| Profile | Machine | Brain | Coder | Speech | Notes |
|---|---|---|---|---|---|
| `full` | MacBook Pro M4, 16 GB | `qwen3-vl:8b-instruct` | `qwen2.5-coder:7b` (swapped in) | Whisper large-v3-turbo | Demo machine |
| `lite` | MacBook Air M2, 8 GB | `qwen3-vl:2b-instruct` | `qwen2.5-coder:3b` (swapped in) | Whisper small.en | Proves it runs on 8 GB; one LLM loaded at a time |

Both profiles use CLAP (`laion/clap-htsat-unfused`) for sounds and `bge-small-en-v1.5` for long manuals.
Why these models, and what we didn't test: [docs/MODELS.md](docs/MODELS.md).

Requires Apple Silicon (mlx-whisper) and **native** Ollama (not Docker: no GPU on macOS).

## Quickstart
```bash
bash scripts/setup_mac.sh            # ffmpeg, Ollama, uv, Python 3.11, Node 20, deps
cp .env.example .env                 # set PRACTICE_PACK_DIR and PROFILE
bash scripts/pull_models.sh full     # or: lite   (~23 GB / ~10 GB incl. bake-off candidates)
uv run python scripts/go_no_go.py    # GO / NO-GO table
uv run pytest                        # unit + hard-rule tests
```
Once per Mac, make the example files and sample manuals:
```bash
uv run python scripts/make_samples.py            # our drawn photos, sounds, voice notes, clips and guides
uv run python scripts/fetch_real_samples.py      # real photos, a chirp and guides (Wikimedia Commons, EPA, CPSC); slow
```
Run the app with Ollama open. Terminal 1 (backend; `PROFILE` comes from `.env`):
```bash
uv run uvicorn app.api.main:app --port 8000
```
Terminal 2 (UI at http://localhost:5173):
```bash
cd frontend && npm install && npm run dev
```
Then turn Wi-Fi off and check nothing reaches the network: `bash scripts/offline_check.sh full`.
Run the eval: `uv run python -m eval.run --profile full --modality all`, then
`uv run python -m eval.report --run <run_id>`. Phone use: see [docs/DEMO.md](docs/DEMO.md).

## Results
Our own test run on the 100-item practice pack, scored with the metrics in [docs/EVAL.md](docs/EVAL.md).
Full tables: [results/summary_full.md](results/summary_full.md) (run `20261120-1009-full-all`) and
[results/summary_lite.md](results/summary_lite.md) (run `20261119-1404-lite-all`).

| Modality | Metric | `full` (M4, 16 GB) | `lite` (M2, 8 GB) |
|---|---|---|---|
| Image | count exact | 14/15 | 14/15 |
| Image | read / describe (fuzzy) | 8/10 | 9/10 |
| Audio | speech transcript (fuzzy) | 8/10 | 6/10 |
| Audio | sound top-1 / top-3 | 8/10 · 9/10 | 8/10 · 9/10 |
| Text | answer match | 15/15 | 14/15 |
| Text | "not in the document" when it isn't | 3/5 (never refused wrongly) | 2/5 (never refused wrongly) |
| Code | pass@1 | 20/20 | 17/20 |
| Video | count / direction / questions | 2/4 · 2/2 · 7/9 | 1/4 · 2/2 · 2/9 |
| **Total** | hits | **87/100** | **75/100** |

Speed (median, request to final answer, first model load included) and memory:

| | Image | Audio | Text | Code | Video | Peak memory |
|---|---|---|---|---|---|---|
| `full` | 9.2 s | 2.9 s | 3.6 s | 12.7 s | 38.8 s | 7.2 GB |
| `lite` | 14.9 s | 22.7 s | 5.1 s | 24.3 s | 22.5 s | 3.0 GB |

Missed our own targets: image on `full` (9.2 s vs 8 s), video on `full` (38.8 s vs 25 s), audio on `lite`
(22.7 s vs 4 s for sounds and 15 s for speech). `lite` video uses 8 frames instead of 16 and the 2b model, so it is
faster and less accurate.

## Docs
[Plan](docs/PLAN.md) · [Team](docs/TEAM.md) · [Architecture](docs/ARCHITECTURE.md) · [Models](docs/MODELS.md) · [Eval](docs/EVAL.md) · [Demo](docs/DEMO.md) · [Risks](docs/RISKS.md) · [Decisions](docs/DECISIONS.md) · [Assets](docs/ASSETS.md)

## Limits
- **It answers only from what you give it.** No manual, no answer from a manual. It asks for one instead of guessing.
- **It is not a repair person.** It says what a code means and what the manual says. Anything inside a machine is for maintenance.
- **Small models, so it can misread or miscount.** Crowded scenes (more than about 8 objects) and blurry text are weak spots.
  Measured: video counting 2/4 on `full`.
- **It refuses carefully, and misses some refusals.** It never refused an answerable question in our run, but it
  said "not in the document" for only 3 of 5 (`full`) and 2 of 5 (`lite`) of the questions it should have.
- **Error codes must be printed as text in the manual.** Real manuals often print them as pictures. A code with a
  space ("E 21") is not matched. Our Unit 4B guide is a sample we wrote.
- **Video is sampled frames.** Fast motion between frames can be missed, and a clip's sound track is not checked.
- **Sound names come from a fixed vocabulary.** Rare appliance sounds map to the nearest generic label, and similar
  beeps are a close call (it says so).
- **The code check runs only the function's own examples**, in a sandbox. Passing them doesn't prove the code is right.
- **Slow spots:** video on `full` and sounds on `lite` (see Results).
- **Apple Silicon and native Ollama only.** Phone use needs HTTPS and the same Wi-Fi network as the laptop.
- **It is a hackathon prototype**, not professional or safety advice. In an emergency, call 911.

More detail: [ARCHITECTURE.md § Limits](docs/ARCHITECTURE.md#limits-we-name-openly).

## License
MIT for our code. Models and datasets keep their own licenses ([docs/ASSETS.md](docs/ASSETS.md)).
