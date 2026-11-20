# Pitch demo and "maintenance tag" theme

Date: 2026-11-20 · Status: approved design, ready to plan

## Intent

Round 1 is a 5-minute pitch. 29 teams, 4 go to round 2. Today we would demo by typing into the live app
and waiting on the models while the clock runs. A stall or a wrong answer on stage costs us the slot.

The UI also reads as plain. It uses the same design system as Meghana's SecondOpinion project (same
fonts, token names and stamps), but it lacks that project's theme colour and its playable demo. The
default blue on off-white says nothing about home repair.

What should change:
1. A presenter-paced demo at `#/demo`. Meghana presses the right arrow (or a clicker), and the next
   piece of a real, pre-recorded HomeFix answer appears. It runs on its own clock, never on a model.
2. A light industrial theme across the whole app: "maintenance tag", warm concrete with safety orange
   (option A from the mockups, chosen 2026-11-20).

## Goals

- `#/demo` route in `frontend/src/App.tsx`, next to `#/ask` and the landing page.
- Six scenes, about 4 minutes in total, leaving 1 minute for questions:

  | # | Scene | Beats (one key press each) | Media |
  |---|---|---|---|
  | 1 | The problem (20 s) | headline, then a strip of 4 real photos of things that go wrong, then the three promises (offline, cites the page, stops at danger) | Commons: breaker panel, leaking pipe, thermostat, smoke detector |
  | 2 | Photo to manual (50 s) | the photo, then the question, then each step chip as recorded, then the citation card with the quote highlighted, then the answer | our drawn washer display `/samples/washer_display_e21.jpg` (made by `scripts/make_samples.py`), labelled "Drawn by us: no openly licensed photo of an error display exists" |
  | 3 | Sound (40 s) | the clip plays, then the sound bars, then the answer | Commons: `Smoke detector alarm battery beep.webm` |
  | 4 | Honesty (30 s) | the question, then the amber "Not in the document" card | none (Unit 4B guide) |
  | 5 | Danger (30 s) | the question, then the hazard-striped stop card, with no repair steps | none |
  | 6 | Proof (50 s) | Wi-Fi off, then a two-column scores table (`full` on M4, `lite` on M2), then three limits | none |

- What the recorder sends (form fields of `POST /api/chat`: `message`, `files`, `manual_id`), and the
  outcome a recording must have to be kept. A recording that misses its outcome is not saved, and the
  script exits non-zero and names the scene. Then pick a different input; never edit events.

  | Scene | `message` | `files` | `manual_id` | Must have |
  |---|---|---|---|---|
  | photo | "What should I do?" | `washer_display_e21.jpg` | `apartment_guide_unit_4b` | a `citation` event whose quote contains "E21", no `refusal`, a `final` |
  | sound | "What is this sound?" | the chirp `.wav` | none | a `sound_labels` event whose top label is `smoke alarm chirp`, no `refusal`, a `final` |
  | honesty | "Is there a warranty on the washer?" | none | `apartment_guide_unit_4b` | a `refusal` with reason `not_in_document`, a `final` |
  | danger | "I smell burning from the outlet behind the fridge" | none | none | a `refusal` with reason `safety`, a `final` |

  Scene 3's catch: the safety rule (`app/safety.py` `ALARM_LABELS`) treats "smoke detector, smoke
  alarm" with a score of at least 0.5 as a sounding alarm and shows the stop card. A chirp should come
  out as `smoke alarm chirp`, which is not on that list. If the Commons clip comes out as an alarm,
  the recorder rejects it and we pin a different Commons chirp.
- Scene 6 content:
  - Scores table, with one row each for image count, sound top-1, speech transcript, text answers,
    text refusals, code pass@1 and video. Values come from `results/summary_full.md` (run
    `20261120-1009-full-all`, 87/100) and `results/summary_lite.md` (run `20261119-1404-lite-all`).
  - The three limits, taken from the landing page's `LIMITS`:
    1. "It answers only from what you give it."
    2. "Real manuals print error codes as pictures."
    3. "It is a hackathon prototype."

- Every answer on screen is a real HomeFix output. `scripts/record_demo.py` sends each scene's real
  input to `POST /api/chat` on the `full` profile and saves the raw SSE events, unedited, to
  `frontend/src/demo/recordings/<scene>.json`. The demo replays those events through the existing
  `frontend/src/state/reduce.ts` and renders them with the existing `TurnView`, so demo cards and app
  cards are the same components.
- `scripts/fetch_demo_media.py` downloads a pinned list of Wikimedia Commons files once, at setup.
  The list is `config/demo_media.yaml`, with these fields per file: `file` (Commons title), `url`,
  `author`, `license` (CC0, CC BY or CC BY-SA only), `sha256` and `use` (the scene). The script
  converts audio to 16 kHz mono `.wav` with ffmpeg and writes everything to the gitignored
  `frontend/public/demo/`. If a checksum doesn't match, it exits with an error and names the file.
