# Pitch demo and "maintenance tag" theme: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a presenter-paced `#/demo` that replays six real, recorded HomeFix answers one key press at a
time, plus a light "maintenance tag" theme (warm concrete, safety orange) across the whole app.

**Architecture:** Two setup scripts do the work before the pitch. `scripts/fetch_demo_media.py`
downloads pinned Wikimedia Commons files. `scripts/record_demo.py` sends each scene's input to
`POST /api/chat` on the `full` profile and saves the raw SSE events. The frontend replays those events
through the existing `reduce()` and renders them with the existing `TurnView`, so demo cards are app
cards. The theme is a token swap in `index.css`, plus a hazard stripe on the safety card.

**Tech Stack:** Python 3.11, httpx, PyYAML, ffmpeg, pytest. React 18, TypeScript, Vite 5, Vitest and
Testing Library. lucide-react icons.

**Spec:** [docs/superpowers/specs/2026-11-20-pitch-demo-and-theme-design.md](../specs/2026-11-20-pitch-demo-and-theme-design.md)

## Who does what

Meghana runs every task. Tasks 1 and 5 edit files Akshayaa wrote: `frontend/src/index.css`,
`RefusalCard.tsx`, `App.tsx` and `Redesign.test.tsx`. **Akshayaa pauses UI edits from the start of
Task 1 until Task 5 is merged to `main`.** Tasks 2, 3, 4 and 6 only create new files, plus small edits
to `.gitignore` and `docs/ASSETS.md`.

## Global Constraints

- Routes: `#/ask` is the workspace, `#/demo` the demo, and anything else is the landing page.
  `routeOf(hash): "landing" | "ask" | "demo"`, where `#/demo` matches `^#\/demo(\b|\/|$)` and
  `#/demos` stays the landing page.
- Scene ids, in this order: `problem`, `photo`, `sound`, `honesty`, `danger`, `proof`.
- Recording file: `frontend/src/demo/recordings/<scene>.json`, holding
  `{ scene, recorded_at, profile, request: { message, files, manual_id }, events }`. Recordings exist
  only for `photo`, `sound`, `honesty` and `danger`. `request.files` holds web paths
  (`/samples/...`, `/demo/...`), never disk paths.
- Scene inputs and pass rules (from the spec):

  | Scene | `message` | file on disk → web path | `manual_id` | Must have |
  |---|---|---|---|---|
  | photo | `What should I do?` | `frontend/public/samples/washer_display_e21.jpg` → `/samples/washer_display_e21.jpg` | `apartment_guide_unit_4b` | `citation` whose `quote` contains `E21` (case-insensitive), no `refusal`, a `final` |
  | sound | `What is this sound?` | `frontend/public/demo/smoke_alarm_chirp.wav` → `/demo/smoke_alarm_chirp.wav` | none | `sound_labels` with `labels[0].label == "smoke alarm chirp"`, no `refusal`, a `final` |
  | honesty | `Is there a warranty on the washer?` | none | `apartment_guide_unit_4b` | `refusal.reason == "not_in_document"`, a `final` |
  | danger | `I smell burning from the outlet behind the fridge` | none | none | `refusal.reason == "safety"`, a `final` |

- The recorder refuses to run unless `GET /api/health` returns `"profile": "full"` (exit code 2).
- A recorded string must not start with `data:` or be longer than 4,000 characters.
- Commons list: `config/demo_media.yaml`, with these fields per item: `file`, `url`, `author`,
  `license`, `sha256`, `use` and `out`.
  - Licenses allowed: values starting with `CC0`, `CC BY ` or `CC BY-SA `, or exactly `CC BY`.
  - `out` matches `^[a-z0-9_]+\.(jpg|png|wav)$`.
  - Output folder: `frontend/public/demo/` (gitignored).
  - Audio becomes 16 kHz mono `.wav`: `ffmpeg -y -i <src> -ac 1 -ar 16000 <out>`.
- Pinned `out` names: `breaker_panel.jpg`, `leaking_pipe.jpg`, `thermostat.jpg`,
  `smoke_detector.jpg`, `smoke_alarm_chirp.wav`.
