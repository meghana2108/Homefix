# HomeFix: whole-app design

Date: 2026-11-18 · Status: approved design, ready to plan

Source docs: [PLAN.md](../../PLAN.md) · [TEAM.md](../../TEAM.md) ·
[ARCHITECTURE.md](../../ARCHITECTURE.md) · [EVAL.md](../../EVAL.md) · [MODELS.md](../../MODELS.md) ·
[RISKS.md](../../RISKS.md) · [DEMO.md](../../DEMO.md) · [DECISIONS.md](../../DECISIONS.md) ·
[ASSETS.md](../../ASSETS.md) · hackathon problem statement (PDF, not in the repo).

## Intent

A student renting their first apartment hears a beep, sees "E21" on the washer, and has to
choose: call the landlord, pay for a visit, or fix it in two minutes. Today they search the
web, can't find the manual, and guess. HomeFix answers from their own laptop with Wi-Fi off. It
listens to the beep, reads the error code, answers from the manual with a quoted page, writes
small scripts for smart-plug data, and looks at a video of the broken part. If the situation
sounds dangerous, it says stop instead of giving repair steps.

For the hackathon, the same app must pass a random-item checklist across five modalities
(image, audio, text, code, video) on both laptops (30% of the score), run a live demo end to
end (25%), and let us explain each model choice and its limits (20%).

What changes: today the repo has Phase 0 only (profiles, safety rules, sound vocabulary,
scripts, 3 tests). `app/`, `eval/`, `mock_server/` hold empty `__init__.py` files and
`frontend/` has only `public/icons/`. This design covers everything else, for both people,
split so that no two people edit the same file.

## Goals

- `POST /api/chat` (multipart) streams SSE events for all 5 modalities, the safety message and
  every refusal. Event types are fixed in `app/contracts.py` (section "Contract").
- `python -m app.cli` runs the same pipeline functions from the terminal, printing events.
- `python -m eval.run --profile <full|lite> --modality <m|all>` calls the same pipeline
  functions and writes `results/raw/<run_id>.jsonl`; `python -m eval.report` writes
  `results/summary_<profile>.md`.
- Five pipelines, each a module with the same entry point `run(req, ctx)`:
  - `app/pipelines/image.py`: describe, count (number first), read text, free Q&A.
  - `app/pipelines/audio.py`: speech → transcript + answer; non-speech → top-3 sound labels.
  - `app/pipelines/text.py`: answer from a document with a verified quote and page, or refuse
    with "The document doesn't contain the answer."
  - `app/pipelines/code.py`: write one Python function, run its doctests in a subprocess, retry once.
  - `app/pipelines/video.py`: 16 frames (`full`) / 8 frames (`lite`) labelled "Frame k at t=…s".
- `app/pipelines/homefix.py` (P2): photo of an error display + selected manual → code read from
  the photo → manual answer with quote and page.
- Safety pre-filter `app/safety.py` runs on the typed message, the Whisper transcript, and the
  top-1 sound label, before any repair answer is shown. Benign look-alikes are let through.
- Rule-based router `app/router.py` (no model call, < 5 ms).
- Memory manager `app/models/memory.py`: on `full` all models resident; on `lite` only one LLM
  loaded at a time, swap reported as a `status` event with `ms`.
- React + Vite + TypeScript UI in `frontend/`: chat, attachments, drag and drop, manual picker,
  status chips, latency badge, citation card, code result panel, sound bars, frame strip.
- `mock_server/` serves the same contract with canned events so the UI is built before the
  backend.
- Both profiles pass `scripts/offline_check.sh` with Wi-Fi off.

## Non-goals

- Fine-tuning, cloud fallback, user accounts, chat history across reloads, a database.
- True temporal video models. We sample frames.
- Bake-offs beyond the top 2 candidates per role; the 7B coder swap.
- Multi-turn memory. Each request is answered on its own (the UI keeps the visible log only).
- Mixed-modality reasoning in one request (e.g. "compare this photo with this audio"). One
  request = one modality (see Router).
- Generating the TypeScript contract from Python. It is hand-mirrored and a test checks it.

## Anti-goals (a failure even if the feature works)

- Any network call at runtime other than to `127.0.0.1` / `localhost`.
- A text (document) answer shown without a verified quote.
- A repair step shown after the safety filter matched.
- Generated code run in the main process, or with network access, or without a timeout.
- Practice pack content (`items.json`, `answers.json`, its media) in git, in a test fixture, in
  a doc, or in a commit message. Pack items are referred to by ID only.
- Any file other than `eval/grade.py` reading `answers.json`.
- The ESC-50 class list used as the sound vocabulary.
- A crash (HTTP 500, dead SSE stream, frozen UI) on any file a judge drops. Every failure ends
  in a `refusal` or `error` event followed by `final`.
- Two people editing the same file on different branches.

## Constraints

