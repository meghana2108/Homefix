# Team and ownership

| | Meghana (`meghana2108`) | Akshayaa (`akshayaamahesh`) |
|---|---|---|
| Machine | MacBook Pro M4, 16 GB | MacBook Air M2, 8 GB |
| Profile | `full` (demo inference server) | `lite` (8 GB proof + demo backup) |
| Owns end to end | Image, Text, Code, backend, HomeFix manuals | Audio, Video, frontend, eval framework |
| Strengths | LLM pipelines, grounded verification, backend, React | _Akshayaa to fill in_ |

**Vertical-slice rule:** whoever owns a modality owns its pipeline, its grader in `eval/grade.py`, its UI component, and the judges' questions about it.
**Unblocking rule:** Akshayaa never waits on the backend. She builds against `mock_server/`, then switches with `VITE_API_URL`.
**Branches:** `feat/<area>`. Merge to `main` only with `uv run pytest` green.

## Syncs (15 min each)
- Thu 08:00, start of day: blockers, today's order
- Thu 12:00, lunch: on track for freeze?
- **Thu 14:00, feature freeze:** decide what ships, what gets cut
- Thu 21:00, end of day: tag, push, rehearsal notes

## Meghana (~20 h)
- [ ] **Repo, env scripts, `go_no_go.py`, model pulls** (2 h). *Done when:* go/no-go prints GO on the M4; `.gitignore` committed first; hard-rule tests pass.
- [ ] **Model serving: Ollama client, profiles, memory manager, coder swap** (2 h). *Done when:* `memory.py` loads/unloads per profile; a code request on lite emits a `status: loading_model` event with swap ms; coder prefetch starts on `code_intent`.
- [ ] **FastAPI backend, SSE, router, safety pre-filter** (2.5 h). *Done when:* `/api/chat` streams contract events; router unit tests cover every question type; safety tests cover gas/sparks/smoke/wires/water and 10 benign look-alikes ("smoke detector battery", "gas stove recipe"?).
- [ ] **Image pipeline + grader + prompts** (1.5 h). *Done when:* count questions answer number first; read questions allow "can't tell"; grader reports count-exact and fuzzy match.
- [ ] **Text pipeline (full-doc, RAG, quote verification, refusal) + grader + citation card** (3.5 h). *Done when:* verifier unit tests pass; refusal precision/recall measured on the 20 practice text items and threshold recorded in MODELS.md; citation card renders quote + page.
- [ ] **Code pipeline (generate, extract, doctest, retry) + grader + result panel** (3 h). *Done when:* extractor tests pass; self-check runs in a subprocess with a 10 s timeout and no network; pass@1 on practice code items recorded.
- [ ] **HomeFix manual layer** (2 h). *Done when:* sidebar lists `data/manuals/*.pdf`; a photo of "E21" + a selected manual returns the manual's answer with the page cited.
- [ ] **Full-profile bake-offs (image, text, code); MODELS.md** (1.5 h). *Done when:* results table filled in with accuracy + p50 latency + memory.
- [ ] **Slides: architecture, model choices, results** (1 h)
- [ ] **Final integration, offline check on M4, `v1.0-submission` tag** (1 h). *Done when:* `offline_check.sh full` prints PASSED with Wi-Fi off; tag visible on GitHub.

## Akshayaa (~20 h)
- [ ] **Media normalization `app/media/convert.py` + tests** (1 h). *Done when:* jpg/png/heic/webp → JPEG ≤1280; wav/mp3/m4a/webm/ogg → 16 kHz mono WAV; mp4/mov/webm → H.264 ≤720p; pdf/txt/md/docx → text with page markers; unsupported → `refusal: unsupported_file`, never a crash.
- [ ] **Audio pipeline: file ASR, CLAP, speech vs non-speech, vocabulary + grader** (3 h). *Done when:* returns transcript + answer for speech, top-3 labels for sounds; WER and top-1/top-3 reported by the grader.
- [ ] **Live mic: WebSocket, chunked transcription, mic UI + live transcript + sound bars** (2 h). *Done when:* partials appear ≤2 s behind on the M2; on stop, the final transcript replaces the partials.
- [ ] **Video pipeline: timestamped frames, sharp frames for reading, caching + grader** (2.5 h). *Done when:* frames are labelled "Frame k at t=…s"; read questions add the 2 sharpest frames; a cache hit on the same file hash skips extraction.
- [ ] **Frontend shell** (4.5 h): chat, attachments, drag-and-drop, streaming events, status chips, latency badge, manual picker, PWA. *Done when:* every event type in the contract renders; works on a phone-width viewport.
- [ ] **Mock server from the contract** (1 h). *Done when:* streams realistic events for all 5 modalities + refusal + safety, with delays.
- [ ] **Eval harness framework `eval/run.py`, `eval/report.py`; lite runs** (2.5 h). *Done when:* `python -m eval.run --profile lite --modality all` writes `results/raw/<run_id>.jsonl` and `results/summary_lite.md`.
- [ ] **HomeFix assets** (1.5 h): beeps, error-display photos, manuals, smart-plug CSV, appliance labels. *Done when:* every asset listed in ASSETS.md with source + license.
- [ ] **Survey (10–15 renting students) + timed comparison test** (1 h)
- [ ] **Slides: problem, user, impact, demo flow; backup video; offline check on M2** (1 h)

## Shared
- [ ] Phase 1 contract session (30 min, Wed 22:30)
- [ ] Pairing on the M4 (1 h, Thu 09:00): Whisper turbo vs small.en, video frame count 8/12/16 on full
- [ ] README, demo rehearsal, 14:00 freeze decision
