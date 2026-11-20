# Demo scripts

## Round 1: 5-minute pitch
| Time | Who | What |
|---|---|---|
| 0:00–0:40 | Akshayaa | **The moment.** "It's 11 PM, your first apartment, and the washer is beeping and showing E21. Do you call the landlord, pay $120 for a visit, or is it a 2-minute fix?" Survey stat: _N of M renting students said …_ |
| 0:40–1:00 | Akshayaa | **The user:** students renting their first place. **Why local:** photos of your home stay on your laptop; no per-question cost; works when the broken thing is the Wi-Fi. |
| 1:00–3:00 | Meghana | **Live demo, Wi-Fi off** (turn Wi-Fi off on stage): (1) play the beep → "washing machine beeping"; (2) photo of "E21" (manual left on "automatic") → "Using the manual: Unit 4B apartment guide", reads E21, quotes p. 2: "clean the drain pump filter"; say the guide is a sample landlord's guide we wrote, because real manuals print codes as pictures; (3) ask something the guide doesn't say ("Is there a warranty on the washer?") → "Not in the document"; (4) "I smell burning" → fixed safety message. |
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
0. Once per Mac, with Wi-Fi on: `uv run python scripts/make_samples.py` (drawn samples and our four sample
   guides) and `uv run python scripts/fetch_real_samples.py` (real photos from Wikimedia Commons, the EPA mold
   guide and CPSC carbon monoxide sheet, a real week of household power data; the two guides also go on the
   manual shelf). Wikimedia rate-limits bursts; if it refuses, copy the folder from the other Mac:
   `uv run python scripts/fetch_real_samples.py --from /path/to/other/frontend/public/samples`.
   None of these files are in git. The gallery then has 38 one-click examples, real ones first, each run
   on the 8 GB Mac on 2026-11-19. Sounds, voice notes and clips are still ones we made (see below).
   For the repair-request demo, make_samples.py also writes `washer_display_e21_edited.jpg`: the E21 photo with
   one pixel changed. Run the E21 example, press "Make a repair request", then "Check a file against this
   request": the original says "Matches … not changed"; the edited copy says "Doesn't match", with both
   fingerprints side by side.
Before judges arrive on the M4 (the demo laptop), with the API running:
   `uv run python scripts/demo_check.py` waits until the header's "Getting ready" is done, asks one question of
   each kind through the API (photo + manual, sound, voice note, document, manual, danger, code, a photo right
   after code, video) and prints each one's seconds and OK / SLOW / FAIL. Run it twice: the second run is the
   warm number the judges will see. If anything is SLOW, run `ollama stop qwen3-vl:8b-instruct`, restart the
   API, and run it again (Ollama's memory grows over a long session).
   Video on the M4 is the slowest step (38.8 s median, target 25 s). To try fewer frames without changing code:
   `uv run python -m eval.run --profile full --modality video --set video.frames=12` and compare accuracy with
   `results/summary_full.md` before changing `config/profiles/full.yaml`.
1. Open Ollama (menu bar icon). Check: `ollama list` shows `qwen3-vl:2b-instruct` and `qwen2.5-coder:3b`.
2. Terminal 1: `uv run uvicorn app.api.main:app --port 8000` (`PROFILE=lite` comes from `.env`).
3. Terminal 2: `cd frontend && npm run dev`, then open http://localhost:5173. The header says `lite · M2`.
4. Turn Wi-Fi off. Terminal 3: `bash scripts/offline_check.sh lite` → `OFFLINE CHECK PASSED`.
5. Warm the models: ask one photo question and play one sound. The first photo after a cold start
   takes about a minute (model load); after that a photo count takes about 15 s.
6. Keep the M2 plugged in, with sleep off (`caffeinate -dis` in a spare terminal).
7. Free the memory: quit Teams, WhatsApp, Safari and anything else big, and stop MySQL. 8 GB only fits
   HomeFix alone. With those open (2026-11-19) the Mac swapped 9 GB and one 10 s voice note took 7.7 s
   to transcribe one time and 24.6 s the next. Check `memory_pressure | tail -1` says 40% free or more.

What `lite` does differently: a 2B vision model (a less detailed reading of photos), 8 video frames instead of 16,
one model loaded at a time (so switching between a photo and a code question adds a model load).

Phone (only if the venue allows a local network): `bash scripts/https_dev.sh` prints
`https://<laptop-ip>:5173`. The phone must trust the laptop's mkcert certificate once (the script prints
the steps). With Wi-Fi off there is no local network, so show the recorded phone clip instead (RISKS.md #10).

## Pitch demo (#/demo)
A page you step through in front of the room, one scene per screen. Each scene builds up by itself, one
step per second, ending with a real answer that we recorded on the M4. It never calls a model, so it works with Wi-Fi off.

Set up once per Mac:
1. `uv run python scripts/make_samples.py`
2. `uv run python scripts/fetch_real_samples.py` (needs the network once). On the M2, copy a samples folder
   from the M4 and run `uv run python scripts/fetch_real_samples.py --from <copied folder>` instead.

Run it:
1. Start the backend, then `cd frontend && npm run dev`.
2. Open http://localhost:5173/ and click "Ask about something at home" (it opens `#/demo` at scene 1), then
   press `F` for full screen. "Open HomeFix" in the top bar, or `Esc` in the demo, opens the live app.
3. `→`, Space or PageDown (or a clicker) goes to the next scene. Pressed while a scene is still building,
   it shows the rest of that scene at once instead. `←` or PageUp shows the previous scene complete.
   `1`-`8` jump to a scene and play it.
4. `Esc` opens the live app. In full screen the first `Esc` only leaves full screen; press it again.

The address shows your scene (`#/demo/3` is scene 3). A reload, or a clicker's F5, comes back to that scene,
shown complete.
Do not press the clicker's slideshow button: it sends F5 then Esc, and the Esc leaves the demo. F5 alone
is safe.

The scenes: 1 the problem, 2 photo to manual, 3 sound, 4 video, 5 honesty, 6 danger, 7 code, 8 proof.
The video scene uses `warning_lights.mp4` from `scripts/make_samples.py` (made by us; the page says so). Its
clip plays muted by itself when the scene opens and ends on four lights, as the answer says. The code scene
asks for a Fahrenheit to Celsius function; it is recorded only if its examples passed in the sandbox.

Re-record a scene (backend running on `full`):
`uv run python scripts/record_demo.py --scene <id>`
Scene ids: `photo`, `sound`, `video`, `honesty`, `danger`, `code`. Never edit a file in `frontend/src/demo/recordings/` by hand.

## Backup
- `docs/demo_backup.mp4` is *not* committed (media). Stored on both laptops + a USB stick.