- **Deadline:** feature freeze Thu Nov 19, 14:00; tag `v1.0-submission` Thu Nov 19, 22:00. The
  brief's code deadline is Fri Nov 20; Friday is buffer for rehearsal and re-running eval only.
  A finished workflow beats an ambitious one that doesn't run. Priority: P0 (5 pipelines,
  safety, API, eval, UI, offline) > P1 > P2 (manual layer, live mic, PWA). Cut order when late:
  P3, then PWA, then live mic. Never cut P0.
- **Machines:** M4 16 GB runs `full`, M2 8 GB runs `lite`. Apple Silicon only (mlx-whisper).
  Native Ollama on `127.0.0.1:11434` (not Docker).
- **Memory:** `full` target ≤ 11 GB of models resident. `lite`: one Ollama LLM at a time
  (`OLLAMA_MAX_LOADED_MODELS=1`); Whisper large-v3-turbo is never loaded on `lite`.
- **Stack (already locked in `pyproject.toml` / `uv.lock`):** Python 3.11, FastAPI, sse-starlette,
  python-multipart, pydantic 2, pydantic-settings, ollama, mlx-whisper, transformers, torch,
  sentence-transformers, librosa, soundfile, pymupdf, python-docx, rank-bm25, rapidfuzz,
  opencv-python-headless, pillow, jiwer, psutil, pytest, pytest-asyncio, ruff. Frontend: Node 20,
  React 18, Vite 5, TypeScript 5. No new Python dependency after Task 0 of the plan.
- **Tooling:** tests `uv run pytest` (skips `@pytest.mark.model`), `uv run pytest -m model` for
  real-model tests, lint `uv run ruff check .`, frontend `npm run typecheck` (`tsc --noEmit`)
  and `npm run build`. No Python type checker.
- **Offline:** `app/settings.py` sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` with
  `os.environ.setdefault` before any model library is imported.
- **Hard rules:** CLAUDE.md rules 1–5 (pack data, `answers.json`, manuals, sound vocab, network).
- **Latency targets** (measured by eval, reported, not pass/fail gates):

  | Request | `full` p50 | `lite` p50 |
  |---|---|---|
  | First `status` event after POST | ≤ 0.3 s | ≤ 0.3 s |
  | Safety match → `final` | ≤ 0.1 s | ≤ 0.1 s |
  | Image question | ≤ 8 s | ≤ 15 s |
  | Sound label (≤ 10 s clip) | ≤ 3 s | ≤ 4 s |
  | Speech (30 s clip) transcript + answer | ≤ 8 s | ≤ 15 s |
  | Text question | ≤ 12 s | ≤ 20 s |
  | Code incl. self-check | ≤ 20 s | ≤ 35 s (incl. swap) |
  | Video (30 s clip) | ≤ 25 s | ≤ 40 s |

## Approaches considered (contract sync)

The architecture itself was settled in ARCHITECTURE.md. The open build choice was how the
shared contract stays in sync between Python and the TypeScript UI.

| | Approach | Trade-off |
|---|---|---|
| **A (picked)** | `app/contracts.py` (pydantic) is the source. `frontend/src/contract.ts` is hand-mirrored. `tests/test_contract_sync.py` parses the TS file and fails if event types, refusal reasons or stages differ. `mock_server/` imports `app/contracts.py`. | ~15 min, no extra tooling; mirroring is manual but checked. |
| B | Generate TS from pydantic JSON Schema with `json-schema-to-typescript`. | No hand-mirror, but a new npm build step at midnight and awkward generated unions. |
| C | Shared JSON Schema read by both. | Neither side gets real types without codegen; B with extra steps. |

Picked A, agreed in conversation on 2026-11-18.

## Ownership and no-conflict rules

Every file has one owner. Only the owner edits it after it exists. If you need a change in
someone else's file, message them; they make it.

**Day-one stubs.** Meghana's first backend task creates every shared seam as a working stub, so
both people start from committed files they then own:
- `app/pipelines/{image,audio,text,code,video,homefix}.py`: each `run()` yields
  `status(stage="generating")`, then `refusal(reason="model_unavailable", message="This
  pipeline isn't built yet.")`, then `final`. Owners replace the body.
- `app/api/mic.py`: empty `APIRouter`, already included by `app/api/main.py`.
- Eval seams are created by **Akshayaa's** first eval task (not Meghana's), because she owns
  `eval/`: `eval/types.py` (`PackItem`, `GradeResult`) and `eval/graders/{image,audio,text,code,
  video}.py`, each `grade(item, ours, ref) -> GradeResult` returning
  `GradeResult(item_id=item.id, metric="todo", score=0.0, hit=False, note="not built")`.
  Meghana's graders start after that task is on `main` (they are due Thu 12:00, the stub task
  lands Wed night).
- `config/profiles/{full,lite}.yaml`: every key any task needs is added on day one (listed in
  "Profile keys"). After that only Meghana edits them.