- Theme tokens in `index.css`:
  - Changed: `--paper #f4f2ee`, `--wash #f0ece5`, `--ink #1c1917`, `--ink-soft #44403c`,
    `--ink-faint #78716c`, `--rule #e2ddd4`, `--rule-strong #b8b0a3`, `--pen #c2410c`,
    `--pen-deep #9a3412`, `--pen-tint #fdeee4`.
  - New: `--panel #1f1d1b`, `--seg #ff8a3d`, `--seg-dim #5a3a26`, `--hazard #f5b800`.
  - Unchanged: `--sheet #ffffff`, `--answered`, `--notfound` and `--danger`, with their tints.
- Hazard stripe: an element with class `hazard`, `aria-hidden="true"`, inside `RefusalCard` only when
  `reason === "safety"`.
- Demo keys:
  - Next beat: `ArrowRight`, ` ` (Space), `PageDown`.
  - Previous beat: `ArrowLeft`, `PageUp`.
  - `1`–`6`: the first beat of that scene.
  - `Escape`: sets `location.hash = "#/ask"`.
  - `f` or `F`: `document.documentElement.requestFullscreen?.()`.
  - Listeners attach on `DemoPage` mount and detach on unmount. Keys from an `input`, `textarea` or
    `select` are ignored.
- Demo copy (exact):
  - Corner label: `Recorded on the M4, full profile, <D Mon YYYY>`, from `recorded_at`.
  - Missing recording: `This scene hasn't been recorded. Run scripts/record_demo.py.`
  - Missing media: `Run scripts/fetch_demo_media.py`.
  - Blocked audio button: `Play the sound`.
  - Scene 2 photo note: `Drawn by us: no openly licensed photo of an error display exists`.
  - Credit line: `Photos and sounds: Wikimedia Commons, see ASSETS.md`.
- Scores, from `results/summary_full.md` (run `20261120-1009-full-all`) and `results/summary_lite.md`
  (run `20261119-1404-lite-all`):

  | Row | full | lite |
  |---|---|---|
  | Image count | 14/15 | 14/15 |
  | Sound top-1 | 8/10 | 8/10 |
  | Speech transcript | 8/10 | 6/10 |
  | Text answers | 15/15 | 14/15 |
  | Text refusals | 3/5 | 2/5 |
  | Code pass@1 | 20/20 | 17/20 |
  | Video (all metrics) | 11/15 | from `summary_lite.md`, or "not run" if the section is missing |

- No remote URL (`http://` or `https://`) in any `frontend/src/demo/` or `frontend/src/components/demo/`
  file, and none in `app/` (hard rule 5).
- Uncommitted now, and not to be staged by Tasks 1–5: `results/summary_full.md` (Task 6 commits it).
  The spec and this plan are committed together before Task 1.
- Commits: conventional, no AI attribution lines. Run `uv run pytest` and `cd frontend && npm test`
  before each commit.

## Review Focus

1. **Empty or partial recording** (`events: []`, or no `final`): the scene shows the missing-recording
   message and the other scenes still play. Task 4 (`expandBeats` tests) and Task 5 (DemoPage test).
2. **Unsupported media type in the list** (`out: chirp.ogg`, a GIF) or a non-free license
   (`CC BY-NC`): `load_media_list` raises `ValueError` naming the item. Task 2.
3. **Malformed server output during recording** (a `data:` line that isn't JSON, or a stream with no
   `final`): that scene fails with a reason, nothing is written for it, and the next scene still
   records. Task 3.
4. **Model not loaded or timing out** (a `refusal` with reason `model_unavailable` or `timeout`, or an
   httpx timeout): the scene fails, its old recording is left as it was, and the exit code is 1.
   Task 3.
5. **Wrong profile (`lite` memory pressure)**: the recorder exits 2 before sending anything. Task 3.
6. **Partial failure on stage**: one scene's media returns 404, or one recording is missing. That
   scene shows its fallback, and the arrow keys still reach every other scene. Task 5.
7. **Keys leaking into the app**: after `DemoPage` unmounts, pressing `Escape` or `3` does nothing.
   Task 5.

---

### Task 1: The maintenance-tag theme

**Files:**
- Modify: `frontend/src/index.css` (the `:root` tokens at lines 9–45; the `body` top border; add
  `.hazard`; the seven-segment panel; the hero glow)
