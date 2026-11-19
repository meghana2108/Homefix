# HomeFix build plan

**Now:** Wed Nov 18, ~21:00. **Code deadline:** Thu Nov 19, 23:59. Tag `v1.0-submission` by **Thu 22:00** at the latest (2 h buffer).
**Feature freeze:** Thu Nov 19, **14:00**. After freeze, only fixes, eval runs, slides, and the backup video.

## Reality check
The task list in [TEAM.md](TEAM.md) is ~20 h per person, but the wall clock is ~27 h including sleep. So we build in **priority order** and cut from the bottom:

| Priority | Scope | Why |
|---|---|---|
| **P0** | All 5 pipelines callable from the CLI + text verifier + code self-check + safety filter | 30% of the score is the random-item checklist, with Wi-Fi off |
| **P0** | Eval harness with real numbers for both profiles | "Our own test results" is part of that 30% |
| **P1** | Web UI over SSE: chat, attachments, all event types, latency badge | 25% usability: the live demo has to run start to finish |
| **P1** | Offline check passing on the M4 | Disqualifying if it fails live |
| **P2** | HomeFix manual layer (image → code → manual page) | Impact story (15%) |
| **P2** | Live mic over WebSocket, PWA/mobile | Bonus points |
| **P3** | Full model bake-offs (beyond the 2 top candidates), 7B coder swap | Architecture polish |

If we're behind at a milestone, drop P3, then P2 mobile, then the live mic. **Never** drop P0.

## Milestones
| ID | Milestone | Target | Owner |
|---|---|---|---|
| M0 | Environment + go/no-go passing on both Macs | Wed 22:30 | Both |
| M1 | API contract + mock server streaming events | Wed 23:30 | Meghana (contract), Akshayaa (mock) |
| M2 | All five pipelines working from `python -m app.cli` | Thu 10:00 | Each owner |
| M3 | Eval harness producing numbers | Thu 12:00 | Akshayaa (framework), owners (graders) |
| M4 | UI integrated end to end with the real backend | Thu 13:30 | Akshayaa (UI), Meghana (backend) |
| — | **FEATURE FREEZE** | **Thu 14:00** | Both |
| M5 | HomeFix layer (only if done by freeze; otherwise demo it from the CLI) | Thu 14:00 | Meghana |
| M6 | Offline hardening, final eval runs, README, tag `v1.0-submission` | Thu 22:00 | Both |

## Hour by hour
| When | Meghana (M4, full) | Akshayaa (M2, lite) |
|---|---|---|
| Wed 21:00–22:30 | Phase 0: setup, model pulls (~23 GB), go/no-go on M4 | Setup, model pulls (~10 GB), go/no-go on M2 |
| Wed 22:30–23:00 | **Joint:** agree the API contract (30 min) | **Joint** |
| Wed 23:00–01:00 | Backend skeleton: settings, Ollama client, memory manager, router, safety + tests | Mock server, `media/convert.py` + tests |
| *Sleep* | | |
| Thu 08:00 | **Sync (15 min)** | **Sync** |
| Thu 08:00–10:00 | Image + text pipelines (verifier) | Audio pipeline (ASR + CLAP + speech/non-speech) |
| Thu 09:00–10:00 | **Pairing on M4 (1 h):** Whisper model + video frame counts on full | **Pairing** |
| Thu 10:00–12:00 | Code pipeline; FastAPI + SSE behind the contract | Video pipeline; eval harness framework |
| Thu 12:00 | **Lunch sync (15 min)**: are both on track for freeze? | **Sync** |
| Thu 12:00–13:30 | Graders (image/text/code), bake-off brain candidates | Graders (audio/video), frontend switched to the real backend |
| Thu 13:30–14:00 | HomeFix manual flow (if P0/P1 green) | Live mic (if P0/P1 green) |
| **Thu 14:00** | **FREEZE SYNC (15 min)**: decide what ships | **FREEZE** |
| Thu 14:00–17:00 | Final eval run (full), fill MODELS.md/EVAL.md, architecture/results slides | Final eval run (lite), problem/impact slides, survey summary |
| Thu 17:00–19:00 | Offline check (Wi-Fi off) on M4, bug fixes | Offline check on M2, record the backup demo video |
| Thu 19:00–21:00 | **Joint:** demo rehearsal x3, README | **Joint** |
| Thu 21:00–22:00 | Tag `v1.0-submission`, push, verify the tag on GitHub | **End-of-day sync** |
