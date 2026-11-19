# Plan

Summarised from the hackathon brief (Multimodal LLM Challenge, "Build AI we own") and our
docs: [TEAM.md](TEAM.md), [ARCHITECTURE.md](ARCHITECTURE.md), [RISKS.md](RISKS.md).

## Why this approach

The random-item checklist is 30% of the score and is run with Wi-Fi off, so everything has to
run on our own laptops with open-weight models. One small vision model plus small specialist
models (Whisper, CLAP, bge-small) fit in 16 GB and 8 GB, which one big multimodal model does not.
Plain code, not the model, makes the calls that must be right every time: the safety filter,
the quote check on text answers and the pass/fail on generated code. The renter story
(beep, error code, manual) gives judges a demo they understand in seconds.

## Scope (cut to finish by Thu Nov 19, 22:00 tag; 23:59 hard deadline)

Keep (P0/P1, never cut):
- 5 pipelines callable from `python -m app.cli`: image (describe, count, read text), audio
  (transcribe + answer, or top-3 sound labels), text (answer with a verified quote and page, or
  refuse), code (write a function, run its doctests in a sandbox, retry once), video (16 frames
  on `full`, 8 on `lite`).
- Safety pre-filter: gas, sparks, smoke/fire, exposed wires, water near electrics, shock. It
  returns the fixed message from `config/safety_rules.yaml` before any model runs.
- Eval harness with real numbers for both profiles (`results/summary_full.md`, `summary_lite.md`).
- Web UI over SSE: chat, file attachments, every event type, latency badge.
- `scripts/offline_check.sh` passing on the M4 with Wi-Fi off.

Keep if green by the 14:00 freeze (P2):
- HomeFix manual layer: photo of an error code + a selected manual → manual answer with page.
  If it's not ready, demo it from the CLI.
- Live mic over WebSocket, PWA on a phone.

Cut: bake-offs beyond the top 2 candidates per role, the 7B coder swap, fine-tuning, any cloud
fallback, user accounts, true temporal video models (we sample frames).

## Expected results

| Input | Expected output |
|---|---|
| Recording of a washer's end-of-cycle beep | Top-3 sound labels with scores, "washing machine beeping" (from `appliances.txt`) in the top 3 |
| Photo of a display showing "E21", washer manual selected | Reads "E21"; answers from the manual with a word-for-word quote and its page number |
| Question the selected manual doesn't cover | "The document doesn't contain the answer." No guess |
| "I smell burning plastic from the dryer" | The fixed safety message, no repair steps, no model call |
| "How many mugs are on the shelf?" + photo | A number first ("4"), then one line of explanation; "I can't tell" if too blurry |
| "Write a function that averages the fridge's watts per hour" + `data/smartplug_fridge.csv` | Python function, its doctests run in a subprocess, pass/fail badge |
| 30 s clip of the drum not turning | Description built from timestamped frames ("Frame k at t=…s") |
| A `.heic` photo or `.m4a` voice note | Converted by ffmpeg and answered; an unsupported type gets `refusal: unsupported_file`, never a crash |

Known traps:
- **The safety regex over-matches today.** Checked on 2026-11-18: "smoke detector keeps
  chirping", "fire alarm battery is low", "my Fire TV stick froze", "burnt toast smell" and
  "water dripping from the outlet hose of the washer" all trigger the safety message. The
  outlet-hose case is a normal washer question. Benign look-alike tests are needed before the
  filter ships.
- Count answers: the grader takes the first integer, and number words count ("four" = 4). Say
  the number first.
- Text: every number in the answer must appear in the quote. SQuAD 2.0-style items are
  unanswerable on purpose, so refusing them is the correct answer.
- Sounds: the vocabulary is the AudioSet-derived list (379 labels), never the ESC-50 classes
  (hard rule 3). Rare appliance sounds may map to the nearest generic label.
- Bake-off: practice items used as few-shot examples must not also be scored.
- Machines: Docker owns port 11434 on the M4 (no GPU). Stop it and use native Ollama.

