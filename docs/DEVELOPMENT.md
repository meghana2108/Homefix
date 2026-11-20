# Development

Configuration, tests, troubleshooting and how HomeFix is built. Back to the [README](../README.md).

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

More: [Plan](PLAN.md) · [Architecture](ARCHITECTURE.md) · [Models](MODELS.md) ·
[Eval](EVAL.md) · [Safety](SAFETY.md) · [Demo](DEMO.md) · [Risks](RISKS.md) ·
[Decisions](DECISIONS.md) · [Assets](ASSETS.md)