- Modify: `frontend/src/components/RefusalCard.tsx:29-38` (the safety branch)
- Modify: `frontend/src/components/landing/SevenSeg.tsx` (segment colours from `--seg` and
  `--seg-dim`, if it hard-codes them now)
- Test: `frontend/src/components/Theme.test.tsx` (new)

**Interfaces:**
- Consumes: `RefusalCard({ refusal }: { refusal: RefusalEvent })`.
- Produces: the CSS tokens `--panel`, `--seg`, `--seg-dim` and `--hazard`, and the class `hazard`,
  which Task 5 reuses.

- [ ] **Step 1: Write the failing tests** in `Theme.test.tsx`:
  - `tokens match the maintenance-tag palette`: read `src/index.css` with `fs.readFileSync`. For each
    token in Global Constraints, assert the `:root` block contains `--<name>: <hex>;`. Assert
    `--answered: #0b6b5e;`, `--notfound: #7d4a00;` and `--danger: #b3261e;` are unchanged.
  - `no raw hex outside :root`: after removing the `:root { … }` block, the CSS contains no
    `#[0-9a-f]{3,6}\b`, except `#fff` and `#000`.
  - `safety card has a hazard stripe`: render
    `<RefusalCard refusal={{type:"refusal", reason:"safety", message:"Stop. Leave and call 911."}} />`.
    Expect `container.querySelector(".card--safety .hazard")` to be present with `aria-hidden="true"`.
  - `not-in-document card has no stripe`: the same with `reason: "not_in_document"`. Expect
    `.hazard` to be absent.
- [ ] **Step 2: Run `cd frontend && npx vitest run src/components/Theme.test.tsx`** → FAIL (old token
  values, and no `.hazard`).
- [ ] **Step 3: Implement.**
  - Swap the tokens.
  - Make the `body` `border-top` 4px `var(--pen)`.
  - Add `.hazard`: `height: 8px`, background `repeating-linear-gradient(-45deg, var(--hazard) 0 9px, var(--ink) 9px 18px)`,
    with negative margins so it spans the card's top edge, and the card's top corners rounded.
  - Put the seven-segment display on `var(--panel)`, with lit segments `var(--seg)` and unlit
    `var(--seg-dim)`.
  - The hero glow: `radial-gradient(ellipse at 85% 30%, rgb(194 65 12 / 0.12), transparent 60%)`.
  - Replace the two `#8f1d17` and `#6d28d9` uses with tokens. `#8f1d17` becomes `var(--danger)`. For
    `#6d28d9`, if it marks code, use `var(--pen-deep)`.
  - Render `<div className="hazard" aria-hidden="true" />` as the first child of the safety branch only.
- [ ] **Step 4: Run `cd frontend && npm test`** → PASS. That's the whole frontend suite, because token
  edits can break snapshot-like assertions in `Redesign.test.tsx`.
- [ ] **Step 5: Look at it.** Run `npm run dev` and open the landing page, `#/ask`, and `#/ask` with
  the "danger" example. Check that the orange top border, the dark display panel and the stripe on the
  safety card appear, and that the amber card has no stripe.
- [ ] **Step 6: Commit.**
  ```bash
  git add frontend/src/index.css frontend/src/components/RefusalCard.tsx \
          frontend/src/components/landing/SevenSeg.tsx frontend/src/components/Theme.test.tsx
  git commit -m "feat(ui): a warm concrete and safety-orange look, with hazard stripes on the stop card"
  ```

### Task 2: Commons media list and fetch script

**Files:**
- Create: `config/demo_media.yaml`, `scripts/fetch_demo_media.py`
- Modify: `.gitignore` (add `frontend/public/demo/` under the samples block), `docs/ASSETS.md` (one row
  per Commons file)
- Test: `tests/test_demo_media.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class MediaItem: file: str; url: str; author: str; license: str; sha256: str; use: str; out: str`
  - `load_media_list(path: Path) -> list[MediaItem]`, which raises `ValueError(f"{file}: …")`.
  - `class ChecksumError(Exception)`
  - `fetch_one(item: MediaItem, dest: Path, get: Callable[[str], bytes], convert: Callable[[Path, Path], None]) -> Path`
  - `main(argv: list[str] | None = None) -> int`, which returns 0 on success, 1 on any failure, and
    prints one line per item.
  - The files `frontend/public/demo/<out>`, which Tasks 3 and 5 read.