- `docs/ASSETS.md` gets one row per Commons file (title, author, license, URL). Scene 6 shows the
  same credits in small print: "Photos and sounds: Wikimedia Commons, see ASSETS.md".
- Controls:
  - Right arrow, Space or PageDown (what clickers send): next beat.
  - Left arrow or PageUp: previous beat.
  - Number keys 1–6: jump to that scene.
  - A scene strip at the bottom: clickable, with the current scene marked.
  - `Esc`: go to `#/ask`, the live app.
  - `F`: fullscreen.
- A corner label on every scene: "Recorded on the M4, `full` profile, 20 Nov 2026". It is honest
  without slowing the pitch.
- Theme: replace the tokens at the top of `frontend/src/index.css` with option A's values:
  - paper `#f4f2ee`, sheet `#ffffff`, wash `#f0ece5`
  - ink `#1c1917`, ink-soft `#44403c`, ink-faint `#78716c`
  - rule `#e2ddd4`, rule-strong `#b8b0a3`
  - pen `#c2410c`, pen-deep `#9a3412`, pen-tint `#fdeee4`
  - new tokens: `--panel` `#1f1d1b`, `--seg` `#ff8a3d`, `--seg-dim` `#5a3a26`, `--hazard` `#f5b800`
  - outcome tokens unchanged (answered teal-green, not-found amber, danger red)
- Theme parts:
  - The orange 4 px top border.
  - The seven-segment display (`landing/SevenSeg.tsx`) on a dark `--panel`.
  - A hazard-stripe band at the top of `RefusalCard`, only when `reason === "safety"`. The amber
    `not_in_document` card has no stripe.
  - A soft orange glow behind the landing hero.
  - Every page uses the same tokens: landing, `#/ask` and `#/demo`.

## Non-goals

- No backend changes: no new endpoint, SSE event or pipeline change. The recorder is a client of
  `POST /api/chat`.
- No live mode inside `#/demo`. Live questions go through `Esc` to `#/ask`.
- No new layout for `#/ask` (no step rail) in this round. It gets the new colours only.
- No video scene, no code scene, and no audio from Freesound (downloads there need an account).
- No dark theme.

## Anti-goals

- A network call while the app runs. `fetch_demo_media.py` is a setup step and is never imported by
  `app/`.
- An edited recording. If a scene's real output is wrong, pick a different input and record it again.
  Never hand-edit events.
- Practice-pack media or answers in any recording, scene or doc (hard rule 1).
- A danger scene that shows any repair step.
- An answer card in the demo that differs from what `#/ask` would show for the same events.
- A text answer without its verified quote (scene 2 must show the citation card).
- Copy that hides that scene 2's photo is drawn by us.

## Constraints

- Offline at the venue. Demo media, fonts (already `@fontsource`) and recordings are all local. No CDN.
- Media stays out of git: `frontend/public/demo/` is gitignored. The hard-rule test already bans
  tracked `.wav/.mp4/.pdf`; Commons `.jpg` files are kept out by the ignore rule too. Recordings
  (`.json`, text only) are committed.
- Recordings must not inline media. No event carries image data today (`frames` holds timestamps only,
  `app/contracts.py`). The recorder checks that no recorded string starts with `data:` or is longer
  than 4,000 characters.
- The recorder can't choose a profile: the server's profile is fixed at start. It reads `profile` from
  `GET /api/health` and refuses to record unless it is `full`.
- Demo keys (arrows, Space, PageUp/PageDown, 1–6, `F`, `Esc`) are attached only while `#/demo` is
  open, so typing in the `#/ask` composer is never affected.
- `routeOf` in `frontend/src/App.tsx` becomes `"landing" | "ask" | "demo"`, and its tests are updated.
- Contrast: white on pen `#c2410c` is about 5.2:1 and ink on paper about 15:1, which passes WCAG AA.
  Outcome stamps keep their icon and word, because orange sits near amber and red.
- Motion: beats fade in over 150–200 ms. With `prefers-reduced-motion`, they appear with no
  movement. No motion on load outside `#/demo` and the landing hero.
- Projector: readable at 1280×720. The answer text is at least 20 px in `#/demo`.
- Timing is the presenter's. Nothing advances on its own except the scene 3 audio, which plays when
  its beat appears.
- Memory and latency: the demo uses no models. The recorder runs once on the M4 (`full`, at most 11 GB
  of models).
- Ownership: `index.css`, `Landing.tsx`, `RefusalCard.tsx` and `SevenSeg.tsx` are Akshayaa's. She
  pauses UI edits while the theme task runs. The demo itself is new files, so it doesn't conflict.

## Approaches considered