- `pyproject.toml` / `uv.lock`: no new dependency is expected. If one is, Meghana adds it on
  `main` and the other person rebases.

| Area | Owner | Files |
|---|---|---|
| Contract (Python) | Meghana | `app/contracts.py` |
| Contract (TS mirror) | Akshayaa | `frontend/src/contract.ts` |
| Contract sync test | Meghana | `tests/test_contract_sync.py` |
| Settings, profiles | Meghana | `app/settings.py`, `config/profiles/*.yaml` |
| Ollama client, memory, embeddings | Meghana | `app/models/ollama_client.py`, `app/models/memory.py`, `app/models/embeddings.py` |
| Whisper, CLAP loaders | Akshayaa | `app/models/whisper.py`, `app/models/clap.py` |
| Safety | Meghana | `app/safety.py`, `config/safety_rules.yaml` |
| Router | Meghana | `app/router.py` |
| Media conversion | Akshayaa | `app/media/convert.py` |
| Pipelines image / text / code / homefix | Meghana | `app/pipelines/{image,text,code,homefix}.py`, `app/text/` (verifier, retrieval), `app/code/` (extract, sandbox) |
| Pipelines audio / video | Akshayaa | `app/pipelines/{audio,video}.py`, `app/video/` (frames, cache) |
| API | Meghana | `app/api/main.py`, `app/api/chat.py`, `app/api/manuals.py` |
| Live mic | Akshayaa | `app/api/mic.py` |
| Orchestrator (convert → empty check → safety → router → pipeline; used by API, CLI and eval) | Meghana | `app/orchestrate.py` |
| CLI | Meghana | `app/cli.py` |
| Eval framework | Akshayaa | `eval/run.py`, `eval/report.py`, `eval/pack.py`, `eval/grade.py` |
| Graders image / text / code | Meghana | `eval/graders/{image,text,code}.py` |
| Graders audio / video | Akshayaa | `eval/graders/{audio,video}.py` |
| Mock server | Akshayaa | `mock_server/server.py`, `mock_server/scripts.py` |
| Frontend shell | Akshayaa | everything in `frontend/` except the two files below |
| Citation card, code panel | Meghana | `frontend/src/components/CitationCard.tsx`, `frontend/src/components/CodeResultPanel.tsx` (created as stubs by Akshayaa's shell task, then owned by Meghana) |
| Tests | owner of the code under test | `tests/test_<module>.py`, one file per module |
| Docs | Meghana: README, MODELS, DECISIONS, ARCHITECTURE, PLAN, `docs/superpowers/`; Akshayaa: ASSETS, DEMO, EVAL | |

`eval/grade.py` is the only file that reads `answers.json` (hard rule 2). It loads the reference
for an item and passes it to `eval/graders/<modality>.py::grade(item, ours, ref)`. Graders never
open files. `tests/test_hard_rules.py` is extended to scan every `.py` file in the repo
(except itself) and allow the string `answers.json` only in `eval/grade.py`.

Git: branches `feat/<area>` (e.g. `feat/text`, `feat/audio`). Merge to `main` only with
`uv run pytest` green. Each person merges their own branch; rebase on `main` first. The two
files `app/contracts.py` and `frontend/src/contract.ts` change together: a contract change is
**one PR on a `contract/<change>` branch that edits both files**, written by whoever needs the
change and approved by both owners before merge. This is the only exception to single-file
ownership, and it keeps `main` green (`tests/test_contract_sync.py` passes on that one PR).
The contract is frozen at M1 (Wed 23:30); after that, changes need both people to agree in chat.

## Contract (`app/contracts.py`)

Python is the source. All events are pydantic models with a literal `type` field. SSE frames
are `event: <type>` + `data: <json>`.

```python
Stage = Literal["converting", "safety_check", "routing", "loading_model", "transcribing",
                "labeling_sounds", "extracting_frames", "retrieving", "generating",
                "verifying", "running_code"]
RefusalReason = Literal["safety", "unsupported_file", "empty_input", "too_large",
                        "no_document", "not_in_document", "model_unavailable", "timeout"]
Modality = Literal["image", "audio", "text", "code", "video", "homefix", "none"]
QuestionType = Literal["describe", "count", "read", "qa", "motion", "speech", "sound",
                       "doc_qa", "code_gen", "manual_lookup", "none"]
```

| Event | Fields (type, meaning, example) |
|---|---|
| `status` | `stage: Stage`; `detail: str \| None` ("loading qwen2.5-coder:3b"); `ms: int \| None` (time the stage took, e.g. swap 6400) |
| `token` | `text: str` (one streamed chunk of the brain's answer, "There are ") |
| `transcript` | `text: str` (full Whisper transcript); `seconds: float` (audio length, 12.4) |
| `sound_labels` | `labels: list[{label: str, score: float}]` (exactly 3, score 0–1, sorted desc); `is_speech: bool` |
| `frames` | `timestamps: list[float]` (seconds of each sampled frame, `[0.0, 1.9, …]`) |
| `citation` | `quote: str` (verbatim span from the document); `page: int \| None` (1-based, `None` for .txt/.md); `source: str` ("washer_manual.pdf"); `score: float` (verifier match 0–100) |
| `code_result` | `code: str`; `passed: bool`; `tests_run: int`; `failures: int`; `output_tail: str` (last 1,500 chars of doctest output); `attempts: int` (1 or 2) |
| `refusal` | `reason: RefusalReason`; `message: str` (shown verbatim); `category: str \| None` (safety category, e.g. "gas") |
| `error` | `stage: Stage`; `message: str` (one plain sentence); `retryable: bool` |
| `final` | `answer: str` (the complete text the UI shows as the answer, "" after a refusal); `modality: Modality`; `question_type: QuestionType`; `latency_ms: int`; `profile: "full" \| "lite"`; `model: str \| None` ("qwen3-vl:8b") |

Every stream ends with exactly one `final`. A `refusal` or `error`, when present, comes right
before `final`. Text-modality streams never emit `token` (the answer must be verified first).

Pipeline interface (also in `app/contracts.py`):

```python
@dataclass
class Attachment:
    path: Path | None   # normalized file on disk (after convert.py); None for an inline
                        # document built by eval from text inside a pack item
    kind: Literal["image", "audio", "video", "document", "data"]
    original_name: str  # "IMG_2041.heic"
    pages: list[str] | None = None   # documents only: text per page

@dataclass
class PipelineRequest:
    message: str                      # user text, stripped; may be ""
    attachments: list[Attachment]
    question_type: QuestionType       # from the router
    manual_id: str | None = None      # stem of a file in data/manuals/

@dataclass
class Ctx:
    profile: Profile                  # parsed config/profiles/<name>.yaml
    memory: MemoryManager
    deadline_s: float = 90.0          # per-model-call timeout

Event = Status | Token | Transcript | SoundLabels | Frames | Citation | CodeResult | Refusal | Error | Final

def run(req: PipelineRequest, ctx: Ctx) -> Iterator[Event]: ...   # every pipeline module
```

Orchestrator (`app/orchestrate.py`, Meghana):

```python
def handle(message: str, files: list[Path], manual_id: str | None, ctx: Ctx,
           original_names: list[str] | None = None,
           attachments: list[Attachment] | None = None) -> Iterator[Event]: ...
```
Runs the whole "Request flow" below and adds `latency_ms` to `final`. `attachments`, when given,
skips conversion (eval uses it for inline documents). The API, `app/cli.py` and `eval/run.py`
all call `handle()`, so eval sees the same safety filter and router as the live app.

Pipelines yield events and never raise. `handle()` wraps each `run()` in a guard: any uncaught
exception becomes `error(stage=<last stage>, message="Something went wrong in the <modality>
step. Other questions still work.", retryable=True)` + `final`. The pipeline that failed does
not affect later requests.

## API

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/chat` | multipart: `message` (str, may be empty), `files` (0–4 files), `manual_id` (str, optional) | `text/event-stream` of the events above |
| GET | `/api/health` | — | `{"profile": "full", "ollama": true, "models": {"brain": "qwen3-vl:8b", ...}, "loaded": ["qwen3-vl:8b"]}` |
| GET | `/api/manuals` | — | `[{"id": "washer_lg_wm3400", "title": "washer_lg_wm3400.pdf", "pages": 64}]` (from `data/manuals/*.pdf`; `[]` when empty) |
| WS | `/api/mic` (P2) | client → `binary` webm/opus chunks every 3 s, then text `{"type":"stop"}` | server → `{"type":"partial","text":...}` per chunk, then `{"type":"final","text":...}` |

Server: `uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8000`. CORS allows
`http://localhost:5173` and `http://127.0.0.1:5173`. Mock server: same paths on port 8001
(`uv run uvicorn mock_server.server:app --port 8001`). The UI picks with `VITE_API_URL`.

## Request flow

`browser → POST /api/chat → save uploads to a temp dir → convert.py → safety (message) →
router → pipeline.run → (safety on transcript / top-1 sound inside audio) → SSE → browser`.
State lives only in the browser (visible chat log) and on disk (manuals, frame cache). The
real decisions are made by plain code: safety, router, quote verifier, code self-check.

1. **Upload limits.** > 4 files → `refusal(unsupported_file, "Attach up to 4 files at a
   time.")`. Any single file > 200 MB → `refusal(too_large, "That file is over 200 MB. Try a
   shorter clip or a smaller photo.")`.
2. **Convert** (`app/media/convert.py::normalize(path) -> Attachment`):
   jpg/jpeg/png/heic/heif/webp/bmp/gif(first frame) → JPEG, longest side ≤ `image.max_side`;
   wav/mp3/m4a/aac/webm(audio-only)/ogg/flac → 16 kHz mono WAV; mp4/mov/m4v/webm(with video)/avi
   → H.264 ≤ 720p, first 120 s only (status detail "Used the first 120 s");
   pdf/docx/txt/md → `pages` (PDF via PyMuPDF per page; docx and txt/md as one page with
   `page=None`); csv/json/py → `kind="data"`, copied as-is. Anything else, or a file ffmpeg
   can't decode → `UnsupportedFile` → `refusal(unsupported_file, "I can't open .<ext> files.
   Try a photo, audio, video, PDF, Word, text or CSV file.")`. A zero-byte file is
   `unsupported_file` with "That file is empty."
3. **Empty input.** No message and no files → `refusal(empty_input, "Type a question or attach
   a file.")`.
4. **Safety** (`app/safety.py::check(text) -> SafetyHit | None`). See "Safety".
5. **Router** (`app/router.py::route(message, attachments, manual_id) -> Route(modality,
   question_type)`). See "Router".
6. **Pipeline** yields events; the API adds `latency_ms` into `final`.

## Safety

`config/safety_rules.yaml` gains a `benign:` list. `check(text)`:
1. Lowercase. Remove each `benign` match (replace with a space).
2. Run the danger `patterns` on what's left. First match → `SafetyHit(category, pattern)`.

`benign` patterns (case-insensitive):
- `\bsmoke (detector|alarm)s?\b.{0,40}\b(chirp\w*|battery|batteries|beep\w* once)\b`
- `\bfire (alarm|detector)s?\b.{0,40}\b(chirp\w*|battery|batteries)\b`
- `\bfire ?(tv|stick|tablet)\b`
- `\bburn(t|ed|ing)? (toast|food|popcorn|rice)\b`
- `\b(outlet|drain|inlet|fill) hose\b`
- `\bgas (stove|range|oven) (recipe|cooking|temperature)\b`
- `\bsparks? joy\b`

Where it runs: on `message` before routing; inside `audio.py` on the transcript before the
answer; inside `audio.py` on the top-1 sound label when it is one of `smoke alarm beeping
loudly`, `carbon monoxide alarm`, `smoke detector, smoke alarm`, `fire alarm` with score ≥
`audio.alarm_safety_min_score` (0.5). The audio track of a video is not transcribed or
checked (our call: it would add a Whisper step to every video; named as a limit in
ARCHITECTURE.md). Image OCR text is not checked (a photo of a "FIRE EXIT"
sign must not trigger it).

On a hit from the message or transcript: `refusal(reason="safety", message=<rules.message
verbatim>, category=<category>)` + `final(answer="")`. No model call after the hit (for the
transcript, the brain answer step is skipped). On an alarm-sound hit: `sound_labels` is still
sent, then the same refusal, then `final`.

| Input | Expected |
|---|---|
| "smoke detector keeps chirping" | no hit |
| "fire alarm battery is low" | no hit |
| "my Fire TV stick froze" | no hit |
| "burnt toast smell" | no hit |
| "water dripping from the outlet hose of the washer" | no hit |
| "smoke alarm is going off and won't stop" | hit, `smoke_fire` |
| "I smell burning plastic from the dryer" | hit, `smoke_fire` |
| "the smoke detector chirps and I smell gas" | hit, `gas` |
| "sparks came out of the outlet" | hit, `sparks` |
| "the cord is frayed, wires showing" / "frayed wire" | hit, `exposed_wires` |
| "water on the floor near the outlet" | hit, `water_electric` |
| "I got a shock from the fridge door" | hit, `shock` |
| "gas stove recipe" | no hit |
| voice note "I smell gas in the kitchen" | hit, `gas` (from transcript) |
| sound clip, top-1 `smoke alarm beeping loudly` at 0.71 | labels + hit |
| sound clip, top-1 `smoke alarm beeping loudly` at 0.32 | labels only |

## Router

Plain rules, in order. `ext` is the original file extension.

1. `manual_id` set and one image attached → `homefix / manual_lookup` (P2; until it ships the
   stub refuses and the UI hides the picker when `/api/manuals` returns `[]`).
2. Any `data` attachment (csv/json/py) or no attachment and the message matches
   `\b(write|create|implement|generate)\b.{0,40}\b(function|script|code|program|class)\b` or
   `\bpython\b|\bdef \w+\(` → `code / code_gen`.
3. First attachment decides the modality. Extra attachments of the same kind: images go to the
   brain together (up to 4); other kinds use only the first and emit
   `status(stage="routing", detail="Only the first file was used.")`. Different kinds mixed: the
   first file wins, same status detail.
4. `image`: count if message matches `\bhow many\b|\bcount\b|\bnumber of\b`; read if
   `\b(read|say|says|written|text|code|display|label|sign|error)\b`; describe if the message is
   empty or matches `\bdescribe|what('s| is) (in|this)\b`; else `qa`.
5. `video`: count / read rules as image; `motion` if
   `\b(direction|moving|move|moves|turn|turning|spin|spinning|left|right|toward|away)\b`;
   describe if empty; else `qa`.
6. `audio`: `speech` if `\b(say|said|says|transcribe|transcript|words|talking)\b`; `sound` if
   `\b(sound|noise|beep|beeping|hear|hearing)\b`; otherwise `none` (the pipeline decides).
7. `document`: `text / doc_qa`. Empty message → `refusal(empty_input, "Ask a question about
   the document.")`.
8. No attachment, `manual_id` set → `text / doc_qa` over that manual.
9. No attachment, no manual, not code → `refusal(no_document, "Attach a file or pick a manual,
   and I'll answer from it. HomeFix only answers from what you give it.")`. (Our call: this
   keeps the "no text answer without a verified quote" rule strict.)

## Pipelines

### Image (`app/pipelines/image.py`, Meghana)
Brain = `profile.models.brain` through `ollama_client.chat_stream(model, messages, images)`.
Prompts by type:
- count: "Count the {thing}. Reply with the number first as digits, then one short sentence.
  If the image is too blurry to count, reply exactly: I can't tell."
- read: "Read the text exactly as written. If you can't read it, reply exactly: I can't tell."
- describe / qa: one paragraph, ≤ 80 words.
`{thing}` = the noun phrase after "how many" (regex), fallback "objects".
Post-processing for count: if the answer doesn't start with an integer, find the first integer
(digits or number words zero–twenty) and prepend it as digits ("four mugs" → "4. four mugs").
If none and not "I can't tell", leave as is. Tokens stream; `final.answer` is the full text.

### Text (`app/pipelines/text.py`, Meghana; helpers in `app/text/`)
1. Document = attachment `pages` or the selected manual (PyMuPDF pages, cached in memory by
   file mtime). Token estimate = words × 1.3.
2. ≤ `text.full_doc_max_tokens` (6000): whole document with `[page N]` markers. Else
   `app/text/retrieve.py`: chunks of ~350 words with 50 overlap, each tagged with its page;
   BM25 top 20 + bge-small cosine top 20, fused by reciprocal rank (k=60), keep
   `text.rag_top_k` (5). Status `retrieving`.
3. Prompt asks for JSON only: `{"answer": str | null, "quote": str | null, "page": int | null}`,
   quote copied word for word, answer `null` if not in the text.
4. Parse: `json.loads`, else the first `{...}` block by regex, else treat as failed attempt.
5. Verify (`app/text/verify.py::verify(answer, quote, pages, threshold) -> Verdict`): quote ≥ 3
   words; normalized quote is a substring of the normalized document, or
   `rapidfuzz.fuzz.partial_ratio ≥ text.quote_fuzz_threshold` (92) against the cited page (or
   all pages if `page` is null/wrong; the matched page is what we cite); every number in the
   answer (digits, decimals, number words one–twenty) appears in the quote. Normalize =
   lowercase, collapse whitespace, unify quotes and dashes.
6. Fail → re-prompt once: "Your quote was not found word for word. Copy a shorter exact
   sentence from the text, or answer null." Fail again or `answer: null` →
   `refusal(not_in_document, "The document doesn't contain the answer.")`.
7. Pass → `citation` then `final(answer=answer)`.

### Code (`app/pipelines/code.py`, Meghana; helpers in `app/code/`)
1. `memory.ensure("coder")` (status `loading_model` with `ms` on `lite`).
2. Prompt: write one Python function with ≥ 2 doctest examples in its docstring, standard
   library only, in one ```python block. If a csv is attached: its header + first 5 rows are
   included and the function takes a file path. If the message contains a signature
   (`def name(...)`, as HumanEval-style prompts do), the prompt adds "Keep this exact function
   name and signature" and `target_name` = that name.
3. Extract (`app/code/extract.py::extract_code(text, target_name=None) -> str | None`): first
   ```python block, else first ``` block, else the whole text if `ast.parse` succeeds and it has
   a `def`. None → attempt fails with output "No code block found." `target_name` set and no
   `def <target_name>(` in the code → attempt fails with "Function <target_name> not found."
   Imports from a stub in the message are kept at the top.
4. Self-check (`app/code/sandbox.py::run_doctests(code, files, timeout_s) -> SandboxResult`):
   write `solution.py` (+ attached data files) to a fresh temp dir; run
   `sys.executable -I -c <prelude> ` where the prelude replaces `socket.socket` and
   `socket.create_connection` with functions raising `OSError("network disabled")`, then runs
   `doctest.testmod` on the module; env = only `PATH`, `HOME=<tmpdir>`, `PYTHONHASHSEED=0`;
   `timeout = code.selfcheck_timeout_s` (10). 0 doctests found → fail "No examples to check.".
   Timeout → fail "Timed out after 10 s.".
5. Fail and attempts < 1 + `code.max_retries` → re-prompt with the last 1,500 chars of output.
6. `code_result` then `final(answer=<one-line explanation from the model, or "">)`.

### Audio (`app/pipelines/audio.py`, Akshayaa; loaders in `app/models/whisper.py`, `clap.py`)
1. Status `transcribing`; Whisper `profile.models.whisper_file` → text + mean `no_speech_prob`.
2. Speech if router said `speech`, or (router said `none`) transcript ≥ 3 words and mean
   `no_speech_prob` < `audio.speech_max_no_speech_prob` (0.6). Router `sound` forces sound path.
3. Speech path: `transcript` event → safety on transcript → if the message has a question,
   brain answers from the transcript (tokens stream); else `final.answer` = transcript.
4. Sound path: status `labeling_sounds`; CLAP zero-shot over `general.txt` ∪ `appliances.txt`
   with template "the sound of {label}" → `sound_labels` (top 3) → alarm safety check →
   `final.answer` = "Sounds like: {top1} ({score:.0%}), {top2}, {top3}."

### Video (`app/pipelines/video.py`, Akshayaa; helpers in `app/video/`)
1. Cache key = sha256 of the normalized file. `.cache/frames/<hash>/` holds frames + `meta.json`.
   Hit → skip extraction (status `extracting_frames`, detail "cached").
2. `video.frames` evenly spaced frames (16 / 8), resized to `video.frame_side` (448).
   `frames` event with timestamps.
3. Read questions add the `video.read_extra_frames` (2) sharpest frames (Laplacian variance)
   at native resolution.
4. Brain gets all frames in one request; prompt lists "Frame k at t=…s" for each image. Count /
   read prompts reuse the image rules (number first, "I can't tell"). Motion prompt asks for
   one direction word from: left, right, up, down, toward, away, clockwise, counterclockwise.

### HomeFix manual (`app/pipelines/homefix.py`, Meghana, P2)
1. Image `read` prompt: "What error code or message is shown on the display? Reply with the
   code only, or I can't tell." Code regex `\b[A-Z]{1,3}\s?-?\d{1,3}\b`.
2. `I can't tell` / no code → `final(answer="I couldn't read a code on the display. Try a
   sharper photo, straight on.")`.
3. Else run the text pipeline over the manual with "What does error code {code} mean and what
   should I do?" and pass its events through (`citation` or `not_in_document` refusal).

## Memory (`app/models/memory.py`, Meghana)

`MemoryManager.ensure(role: Literal["brain","coder"]) -> Iterator[Status]`.
- `full`: both resident (`keep_alive: -1`); `ensure` yields nothing when already loaded.
- `lite`: if the other LLM is loaded, unload it (`keep_alive=0` request), load the target,
  yield `status(stage="loading_model", detail="loading <tag>", ms=<elapsed>)`. Coder
  `keep_alive: 120`.
- Router `code_intent` (route = code) triggers `prefetch("coder")` in a background thread on
  `full` only.
- Ollama not reachable → `ModelUnavailable` → `refusal(model_unavailable, "The local model
  server isn't running. Start Ollama and try again.")`. Call > `ctx.deadline_s` (90 s) →
  `refusal(timeout, "The model took too long. Try a shorter clip or a smaller question.")`.
  Whisper / CLAP / bge load failure → `refusal(model_unavailable, "The <role> model isn't
  installed. Run scripts/pull_models.sh.")`.

## Profile keys (added on day one, both YAML files)

Existing keys stay. Added:
```yaml
audio:
  speech_max_no_speech_prob: 0.6
  alarm_safety_min_score: 0.5
  top_k: 3
server:
  max_files: 4
  max_file_mb: 200
  video_max_seconds: 120
  model_call_timeout_s: 90
cache_dir: .cache
```

## Eval

- `eval/pack.py::load_items(pack_dir) -> list[PackItem]` with
  `PackItem(id: str, modality: str, question: str, path: Path | None, meta: dict)`. The exact
  `items.json` field names are confirmed when the pack is downloaded; this is the only file that
  knows them. `go_no_go.py` already assumes `modality` and `file`.
- Pack shape is not known yet (the pack isn't downloaded). `eval/pack.py` absorbs both
  possibilities: a text item whose document is a file becomes a normal file; a document given
  as a string inside the item becomes `Attachment(path=None, kind="document",
  original_name="<item id>.txt", pages=[text])`. A code item's prompt (signature + docstring)
  becomes the `message`. If the pack's code tests expect a specific module name, `eval/run.py`
  writes our function to that name before `eval/graders/code.py` runs the test.
- `eval/run.py`: for each item, call `app.orchestrate.handle(...)` (never a pipeline
  directly), write one JSON line `{run_id, item_id, modality, question_type, answer, events_summary,
  latency_ms, peak_mem_gb, profile, model}` to `results/raw/<run_id>.jsonl`. Item IDs only, no
  question text in committed output.
- `eval/grade.py`: reads `answers.json`, calls `eval/graders/<modality>.py::grade`.
- `eval/report.py`: writes `results/summary_<profile>.md` (numbers only) using the metrics in
  EVAL.md.
- Tests needing the pack read `PRACTICE_PACK_DIR` and are skipped when it is unset. All other
  tests use tiny generated fixtures (PIL images, sine-wave WAVs, synthetic frames, text written
  in the test).

## UI (`frontend/`, Akshayaa; two components Meghana)

Layout (desktop; phone = one column, sidebar becomes a drawer):
```
┌───────────── HomeFix ── [full · M4] [Wi-Fi off ✓] ──────────────┐
│ Manuals      │  (welcome: 5 tiles  🖼 🔊 📄 💻 🎬 + "drop a file")  │
│ ○ none       │  you: how many mugs?  [mugs.jpg]                    │
│ ● washer…pdf │  [converting ✓][routing ✓][generating …]            │
│              │  HomeFix: 4. Four mugs on the top shelf.   ⏱ 6.2 s  │
│              │  ┌ citation ┐ ┌ code ✓ 2/2 ┐ ┌ sound bars ┐          │
│              │ [📎] [ type a question…            ] [🎤] [Send]    │
└──────────────┴──────────────────────────────────────────────────┘
```
States:
- **Empty:** five capability tiles and "Drop any photo, audio, video, document or CSV."
- **Loading:** status chips appear per `status` event (spinner on the latest, ✓ on earlier,
  `ms` shown for `loading_model`); Send disabled until `final`.
- **Streaming:** `token` text appends live.
- **Done:** answer, latency badge from `final.latency_ms` (e.g. "6.2 s"), model tag on hover;
  citation card (quote in a blockquote, "p. 37 · washer_manual.pdf"); code panel (code,
  green "passed 2/2" or red "failed 1/2", attempts, collapsible output); sound bars (3 bars
  with %); frame strip (timestamps as ticks).
- **Refusal:** grey card with `message` verbatim; safety refusals get a red ⚠️ card and no
  other content.
- **Error:** amber card with `message`, "Try again" button resends the same request.
- **Backend down:** banner "Can't reach HomeFix at {VITE_API_URL}. Is the server running?",
  retried every 5 s via `/api/health`.
- **Mock mode:** a "MOCK" badge when `VITE_API_URL` points at port 8001.
- **Manual picker:** hidden when `/api/manuals` returns `[]`.

## Golden examples

| # | Input | Expected output |
|---|---|---|
| G1 | Washer end-of-cycle beep recording | `sound_labels` top 3 includes "washing machine beeping" |
| G2 | Photo of a display showing "E21" + washer manual selected | reads "E21"; `citation` with verbatim quote and page (P2) |
| G3 | Question the selected manual doesn't cover | `refusal(not_in_document, "The document doesn't contain the answer.")` |
| G4 | "I smell burning plastic from the dryer" | `refusal(safety, <fixed message>)`, no model call, latency ≤ 0.1 s |
| G5 | "How many mugs are on the shelf?" + photo | answer starts with an integer; "I can't tell" if blurry |
| G6 | "Write a function that averages the fridge's watts per hour" + `data/smartplug_fridge.csv` | `code_result.passed = true`, `tests_run ≥ 2` |
| G7 | 30 s clip of the drum not turning | `frames` with 16 timestamps (8 on lite); answer refers to frames by time |
| G8 | `.heic` photo / `.m4a` voice note | converted and answered |
| G9 | `.exe` or `.zip` | `refusal(unsupported_file, "I can't open .exe files. …")`, no crash |
| G10 | "smoke detector keeps chirping" + manual selected | normal answer, no safety message |
| G11 | Empty message, no file | `refusal(empty_input, "Type a question or attach a file.")` |
| G12 | Ollama stopped, image question | `refusal(model_unavailable, …)`; next audio sound request still works |

## Left to the builder

- Exact prompt wording beyond what is quoted above (keep the quoted sentences verbatim).
- Chunk sizes for live mic decoding, CSS, component internals.
- How `eval/report.py` formats tables, as long as the EVAL.md metrics appear.

## Calls made without asking (check these)

- No attachment and no manual → `refusal(no_document)`, not a general-advice answer.
- One request = one modality; mixed attachments use the first file.
- Video audio track is not transcribed or safety-checked.
- Upload caps: 4 files, 200 MB each, first 120 s of video.
- Contract changes go in one `contract/<change>` PR touching both files, approved by both.
- Eval seams (`eval/types.py`, grader stubs) are created by Akshayaa; everything else shared is
  stubbed by Meghana on day one.
- `app/orchestrate.py::handle()` is the single entry for API, CLI and eval.
- Latency targets in "Constraints" are our numbers; the README referred to a table that didn't
  exist yet.
