# Demo scripts

## Round 1: 5-minute pitch
| Time | Who | What |
|---|---|---|
| 0:00–0:40 | Akshayaa | **The moment.** "It's 11 PM, your first apartment, and the washer is beeping and showing E21. Do you call the landlord, pay $120 for a visit, or is it a 2-minute fix?" Survey stat: _N of M renting students said …_ |
| 0:40–1:00 | Akshayaa | **The user:** students renting their first place. **Why local:** photos of your home stay on your laptop; no per-question cost; works when the broken thing is the Wi-Fi. |
| 1:00–3:00 | Meghana | **Live demo, Wi-Fi off** (turn Wi-Fi off on stage): (1) play the beep → "washing machine beeping"; (2) photo of "E21" with the washer manual selected → reads E21, cites the manual page: "clean the drain pump filter"; (3) ask something the manual doesn't say → "The document doesn't contain the answer"; (4) "I smell burning" → fixed safety message. |
| 3:00–4:00 | Meghana | **Architecture:** one diagram. Rule-based router (0 ms), verifier that refuses unsupported answers, code self-check in a sandbox, models chosen by bake-off. Results table (both laptops). |
| 4:00–4:40 | Akshayaa | **It runs on 8 GB.** Same app on the M2 Air (lite profile). Impact: timed test (with vs. without HomeFix). |
| 4:40–5:00 | Both | Ask + close. |

## Final round: judges pick random items
1. Before judges arrive: `bash scripts/offline_check.sh full` → PASSED, Wi-Fi off, demo mode on (models warmed).
2. Show the five capability tiles: image, audio, text, code, video. Let judges drop **any** file.
3. For each item: drag the file in, type their question, point out the **latency badge**, the **citation** (text), the **pass/fail badge** (code), the **sound bars** (audio).
4. Surprise items: the app accepts mp3/m4a/mov/webm/png/heic/docx (normalized by ffmpeg). Unsupported types get a clear message, not a crash.
5. If anything fails: switch to the M2 (`lite`) laptop (steps below), or play the backup video for that segment. Say what failed and why; naming limits scores on architecture.

## Backup on the M2 (8 GB, `lite`)
With Wi-Fi off there is no network between the two laptops, so the M4 browser can't open the M2's URL.
The backup is the M2 itself: keep it open on the table, app running, models warm.

Before judges arrive (Wi-Fi still on is fine for steps 1–3):
1. Open Ollama (menu bar icon). Check: `ollama list` shows `qwen3-vl:2b-instruct` and `qwen2.5-coder:3b`.
2. Terminal 1: `uv run uvicorn app.api.main:app --port 8000` (`PROFILE=lite` comes from `.env`).
3. Terminal 2: `cd frontend && npm run dev`, then open http://localhost:5173. The header says `lite · M2`.
4. Turn Wi-Fi off. Terminal 3: `bash scripts/offline_check.sh lite` → `OFFLINE CHECK PASSED`.
5. Warm the models: ask one photo question and play one sound. The first photo after a cold start
   takes about a minute (model load); after that a photo count takes about 15 s.
6. Keep the M2 plugged in, with sleep off (`caffeinate -dis` in a spare terminal).

What `lite` does differently: a 2B vision model (a less detailed reading of photos), 8 video frames instead of 16,
one model loaded at a time (so switching between a photo and a code question adds a model load).

Phone (only if the venue allows a local network): `bash scripts/https_dev.sh` prints
`https://<laptop-ip>:5173`. The phone must trust the laptop's mkcert certificate once (the script prints
the steps). With Wi-Fi off there is no local network, so show the recorded phone clip instead (RISKS.md #10).

## Backup
- `docs/demo_backup.mp4` is *not* committed (media). Stored on both laptops + a USB stick.