- [ ] **Step 1: Write the failing tests** in `tests/test_demo_media.py`. Use `tmp_path`, a fake `get`
  that returns fixed bytes, and a fake `convert` that records its calls.
  - `test_load_accepts_cc0_and_cc_by_sa`: a two-item YAML with `CC0` and `CC BY-SA 4.0` loads as 2 items.
  - `test_load_rejects_non_free_license`: `CC BY-NC 2.0` raises `ValueError`, and the message contains
    the item's `file`.
  - `test_load_rejects_bad_out_name`: `out: Chirp.ogg` and `out: ../x.jpg` both raise `ValueError`.
  - `test_load_rejects_missing_field`: an item without `sha256` raises `ValueError`.
  - `test_checksum_mismatch_writes_nothing`: when `sha256` doesn't match the bytes, it raises
    `ChecksumError`, the message contains `file`, and `dest/<out>` doesn't exist.
  - `test_image_written_as_is`: for a matching sha256 the file is written byte-for-byte, and `convert`
    is not called.
  - `test_audio_converted_to_wav`: a `.webm` URL with `out: smoke_alarm_chirp.wav` calls `convert`
    once with the downloaded temp file and `dest/smoke_alarm_chirp.wav`.
  - `test_existing_output_skipped`: if `dest/<out>` already exists, `get` is never called.
  - `test_pinned_list_is_valid`: `load_media_list(ROOT / "config/demo_media.yaml")` loads. Its `out`
    names are exactly the five pinned names. Every `sha256` is 64 hex characters, and every `url`
    starts with `https://upload.wikimedia.org/`.
  - `test_demo_folder_ignored`: `git check-ignore frontend/public/demo/x.jpg` exits 0 (use
    `subprocess.run`).
- [ ] **Step 2: Run `uv run pytest tests/test_demo_media.py -v`** → FAIL (module not found).
- [ ] **Step 3: Implement.**
  - **Script:**
    - `get` uses `httpx.get(url, follow_redirects=True, timeout=60, headers={"User-Agent": "homefix-setup/1.0"})`
      and returns `.content`.
    - `convert` runs the ffmpeg command from Global Constraints and raises if it exits non-zero.
    - `main` reads `config/demo_media.yaml`, creates `frontend/public/demo/`, and calls `fetch_one`
      for each item. It catches each item's error, prints it, and carries on with the next item.
    - Docstring: "Setup only, never imported by app/. Downloads once; runs offline afterwards."
  - **Pin the list.** Look up each file through the Commons API:
    `https://commons.wikimedia.org/w/api.php?action=query&titles=File:<title>&prop=imageinfo&iiprop=url|sha1|extmetadata&format=json`.
    - Take `url`, `extmetadata.Artist` (as plain text) and `extmetadata.LicenseShortName`.
    - Download the file once and compute its sha256.
    - Candidates:
      - `Eaton circuit breaker panel open.JPG` → `breaker_panel.jpg`
      - `Leaking pipe by Saltash Field - geograph.org.uk - 7324720.jpg` → `leaking_pipe.jpg`
      - `Person holds a thermostat showing room temperature in a home setting.jpg` → `thermostat.jpg`
      - `Smoke detector (1).JPG` → `smoke_detector.jpg`
      - `Smoke detector alarm battery beep.webm` → `smoke_alarm_chirp.wav`
    - If a candidate's license isn't allowed, pick another Commons file for the same `use` and say so
      in the report.
  - **ASSETS.md:** add one row per item: file title, `frontend/public/demo/<out>`, author, license,
    URL, and "No (media)".
- [ ] **Step 4: Run `uv run pytest tests/test_demo_media.py -v`** → PASS. Then
  `uv run python scripts/fetch_demo_media.py` → five `ok` lines. A second run prints five `skip`
  lines.
- [ ] **Step 5: Commit.**
  ```bash
  git add config/demo_media.yaml scripts/fetch_demo_media.py tests/test_demo_media.py .gitignore docs/ASSETS.md
  git commit -m "feat(ui): one setup command fetches the demo's real photos and smoke-alarm chirp from Wikimedia Commons"
  ```

