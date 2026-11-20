# HomeFix

**A local assistant for students renting their first apartment**, built for the IEEE AI Hackathon 2026,
Multimodal LLM Challenge ("Build AI we own").

> Hackathon prototype. Not professional or safety advice. In an emergency, call 911.
> Everything runs on one laptop with open-weight models. It works with Wi-Fi off.

Show HomeFix a photo of an error code, play it a beep, ask about your lease or the landlord's guide, or
send a short video. It tells you what is going on and what to do, and shows where it found the answer.
If the answer isn't in your document, it says so. If something sounds dangerous, it says stop first.

## How to run it, step by step

HomeFix runs on **macOS on Apple Silicon** only (M1 or newer). Speech uses `mlx-whisper`, which needs
Apple Silicon, and Ollama must run natively to use the GPU. The first setup takes about 30 to 60
minutes, most of it downloading models (about 14 GB on `full`, 5 GB on `lite`).

### Step 1. Check your Mac and Homebrew

```bash
uname -m            # must print arm64
brew --version      # any version
git --version       # any version
```

If `brew` is missing, install it from <https://brew.sh>. The setup script installs everything else.

### Step 2. Get the code

```bash
git clone https://github.com/meghana2108/Homefix.git
cd Homefix
```

Run every remaining command from inside this `Homefix` folder unless the step says otherwise.

### Step 3. Install everything

```bash
bash scripts/setup_mac.sh
```

This installs what is missing: ffmpeg, the Ollama app, uv, Python 3.11 (through uv), Node 20, the
Python packages (about 1.5 GB, most of it torch) and the web packages. It is safe to run again. It also
creates `.env` from `.env.example`.

If it says `node -v` is not v20, run the `export PATH=...` line it prints, then open a new terminal.

### Step 4. Pick a profile

Open `.env` and set `PROFILE`:

| Your Mac | `PROFILE` | Models |
| --- | --- | --- |
| 16 GB or more | `full` | `qwen3-vl:8b-instruct` (vision), `qwen2.5-coder:7b` (code), Whisper large-v3-turbo |
| 8 GB | `lite` | `qwen3-vl:2b-instruct`, `qwen2.5-coder:3b`, Whisper small.en, one LLM loaded at a time |

