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
5. If anything fails: switch the browser to the M2 (`lite`) URL, or play the backup video for that segment. Say what failed and why; naming limits scores on architecture.

## Backup
- `docs/demo_backup.mp4` is *not* committed (media). Stored on both laptops + a USB stick.