### Task 3: The demo recorder

**Files:**
- Create: `scripts/record_demo.py`
- Test: `tests/test_record_demo.py`

**Interfaces:**
- Consumes: `POST /api/chat` (multipart `message`, `files`, `manual_id`; SSE reply), `GET /api/health`
  (`{"profile": str, ...}`), and the media files from Task 2 and `scripts/make_samples.py`.
- Produces:
  - `SCENES: dict[str, SceneInput]`, where
    `@dataclass(frozen=True) class SceneInput: message: str; disk_file: str | None; web_file: str | None; manual_id: str | None`.
    Values are from Global Constraints.
  - `parse_sse(text: str) -> list[dict]`, which raises `ValueError("bad event: …")` on a `data:`
    payload that isn't JSON.
  - `check_scene(scene: str, events: list[dict]) -> list[str]`, which returns the problems found (an
    empty list means pass).
  - `check_no_inline_media(events: list[dict]) -> list[str]`
  - `record_scene(scene: str, client: httpx.Client, root: Path) -> dict`, which returns the recording
    dict.
  - `main(argv: list[str] | None = None, client: httpx.Client | None = None, root: Path = ROOT) -> int`
    - Flags: `--base-url` (default `http://127.0.0.1:8000`) and `--scene` (repeatable; default all four).
    - Exit 0 when all pass, 1 if any scene failed, 2 on a wrong profile.
  - The files `frontend/src/demo/recordings/{photo,sound,honesty,danger}.json`, which Task 4 reads.

- [ ] **Step 1: Write the failing tests** in `tests/test_record_demo.py`.
  - **Test setup:**
    - Use `httpx.Client(transport=httpx.MockTransport(handler))`, where `handler` returns
      `{"profile": "full"}` for `/api/health` and a canned SSE body per scene for `/api/chat`.
    - Build the SSE body from `app.contracts.to_sse`, so the format matches the server.
    - Use a `tmp_path` root with the two media files created as small stub files.
  - **Tests:**
    - `test_wrong_profile_exits_2_and_writes_nothing`: health returns `lite`; `main` returns 2, no
      `/api/chat` request is made, and the recordings folder is empty.
    - `test_photo_passes_with_e21_quote`: the events are status, citation with
      `quote="E21 Drain fault ..."`, and final. `check_scene("photo", …) == []`.
    - `test_photo_fails_on_refusal`: when a `refusal` is present, the problems mention `refusal`.
    - `test_photo_fails_when_quote_lacks_code`: with quote `"Clean the filter"`, the problems mention
      `E21`.
    - `test_sound_fails_when_heard_as_alarm`: when `labels[0].label == "smoke detector, smoke alarm"`,
      the problems mention `smoke alarm chirp`.
    - `test_honesty_needs_not_in_document`: a `refusal` with reason `safety` fails; one with
      `not_in_document` passes.
    - `test_danger_needs_safety`: a `refusal` with reason `safety` passes; with no refusal, it fails.
    - `test_missing_final_fails`: any scene without a `final` reports `no final`.
    - `test_model_unavailable_fails`: a `refusal` with reason `model_unavailable` fails the photo scene.
    - `test_inline_media_flagged`: `check_no_inline_media` flags a string starting `data:image/png`
      and a 4,001-character string.
    - `test_bad_sse_line_fails_scene_not_run`: for the photo scene, `/api/chat` returns `data: {oops`.
      `main` returns 1, `photo.json` is not written, and `honesty.json` is written.
    - `test_failed_scene_keeps_old_recording`: an existing `photo.json` is byte-identical after a
      failing photo run.
    - `test_request_shape`: the photo request is multipart, with `message="What should I do?"`,
      `manual_id="apartment_guide_unit_4b"` and one file named `washer_display_e21.jpg`. The written
      `request.files == ["/samples/washer_display_e21.jpg"]`.
    - `test_missing_input_file_names_setup_script`: with no `washer_display_e21.jpg` under root, the
      problems contain `scripts/make_samples.py`. For the sound scene, they contain
      `scripts/fetch_demo_media.py`.
    - `test_timeout_fails_scene`: when the handler raises `httpx.ReadTimeout`, `main` returns 1 and
      the next scene still records.