Both profiles use CLAP (`laion/clap-htsat-unfused`) for sounds and `bge-small-en-v1.5` for long
documents. `PRACTICE_PACK_DIR` is only needed for the eval (see [Tests and checks](#tests-and-checks)).

### Step 5. Download the models

Open the Ollama app (it shows an icon in the menu bar), then:

```bash
bash scripts/pull_models.sh full --final     # or: lite --final
```

`--final` downloads only the models the profile uses. Without it, the script also downloads the
models we compared against (about 23 GB on `full`, 10 GB on `lite`).

### Step 6. Make the example files and sample manuals

```bash
uv run python scripts/make_samples.py           # our drawn photos, sounds, voice notes, clips and guides
uv run python scripts/fetch_real_samples.py     # real photos, a smoke alarm chirp and public guides; needs the network, slow
```

The first script works offline. It writes the gallery files to `frontend/public/samples/` and the
sample manuals to `data/manuals/` (including the Unit 4B apartment guide the demo uses). Both folders
are gitignored, so every Mac runs these once.

### Step 7. Check the machine

```bash
uv run python scripts/go_no_go.py
```

It runs one question through each model and prints a table with `GO` or `NO-GO` for each one, with
times and memory. Fix any `NO-GO` before going on (see [Troubleshooting](#troubleshooting)).

### Step 8. Start the backend

Terminal 1:

```bash
uv run uvicorn app.api.main:app --port 8000
```

`PROFILE` comes from `.env`. Every model starts loading in the background as soon as the API starts.
Leave this terminal open.

### Step 9. Start the web app

Terminal 2:

```bash
cd frontend && npm run dev
```

Leave this terminal open too. When it prints a `Local:` address on port 5173, go to the next step.

### Step 10. Open it in your browser

Go to **<http://localhost:5173>**.

- **Open HomeFix** (top right) opens the app. The header says "Getting ready: Speech (2 of 5)" while
  the models load, then shows the profile. On the M2 this takes about 29 s from a cold start.
- **Ask about something at home** plays the demo (`#/demo`): eight short scenes with answers recorded
  on the M4. See [The demo](#the-demo).

To try the app, pick an example from **Try an example** (a washer error code, a smoke alarm chirp, a
lease question, a video, a coding task), or type a question and drop in a photo, sound, video or file.

### Step 11. Go offline and check

Turn Wi-Fi off, then, with the backend running:

```bash
bash scripts/offline_check.sh full     # or: lite
```

It checks that the network is unreachable, that every model is on disk, runs the go/no-go test and
asks the API for its health. It must end with `OFFLINE CHECK PASSED`.

### Step 12. Stop the app

Press **Ctrl+C** in both terminals. To free the model's memory too, run
`ollama stop qwen3-vl:8b-instruct` (or `qwen3-vl:2b-instruct` on `lite`).

### Running it again later

Open Ollama, then steps 8 to 10:

```bash
cd Homefix
uv run uvicorn app.api.main:app --port 8000     # terminal 1
cd frontend && npm run dev                      # terminal 2
```

### Without the browser (optional)

Run one question from the terminal through the same code the API uses:

```bash
uv run python -m app.cli "What should I do?" --file frontend/public/samples/washer_display_e21.jpg \
  --manual apartment_guide_unit_4b
```

It prints each step as it happens (`[status]`, `[citation]`, the answer). `--json` prints the raw
events, and `--profile lite` overrides `.env`.

### On a phone (optional)

Camera and microphone need HTTPS. With the backend running and the phone on the same network:

```bash
brew install mkcert                 # once, needs the network
bash scripts/https_dev.sh
```

Open the address it prints on the phone. With Wi-Fi off there is no network between phone and
laptop, so this only works on a local network. See [docs/DEMO.md](docs/DEMO.md).

If something goes wrong, see [Troubleshooting](#troubleshooting).

## What it does

When something in your first apartment beeps, blinks or leaks, you have to work out what it means, find
the manual, and decide whether it is dangerous. The landlord may not answer. HomeFix does that work.
You bring:

| You bring | HomeFix gives you |
| --- | --- |
| A photo | What it shows, a count, or the text on a display (error codes, labels, thermostat readings) |
| A photo of an error code, plus a manual | What the manual says the code means, with the page and the exact words |
| A sound | The top three sound labels with scores ("smoke alarm chirp"), and a warning if it could be an alarm |
| A voice note | The transcript, and an answer to your question about it |
| A document (lease, guide, manual; PDF, text or Word) | An answer with a word-for-word quote and its page, or "the document doesn't contain the answer" |
| A short video | A count, which way something moves, or what happens, with the frames it looked at |
| A coding task | A Python function, tested in a sandbox, with "passed 2 of 2" or what failed |
| Anything that sounds dangerous | A fixed safety message (gas: leave, don't touch a switch) and no repair steps |

Example, from the demo (a photo of a washer display showing E21, with our sample Unit 4B guide):

> **What should I do?**
>
> E21 means the washer cannot drain the water. Turn the washer off and unplug it. Clean the drain pump
> filter behind the small door at the bottom right (see page 3). Then check that the drain hose is not
> kinked.
>
> *Word for word from the document, p. 2 · apartment_guide_unit_4b.pdf:* "E21 - The washer cannot drain
> the water. Turn the washer off and unplug it. Clean the drain pump filter behind the small door at the
> bottom right (see page 3)."

The other demo scenes, each a real answer recorded on the M4 (`full`):

| Question | What came back | Time |
| --- | --- | --- |
| "What is this sound?" + a smoke alarm chirp | Most likely **smoke alarm chirp** (13%), then silence, background noise; "If this could be a smoke or carbon monoxide alarm, don't wait: leave and call 911." | 6.7 s |
| "How many warning lights are on at the end?" + a 6 s clip | 4, with the 16 frames it looked at | 10.2 s |
| "Is there a warranty on the washer?" + the Unit 4B guide | "The document doesn't contain the answer." (it doesn't) | 2.2 s |
| "I smell burning from the outlet behind the fridge" | The fixed safety message for smoke or fire, no repair steps | 0.001 s |
| "Write a function that converts a thermostat temperature from Fahrenheit to Celsius." | The function, passed 2 of 2 examples in the sandbox | 11.2 s |

### Who it is for

**User:** a student in their first apartment, with a beeping appliance and a landlord who isn't
answering.

**The one thing they finish:** show HomeFix the problem (photo, sound, video or question) → read what it
means and what to do, with where that came from → if it's beyond them, press **Make a repair request**:
a dated page with every file fingerprinted, the verified quote, the danger check and a letter to the
landlord they can edit, then print or save as PDF. It is built in the browser; nothing is uploaded.
**Check a file against this request** later shows whether a file was changed.

### How an answer is decided

Fixed rules have the final say. A model can make HomeFix more careful (stop, ask, refuse), never less.
The full design is in [docs/SAFETY.md](docs/SAFETY.md).

- **Danger first.** Every question and voice-note transcript is checked for danger words (gas, sparks,
  smoke, exposed wires, water near an outlet, shocks) before any model runs. A match gets the fixed
  message for that danger and no repair steps. A second check by meaning catches paraphrases ("a weird
  sulfur smell by the oven"); it can only add a stop.
- **Routing is plain code.** `app/router.py` picks the pipeline from the files and the question words in
  about 0 ms. No model decides where a question goes.
- **No verified quote, no answer.** A document answer is shown only if its quote is in the document:
  word for word, or a fuzzy match of at least 92 (`quote_fuzz_threshold`) for quotes of 8 words or
  more. Shorter quotes must match exactly. Every number and code in the answer must also be in the quote.
  If the question asks about an error code ("What does E21 mean?"), the quote must name that code.
- **Displays are read twice.** If the two reads disagree (80 vs 60, E24 vs 624), a third read decides
  by majority. With no majority, HomeFix shows the reads and asks which one is right.
- **It asks instead of guessing** when a question about a display is vague, a code can't be read, or two
  manuals fit.
- **Sounds that might be alarms** get a warning even when the alarm label isn't first.
- **Generated code never runs in the app.** It runs its own examples in a locked-down subprocess (no
  network, temporary folder, 10 s limit) and gets one retry if they fail.

## The demo

The demo page plays real answers that we recorded on the M4, so it never calls a model and works with
Wi-Fi off.

1. Open <http://localhost:5173> and click **Ask about something at home**, then press `F` for full screen.
2. Each scene builds up by itself, one step per second, and ends on the answer. `→`, Space, PageDown or a
   clicker goes to the next scene; pressed while a scene is still building, it finishes that scene
   first. `←` goes back. `1` to `8` jump to a scene. `Esc` opens the live app.
3. The scenes: 1 the problem, 2 photo to manual, 3 sound, 4 video, 5 honesty, 6 danger, 7 code, 8 proof
   (the scores below and our test counts).

Before presenting, with the backend running on the M4:

```bash
uv run python scripts/demo_check.py      # asks one question of each kind, prints seconds and OK / SLOW / FAIL
```

Run it twice; the second run is the warm number. To record the scenes again (backend on `full`):

```bash
uv run python scripts/record_demo.py                 # all six recorded scenes
uv run python scripts/record_demo.py --scene photo   # one scene
```

A scene is saved only if its answer passes the checks in `scripts/record_demo.py` (for example, the
photo answer must quote E21 and the code must pass its examples). The full run sheet, with the M2
backup plan, is in [docs/DEMO.md](docs/DEMO.md).

## Results

Our own run on the organizers' 100-question practice pack, scored with the metrics in
[docs/EVAL.md](docs/EVAL.md). Full tables: [results/summary_full.md](results/summary_full.md) (run
`20261120-1009-full-all`) and [results/summary_lite.md](results/summary_lite.md) (run
`20261119-1404-lite-all`).

The pack is general test data from public datasets (photos, sounds, speech, passages, coding tasks and
short clips). None of it is about apartments. It measures the skills HomeFix is built on: seeing,
hearing, reading, coding and watching video, offline, on our laptops.

| Modality | Metric | `full` (M4, 16 GB) | `lite` (M2, 8 GB) |
| --- | --- | --- | --- |
| Image | count exact | 14/15 | 14/15 |
| Image | other questions (fuzzy) | 8/10 | 9/10 |
| Audio | speech answers (fuzzy) | 8/10 | 6/10 |
| Audio | sound top-1 / top-3 | 8/10 · 9/10 | 8/10 · 9/10 |
| Text | answer match | 15/15 | 14/15 |
| Text | "not in the document" when it isn't | 3/5 (never refused wrongly) | 2/5 (never refused wrongly) |
| Code | pass@1 | 20/20 | 17/20 |
| Video | count / direction / other questions | 2/4 · 2/2 · 7/9 | 1/4 · 2/2 · 2/9 |
| **Total** | hits | **87/100** | **75/100** |

Speed (median, request to final answer, first model load included) and peak memory:

| | Image | Audio | Text | Code | Video | Peak memory |
| --- | --- | --- | --- | --- | --- | --- |
| `full` | 9.2 s | 2.9 s | 3.6 s | 12.7 s | 38.8 s | 7.2 GB |
| `lite` | 14.9 s | 22.7 s | 5.1 s | 24.3 s | 22.5 s | 3.0 GB |

Missed our own targets: image on `full` (9.2 s vs 8 s), video on `full` (38.8 s vs 25 s), audio on
`lite` (22.7 s vs 4 s for sounds and 15 s for speech). These runs were made before the model warm-up
was added (commit `f337823`); see [Limitations](#limitations) for what that changed on the M4.

## Configuration

| Setting | Where | What it does |
| --- | --- | --- |
| `PROFILE` | `.env` | `full` or `lite`: which models and limits to use |
| `PRACTICE_PACK_DIR` | `.env` | Absolute path to the unzipped practice pack, outside the repo. Only the eval and `go_no_go.py` use it |
| `OLLAMA_HOST` | `.env` (default `http://127.0.0.1:11434`) | Where Ollama listens |
| `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` | `.env` (both `1`) | Never download models at runtime |
| `OLLAMA_MAX_LOADED_MODELS` | `.env` (`1`) | `lite`: keep one LLM in memory |
| `VITE_API_URL` | environment, for `npm run dev` (default `http://127.0.0.1:8000`) | Where the web app finds the API |
| `config/profiles/full.yaml`, `lite.yaml` | repo | Models, video frames (16 / 8), `quote_fuzz_threshold: 92`, code timeout (10 s), file limits (4 files, 200 MB, 2 min of video) |
| `config/safety_rules.yaml`, `safety_semantic.yaml` | repo | Danger words and the fixed message for each danger, and the paraphrases checked by meaning |

To try a profile setting without editing the file, the eval takes overrides:
`uv run python -m eval.run --profile full --modality video --set video.frames=12`.

## Tests and checks

```bash
uv run pytest                    # unit and hard-rule tests (825 pass); skips tests marked `model`
uv run pytest -m model           # tests that need a real model (Ollama running)
uv run ruff check .              # lint
cd frontend && npx vitest run    # web unit tests (174 pass)
cd frontend && npm run typecheck
cd frontend && npm run build
```

`tests/test_hard_rules.py` checks the hackathon rules on every run: only `eval/grade.py` reads
`answers.json`, the app has no remote URLs, no practice-pack files or manuals are tracked in git, and
the sound vocabulary is not the ESC-50 class list.

Run the eval (needs `PRACTICE_PACK_DIR`):

```bash
uv run python -m eval.run --profile full --modality all       # every item; or image, audio, text, code, video
uv run python -m eval.run --profile full --modality all --limit 2   # quick check: 2 items per modality
uv run python -m eval.report --run <run_id>                   # writes results/summary_full.md
```

Raw answers go to `results/raw/` (gitignored). Only the summary, which holds numbers and no pack
content, is committed.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Ollama is not running` from `pull_models.sh`, or `ollama: false` in `/api/health` | Open the Ollama app, or run `ollama serve` |
| Answers are very slow, and `setup_mac.sh` warned that Docker owns port 11434 | Docker's Ollama on macOS has no GPU. Stop it (`docker ps`, then `docker stop <id>`) and use the Ollama app |
| `demo_check.py` prints `SLOW` | Ollama's memory grows over a long session. Run `ollama stop qwen3-vl:8b-instruct`, restart the API, run the check again. Quit other apps (Docker Desktop holds several GB) |
| The header stays on "Getting ready" | A model is still loading or failed. Check terminal 1 for an error and `go_no_go.py` for a `NO-GO` |
| `model_unavailable` or `timeout` in an answer | The model isn't pulled or didn't load in 90 s. Run `ollama list`, then `pull_models.sh <profile> --final` |
| The manual list is empty | Run `uv run python scripts/make_samples.py` (writes `data/manuals/`) |
| The demo says "this photo is missing" or "the sound file is missing" | Run `uv run python scripts/fetch_real_samples.py` (needs the network once) |
| The demo says "This scene hasn't been recorded" | Run `uv run python scripts/record_demo.py` with the backend on `full` |
| `node -v` is not v20 after setup | Run the `export PATH=...` line `setup_mac.sh` printed, then open a new terminal |
| Port 8000 or 5173 is busy | Find it with `lsof -iTCP:8000 -sTCP:LISTEN` and stop it. The web app expects the API on 8000 unless you set `VITE_API_URL` |
| Camera or mic doesn't work on a phone | They need HTTPS. Use `bash scripts/https_dev.sh` on the same network |
| `OFFLINE CHECK FAILED` at step 1 | The network is still reachable. Turn Wi-Fi off and unplug Ethernet |

## Limitations

- **It answers only from what you give it.** No manual, no answer from a manual. It asks for one instead
  of guessing.
- **It is not a repair person.** It says what a code means and what the manual says. Anything inside a
  machine is for maintenance.
- **Small models can misread or miscount.** Crowded scenes (more than about 8 objects) and blurry text
  are weak spots. Video counting was 2/4 on `full`.
- **It refuses carefully and misses some refusals.** It never refused an answerable question in our run,
  but said "not in the document" for only 3 of 5 (`full`) and 2 of 5 (`lite`) of the questions it should
  have.
- **Error codes must be printed as text in the manual.** Real manuals often print them as pictures, so a
  code can only be matched when it is typed out, as in a landlord's guide. Our Unit 4B guide is a sample
  we wrote. A code with a space ("E 21") is not matched, and codes written digit first ("4C", "5E") are
  not treated as codes in a question.
- **Video is sampled frames** (16 on `full`, 8 on `lite`). Fast motion between frames can be missed, and
  a clip's sound track is not checked.
- **Sound names come from a fixed vocabulary**, derived from AudioSet. Rare appliance sounds map to the
  nearest generic label, and similar beeps are a close call (it says so).
- **The code check runs only the function's own examples.** Passing them doesn't prove the code is right.
- **The safety check is strict.** "Is this pipe leaking?" about a video of a drip gets the
  water-near-electrics message. We chose stopping too often over missing a real danger.
- **Memory on the M4 is tight since the warm-up change.** With every model loaded, the 16 GB M4 had 14%
  memory free (our run sheet asks for 40%), and the photo + manual answer took 12 to 37 s (target 20 s).
  The demo recordings were made in that state.
- **Apple Silicon and native Ollama only.** Phone use needs HTTPS and the same network as the laptop.
- **It is a hackathon prototype**, not professional or safety advice. In an emergency, call 911.

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#limits-we-name-openly).

## How it is built

```text
app/api/          FastAPI: /api/chat (SSE), /api/health, /api/manuals, /api/mic (WebSocket)
app/pipelines/    One pipeline per input: image, audio, text, code, video, and homefix (photo + manual)
app/text/         Retrieval for long documents (BM25 + bge-small) and the quote check (verify.py)
app/code/         Pulling the function out of the model's reply, and the sandbox
app/media/        ffmpeg conversion: photos, sounds, videos and documents into one format each
app/              Router, safety checks, clarify rules, model memory and warm-up, the CLI
frontend/         React + TypeScript (Vite): the app, the front page and the #/demo page
eval/             Practice-pack runner, graders and report
config/           Profiles, safety rules, intent examples, sound vocabularies
scripts/          Setup, model download, samples, go/no-go, offline check, demo check and recorder
docs/             Plan, architecture, models, eval, safety, demo, risks, decisions, assets
tests/            Backend tests, including the hard-rule tests
```

Browser → `POST /api/chat` (files and question) → convert → danger check → router → one pipeline →
Ollama (vision or code model), mlx-whisper or CLAP → checks (quote, reads, sandbox) → a stream of
server-sent events back to the browser. No database, and no network calls at runtime.

| Module | Role |
| --- | --- |
| `app/safety.py`, `app/safety_semantic.py` | Danger words, then danger by meaning; fixed messages |
| `app/router.py` | Picks the pipeline and question type from the files and words (rules, no model) |
| `app/pipelines/image.py` | Describe, count and read photos; the danger look; read twice, majority of three |
| `app/pipelines/homefix.py` | A photo of an error code plus a chosen manual: read the code, find it in the manual, quote it |
| `app/pipelines/audio.py` | Speech (Whisper) or sound labels (CLAP), with the possible-alarm warning |
| `app/pipelines/text.py`, `app/text/verify.py` | Document answers and the quote check |
| `app/pipelines/code.py`, `app/code/sandbox.py` | Write a function, run its examples in a subprocess, retry once |
| `app/pipelines/video.py` | Sample frames, then count, follow motion or answer |
| `app/clarify.py`, `app/intent.py` | When to ask instead of guessing |
| `app/models/memory.py`, `app/warmup.py` | Which models stay loaded, swapping in the coder, the start-up warm-up |

| API route | Purpose |
| --- | --- |
| `POST /api/chat` | Question, files (up to 4) and an optional `manual_id` → a stream of events |
| `GET /api/health` | Profile, Ollama status, loaded models and warm-up progress |
| `GET /api/manuals` | The manuals in `data/manuals/` |
| `WS /api/mic` | Live microphone: 3 s chunks in, partial transcripts out |

`/api/chat` streams these events: `status` (one per stage), `token`, `transcript`, `sound_labels`,
`frames`, `citation`, `code_result`, `clarify`, `refusal`, `error` and `final`. A `refusal` has one of
these reasons: `safety`, `unsupported_file`, `empty_input`, `too_large`, `no_document`,
`not_in_document`, `model_unavailable`, `timeout`. The names are kept the same in `app/contracts.py`
and `frontend/src/contract.ts` by `tests/test_contract_sync.py`.

More: [Plan](docs/PLAN.md) · [Architecture](docs/ARCHITECTURE.md) · [Models](docs/MODELS.md) ·
[Eval](docs/EVAL.md) · [Safety](docs/SAFETY.md) · [Demo](docs/DEMO.md) · [Risks](docs/RISKS.md) ·
[Decisions](docs/DECISIONS.md) · [Assets](docs/ASSETS.md)

## Team

| Name | Built |
| --- | --- |
| Meghana R | Image, text and code pipelines, the backend, the quote check, the HomeFix manuals; runs the `full` profile on the M4 |
| Akshayaa Mahesh | Audio and video pipelines, the web app, the eval framework; runs the `lite` profile on the M2 |

## Credits and licenses

Our code is MIT ([LICENSE](LICENSE)). Models and data keep their own licenses; every asset, its source
and its license is listed in [docs/ASSETS.md](docs/ASSETS.md).

- **Models:** Qwen3-VL and Qwen2.5-Coder (through Ollama), Whisper (mlx-community conversions), CLAP
  (LAION), bge-small-en-v1.5 (BAAI). Why we chose them: [docs/MODELS.md](docs/MODELS.md).
- **Sound vocabulary:** category names from the [AudioSet ontology](https://github.com/audioset/ontology)
  (Google, CC BY-SA 4.0).
- **Real photos and the smoke alarm chirp:** Wikimedia Commons, with each author and license in
  `docs/ASSETS.md`.
- **Public guides:** US EPA, "A Brief Guide to Mold, Moisture, and Your Home", and US CPSC, "Carbon
  Monoxide: The Invisible Killer".
- **Real power data:** UCI "Individual household electric power consumption" (G. Hébrail, A. Bérard),
  CC BY 4.0.
- **Practice pack:** from the hackathon organizers. It is never stored in this repository.
- Everything else (the drawn error displays, beeps, voice notes, clips, the Unit 4B guide and the other
  sample manuals) was made by us with the scripts in `scripts/`.