## Build order

### Tech stack

- Frontend: React + Vite (Node 20) for chat, attachments, status chips, citation card, code
  result panel and sound bars. Builds against `mock_server/` until the backend is ready
  (`VITE_API_URL`).
- API: FastAPI + Uvicorn, `sse-starlette` for streamed events, `python-multipart` for uploads,
  `pydantic-settings` for profiles and env.
- Media: ffmpeg, OpenCV, Pillow, PyMuPDF and python-docx normalise every upload (JPEG ≤ 1280,
  16 kHz mono WAV, H.264 ≤ 720p, text with page markers).
- Models: Ollama (vision brain `qwen3-vl:8b` / `:2b`, coder `qwen2.5-coder:3b`), mlx-whisper
  (large-v3-turbo, small.en), CLAP via transformers, bge-small via sentence-transformers.
- Text grounding: full document under 6,000 tokens, otherwise BM25 + bge-small top 5. The
  rapidfuzz quote verifier (threshold 92) decides whether an answer is shown.
- Code check: generated function's doctests in a subprocess, 10 s timeout, temp dir, no network.
- Eval and tests: pytest (unit + hard rules), `eval/` with jiwer and rapidfuzz graders.
- Storage: files on disk only. Manuals in `data/manuals/` and pack data outside the repo, both
  gitignored. No database.

Architecture: browser → FastAPI `/api/chat` → ffmpeg normalise → safety filter → rule-based
router → modality pipeline → local models → quote verifier / code self-check → SSE events →
browser. The CLI, the API and the eval harness call the same pipeline functions.

Built so far (commits `beaefad`, `46f636d`): `.gitignore` with the hard rules, both profiles,
safety rules, sound vocabulary, synthetic smart-plug CSV, setup / model-pull / go-no-go /
offline scripts, docs and 3 passing hard-rule tests. Still to build: everything under `app/`
(settings, Ollama client, memory manager, router, safety module, 5 pipelines, API, CLI),
`mock_server/`, `eval/` and `frontend/`. Those folders hold only empty `__init__.py` files.

| When | Goal |
|---|---|
| Wed Nov 18, 22:30 | M0: go/no-go prints GO on both Macs |
| Wed Nov 18, 23:30 | M1: API contract agreed; mock server streams every event type |
| Thu Nov 19, 10:00 | M2: all 5 pipelines work from `python -m app.cli` |
| Thu Nov 19, 12:00 | M3: eval harness produces numbers |
| Thu Nov 19, 13:30 | M4: UI runs end to end on the real backend |
| Thu Nov 19, 14:00 | **Feature freeze.** M5: HomeFix manual layer ships only if done |
| Thu Nov 19, 22:00 | M6: offline check passes, final eval numbers in README, tag `v1.0-submission` |

The hour-by-hour schedule and owners are in [TEAM.md](TEAM.md#hour-by-hour). If we're behind,
drop P3, then the PWA, then the live mic. Never drop P0.

## Risks

Full list with likelihood and impact: [RISKS.md](RISKS.md).

- Network call at runtime (disqualifying): `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
  Ollama on localhost; run `offline_check.sh` with Wi-Fi off on both Macs.
- Hard-rule breach (pack data committed, `answers.json` read outside `eval/grade.py`):
  `tests/test_hard_rules.py` runs before every merge.
- Sound vocabulary called an ESC-50 lookup: it's generated from AudioSet by a script; confirm
  with organizers (DECISIONS.md D3).
- Brain too slow or out of memory: drop to `qwen3-vl:4b` on `full`; on `lite`, one LLM at a
  time and `num_ctx` 4096.
- Safety filter blocks normal questions: benign look-alike tests (see Known traps).
- Verifier refuses correct answers: tune the threshold on the 20 practice text items; re-prompt
  once for a shorter quote.
- Model crashes mid-demo: error event, other modalities keep serving; switch to the M2 or the
  backup video.
- Running out of time (high likelihood): freeze at 14:00, cut in priority order, tag by 22:00.