- [ ] **Step 2: Run `uv run pytest tests/test_record_demo.py -v`** → FAIL (module not found).
- [ ] **Step 3: Implement.**
  - The chat timeout is 180 s.
  - `recorded_at` uses `datetime.now().isoformat(timespec="seconds")`.
  - Write the JSON with `indent=1` and `ensure_ascii=False`, through a temp file plus `os.replace`,
    so a crash never leaves half a file.
  - Print `<scene>: ok` or `<scene>: FAILED - <problems joined by "; ">`.
- [ ] **Step 4: Run `uv run pytest tests/test_record_demo.py -v`** → PASS. Run `uv run ruff check .`
  → clean.
- [ ] **Step 5: Commit.**
  ```bash
  git add scripts/record_demo.py tests/test_record_demo.py
  git commit -m "feat(ui): record the demo's four answers from the real models, keeping only ones that pass"
  ```

### Task 4: Demo scenes, cuts and scores (no UI yet)

**Files:**
- Create: `frontend/src/demo/scenes.ts`, `frontend/src/demo/cuts.ts`, `frontend/src/demo/beats.ts`,
  `frontend/src/demo/scores.ts`, `frontend/src/demo/recordings/.gitkeep`
- Test: `frontend/src/demo/demo.test.ts`

**Interfaces:**
- Consumes: `HomeFixEvent` (`src/contract.ts`), `newTurn` and `reduce` (`src/state/reduce.ts`), and
  `SentFile` (`{ name, kind, url }`).
- Produces:
  - In `scenes.ts`:
    - `type SceneId = "problem" | "photo" | "sound" | "honesty" | "danger" | "proof"`
    - `Beat`, as in the spec, with `{ kind: "turn" }` replacing `events`.
    - `interface Scene { id: SceneId; title: string; note?: string; beats: Beat[] }`
    - `interface Recording { scene: SceneId; recorded_at: string; profile: string; request: { message: string; files: string[]; manual_id: string | null }; events: HomeFixEvent[] }`
    - `SCENES: Scene[]`
    - `RECORDINGS: Partial<Record<SceneId, Recording>>`, loaded with
      `import.meta.glob("./recordings/*.json", { eager: true, import: "default" })`.
  - `cutPoints(events: HomeFixEvent[]): number[]` in `cuts.ts`. Each value k means "show
    `events.slice(0, k)`".
  - In `beats.ts`:
    - `type Flat = { scene: number; kind: Beat["kind"] | "missing"; upTo?: number; beat: Beat | null }`
    - `expandBeats(scenes: Scene[], recs: Partial<Record<SceneId, Recording>>): Flat[]`
    - `turnAt(rec: Recording, upTo: number): Turn`
    - `firstBeatOf(flat: Flat[], scene: number): number`
  - `SCORES: { row: string; full: string; lite: string }[]` in `scores.ts`, with
    `SCORE_RUNS = { full: "20261120-1009-full-all", lite: "20261119-1404-lite-all" }`.

- [ ] **Step 1: Write the failing tests** in `demo.test.ts`.
  - `cutPoints` cases:
    - `[st("a"), st("a",detail), st("b"), tok, tok, citation, final]` → `[1, 3, 6, 7]`. Cuts come
      after the first new stage `a`, after new stage `b`, after `citation` and at `final`. The tokens
      fold into the next cut.
    - `[st("a"), sound_labels, refusal, final]` → `[1, 2, 3, 4]`.
    - `[]` → `[]`.
    - A list with no `final` → no cut at `events.length` unless the last event is itself a cut type.
  - `turnAt(photoRec, 7)`:
    - `.citation` is set, `.final` is set, and `.sentFiles[0]` equals
      `{ name: "washer_display_e21.jpg", kind: "image", url: "/samples/washer_display_e21.jpg" }`.
    - `turnAt(photoRec, 1).final` is `null`.
  - `expandBeats` cases:
    - With all four recordings, the `photo` scene's beat count is its non-turn beats plus
      `cutPoints(...).length`, and every `turn` beat has `upTo` set.
    - With `photo` missing, that scene expands to exactly one `{ kind: "missing" }`, and the other
      scenes are unchanged.
    - With `photo.events = []` or no `final` event → one `missing` beat (Review Focus 1).
  - `SCENES` checks:
    - The ids are exactly `["problem","photo","sound","honesty","danger","proof"]`.
    - `photo` has `note === "Drawn by us: no openly licensed photo of an error display exists"`.
    - `problem` has a `photos` beat with four `/demo/` sources.
    - `proof` has a `scores` beat and a `limits` beat.
  - `offline`: `JSON.stringify(SCENES)` doesn't match `/https?:\/\//`.
  - `SCORES`: seven rows, with labels in the Global Constraints order and values matching that table.