1. **Presenter-paced replay of real recordings (chosen).** Reliable on stage, every output real, the
   presenter sets the pace.
2. Live calls with a recorded fallback. More "real-time", but a stall still eats pitch seconds, and
   the presenter can't rehearse exact timing.
3. A screen recording (video). Simplest, but not interactive. You can't pause on a beat or jump to a
   scene during questions.

For the theme, options B (toolbox teal) and C (steel with safety yellow) were mocked up. Meghana
picked A.

## Design

### Data shapes

`frontend/src/demo/scenes.ts`:

```ts
export type Beat =
  | { kind: "title"; text: string; sub?: string }
  | { kind: "photos"; items: { src: string; caption: string }[] }        // /demo/... paths
  | { kind: "promises" }
  | { kind: "media"; src: string; label?: string; audio?: boolean }
  | { kind: "turn" }                   // the recording, one beat per cut (see cutPoints)
  | { kind: "scores" }
  | { kind: "limits" };

export interface Scene {
  id: "problem" | "photo" | "sound" | "honesty" | "danger" | "proof";
  title: string;                 // scene strip label
  question?: string;             // shown as the user's message
  recording?: string;            // "photo" -> recordings/photo.json
  beats: Beat[];
}
```

The beats in a scene stack. Beat n shows everything from beats 0..n.

The user's photo or clip is not a separate beat. It shows in `TurnView`'s own "You" bubble: the demo
builds `sentFiles` from `request.files`, with `url` set to the `/demo/...` or `/samples/...` path. That
way the demo card is the same component as the app card. The `media` beat is only for scene 1's
photo strip. Scene 3's clip starts playing when the turn's first beat appears. A small demo-only
`<audio>` element plays it, and `SentFiles` is not changed. If the browser blocks autoplay, that
element shows a play button.

`events` beats are computed, not written by hand, because the number of steps depends on the real
run. `cutPoints(events)` in `frontend/src/demo/cuts.ts` returns one cut after each `status` event
whose stage is new, one after `transcript`, one after `sound_labels`, one after `citation` or
`refusal`, and one at `final`. A scene's turn gets one beat per cut. The beats before `final` keep
`TurnView`'s live line, so they read as an answer arriving.

So `Beat`'s `events` variant is `{ kind: "turn" }`, which expands to one beat per cut.

`frontend/src/demo/recordings/<id>.json`:

```json
{ "scene": "photo", "recorded_at": "2026-11-20T21:40:00", "profile": "full",
  "request": { "message": "What should I do?", "files": ["/samples/washer_display_e21.jpg"],
               "manual_id": "apartment_guide_unit_4b" },
  "events": [ { "type": "status", "...": "..." } ] }
```

`frontend/src/demo/scores.ts` holds the scene 6 numbers. They are copied by hand from
`results/summary_full.md` and `results/summary_lite.md`, with the run id of each.

### Flows

- Setup on each Mac: `uv run python scripts/make_samples.py` (the E21 photo and the Unit 4B guide),
  then `uv run python scripts/fetch_demo_media.py` (Commons files).
- Recording, once, on the M4:
  1. Start the backend.
  2. `uv run python scripts/record_demo.py --profile full`.
  3. Check each scene's output by eye.
  4. Commit `frontend/src/demo/recordings/`.
- At the pitch:
  1. Open `http://127.0.0.1:5173/#/demo`.
  2. Press `F`.
  3. Step through with the clicker.
  4. Press `Esc` for live questions.

### UI states

- **Recording missing** (JSON not present): the scene shows "This scene hasn't been recorded. Run
  `scripts/record_demo.py`." The other scenes still work.
- **Media missing** (file under `/demo/` returns 404): a grey tile with the caption and "Run
  `scripts/fetch_demo_media.py`". It never breaks the scene.
- **Audio blocked** (the browser refuses autoplay): a play button appears on the sound beat.
- **First and last beat**: left arrow on the first beat and right arrow on the last do nothing (no wrap).
- **Small screen** (≤ 640 px): single column, with the scene strip scrolling sideways in its own container.

### SSE events

None new. The recorder consumes the existing `status`, `token`, `transcript`, `sound_labels`,
`citation`, `refusal`, `error` and `final` events exactly as `POST /api/chat` sends them.

## Left to the builder

- Which Commons files to pin, from the candidates found on 2026-11-20 (see below), after checking each
  file page's license.
- Exact scene copy, keeping the plain style from CLAUDE.md.
- Whether the scene strip shows titles or numbers at 1280 px.

Candidate Commons files: `Eaton circuit breaker panel open.JPG`, `Leaking pipe by Saltash Field -
geograph.org.uk - 7324720.jpg`, `Person holds a thermostat showing room temperature in a home
setting.jpg`, `Smoke detector (1).JPG`, `Smoke detector alarm battery beep.webm`.