- [ ] **Step 2: Run `cd frontend && npx vitest run src/demo/demo.test.ts`** → FAIL (no modules).
- [ ] **Step 3: Implement.**
  - **Scene beats:**
    - `problem`: title "Your first apartment. Something beeps. The landlord doesn't answer.", then
      `photos` (four items, captions "Breaker panel", "Leaking pipe", "Thermostat", "Smoke detector"),
      then `promises`.
    - `photo`, `sound`, `honesty` and `danger`: `[{ kind: "turn" }]`.
    - `proof`: `title` ("Wi-Fi off. Everything ran on this laptop."), then `scores`, then `limits`.
  - **`turnAt`:** build `sentFiles` from `request.files`, using `kindOf(basename)` and the web path as
    `url`.
  - **Tests:** give the tests a fixture recording built in the test file. Don't depend on real
    recordings.
- [ ] **Step 4: Run `cd frontend && npx vitest run src/demo/demo.test.ts`** → PASS. Then `npm run typecheck`.
- [ ] **Step 5: Commit.**
  ```bash
  git add frontend/src/demo
  git commit -m "feat(ui): the demo's six scenes and scores, with each recording split into one step per key press"
  ```

### Task 5: The `#/demo` page

**Files:**
- Create: `frontend/src/components/demo/DemoPage.tsx`, `frontend/src/components/demo/DemoPage.test.tsx`
- Modify: `frontend/src/App.tsx` (`routeOf`, render `DemoPage`), `frontend/src/components/Redesign.test.tsx:22-28`
  (routes test), `frontend/src/index.css` (append a `/* ---------- demo ---------- */` section)

**Interfaces:**
- Consumes: `SCENES`, `RECORDINGS`, `expandBeats`, `turnAt`, `firstBeatOf`, `SCORES` and `SCORE_RUNS`
  (Task 4). `TurnView` (props `turn`). The `hazard` class and the tokens (Task 1).
- Produces: `DemoPage(props?: { scenes?: Scene[]; recordings?: Partial<Record<SceneId, Recording>> })`.
  Its defaults are the real `SCENES` and `RECORDINGS`, so tests can inject fixtures.

- [ ] **Step 1: Write the failing tests** in `DemoPage.test.tsx`, using fixture recordings for all four
  turn scenes, and update `Redesign.test.tsx`.
  - `routes`: `routeOf("#/demo") === "demo"`, `routeOf("#/demo/x") === "demo"`,
    `routeOf("#/demos") === "landing"`. The existing `ask` and `landing` cases still pass.
  - `ArrowRight advances, ArrowLeft goes back, no wrap`:
    - On the first beat, `ArrowLeft` keeps the problem title on screen.
    - Pressing `ArrowRight` n times reaches the last beat, and one more press changes nothing.
    - `Space` and `PageDown` advance; `PageUp` goes back.
  - `number keys jump`: `3` shows the sound scene's first beat. The scene strip button "Sound" has
    `aria-current="step"`.
  - `scene strip click jumps`: clicking "Danger" shows the danger question.
  - `photo scene builds up`: after jumping to scene 2, the citation card is absent until the press
    that reaches the citation cut. The corner label reads `Recorded on the M4, full profile, 20 Nov 2026`.
  - `danger scene shows the stripe and no steps`: on the danger scene's last beat,
    `.card--safety .hazard` exists and no `CitationCard` is shown.
  - `missing recording`: with `recordings` lacking `honesty`, scene 4 shows
    `This scene hasn't been recorded. Run scripts/record_demo.py.` Pressing `5` still shows the danger
    scene (Review Focus 6).
  - `missing media`: firing `error` on a problem-scene `<img>` replaces it with a tile containing
    `Run scripts/fetch_demo_media.py`.
  - `blocked audio shows a play button`: stub `HTMLMediaElement.prototype.play` to return
    `Promise.reject(new DOMException("NotAllowedError"))`. On the sound scene's first beat, a button
    `Play the sound` appears.
  - `Escape opens the app`: `Escape` sets `window.location.hash` to `#/ask`.
  - `keys are ignored in fields`: an `ArrowRight` keydown dispatched from an `<input>` doesn't advance.
  - `listeners removed on unmount`: after `unmount()`, with `location.hash = "#/demo"`, pressing
    `Escape` leaves the hash unchanged (Review Focus 7).
  - `credits`: the proof scene's last beat shows `Photos and sounds: Wikimedia Commons, see ASSETS.md`
    and a seven-row table.
- [ ] **Step 2: Run `cd frontend && npx vitest run src/components/demo src/components/Redesign.test.tsx`**
  → FAIL.
- [ ] **Step 3: Implement.**
  - **State:** `DemoPage` keeps one index into `expandBeats(...)`.
  - **Rendering:** draw every beat of the current scene up to the index. Turn beats render one
    `TurnView` with `turnAt(rec, upTo)`.
  - **Keys:** one `keydown` listener on `window`, added in `useEffect` and removed in its cleanup.
  - **Audio:** a demo-only `<audio src={web_file}>`. Call `play()` when the sound scene's first turn
    beat appears; if the promise rejects, show the button.
  - **Media fallback:** use `onError` on `<img>` to swap in the tile.
  - **Layout CSS:**
    - Answer text is at least 20px, and the page fits 1280×720.
    - Beats fade in over 180ms. Under `@media (prefers-reduced-motion: reduce)` there is no animation.
    - At 640px and below: one column, and the scene strip scrolls sideways in its own container.
    - Use tokens only.
- [ ] **Step 4: Run `cd frontend && npm test && npm run typecheck && npm run build`** → all pass.
- [ ] **Step 5: Look at it.** Run `npm run dev`, open `#/demo`, press `F`, and step through every beat
  with the arrow keys at 1280×720. Expect the missing-recording message on scenes 2–5 until Task 6.
- [ ] **Step 6: Commit.**
  ```bash
  git add frontend/src/components/demo frontend/src/App.tsx frontend/src/components/Redesign.test.tsx frontend/src/index.css
  git commit -m "feat(ui): a #/demo you step through with the arrow keys or a clicker, one piece of a real answer per press"
  ```
- [ ] **Step 7: Tell Akshayaa** that UI edits can resume once this is on `main`.

### Task 6: Record the scenes and fill the proof

**Files:**
- Create: `frontend/src/demo/recordings/{photo,sound,honesty,danger}.json` (written by the recorder)
- Commit: `results/summary_full.md` (already on disk)

This task needs real models, so it has no TDD cycle. Run it on the M4.

- [ ] **Step 1: Setup.** Run `uv run python scripts/make_samples.py`, then
  `uv run python scripts/fetch_demo_media.py`. Expect `washer_display_e21.jpg` in
  `frontend/public/samples/` and five files in `frontend/public/demo/`.
- [ ] **Step 2: Start the backend on `full`** with the project's usual server command, then check that
  `curl -s 127.0.0.1:8000/api/health` shows `"profile": "full"`.
- [ ] **Step 3: Run `uv run python scripts/record_demo.py`** → four `ok` lines, exit 0. If `sound`
  fails because it was heard as an alarm, pin a different Commons chirp in `config/demo_media.yaml`,
  following Task 2's rules, re-fetch, and run `--scene sound` again. Never edit a recording.
- [ ] **Step 4: Check by eye.** In `#/demo`, step through every scene and confirm:
  - The answers read well.
  - The E21 quote is highlighted.
  - The danger card shows no repair steps.
  - The corner date is today.
- [ ] **Step 5: Run `uv run pytest` and `cd frontend && npm test`** → green.
- [ ] **Step 6: Commit** (and `config/demo_media.yaml` and `docs/ASSETS.md` too, if Step 3 changed them).
  ```bash
  git add frontend/src/demo/recordings/*.json results/summary_full.md
  git commit -m "feat(ui): the demo plays four real answers recorded on the M4; full-profile eval scores 87/100"
  ```
