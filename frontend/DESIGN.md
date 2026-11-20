# HomeFix design system: "the repair card"

The card taped inside a closet door that tells you what each beep and code means. Calm, plain, honest.
Paper, ink, one blue pen, and three stamps. Not a SaaS dashboard and not a chat toy.

## Two places
- **Front door** (`#/`, `components/landing/`): the question HomeFix answers ("Is it broken, or is it
  normal?"), one worked example that plays its steps on a loop (pause button; reduced motion opens on the
  answer), why it exists, what you get, what you can bring, what an answer looks like, what it can't do,
  and one way in: "Ask about something at home".
- **Workspace** (`#/ask`, `components/Workspace.tsx`): the rail "What happened to your question" (large
  screens) shows every step of the selected question as it runs: title, what it does, what it found
  (`state/steps.ts`, built from the real SSE events). On small screens the same list sits inside each
  answer under "What happened, step by step".

## Every answer, at a glance
One panel per answer: an **outcome stamp** first (icon + words + colour, never colour alone), then the
answer, then its evidence with a plain label ("Word for word from the document", "The closest matching
sounds", "Transcript").

| Stamp | When |
|---|---|
| green "From the manual, page N" / "Code tested: passed N of N" | a verified quote, or code that passed |
| amber "Not in the document" / "Couldn't answer this one" | a refusal: say why and what to try next |
| red "Stop: this could be dangerous" | the safety filter matched; only the safety card shows |
| blue "Answered from your photo", "Sound identified", ... | a direct answer from a photo, clip or sound |
| dashed blue "HomeFix needs to know more" | a `clarify` event: HomeFix asks instead of guessing |

## Asking instead of guessing
A vague question about a photo ("What is this?", or none), a photo question the model can't answer, a code
that isn't on the display, or a question two manuals could answer gets a question back, never a guess
(`app/clarify.py`). The card shows the question, "What HomeFix could read" (the display's own words, serif),
and one-click replies. Clicking one asks again with the same files; typing below answers it too (the composer
says "Answering HomeFix's question", with a way out: "Ask something new instead").

## Voices
| Voice | Font | Use |
|---|---|---|
| The interface | IBM Plex Sans | labels, buttons, answers |
| The document's own words | Newsreader (serif) | manual quotes, transcripts, the live mic text |
| The data | IBM Plex Mono | times, percentages, profile badge |

Fonts are bundled with `@fontsource` (no network at runtime). Sentence case everywhere. No ALL-CAPS labels.

## Tokens (`src/index.css`)
paper / sheet / wash (surfaces), ink / ink-soft / ink-faint (text), rule / rule-strong (hairlines),
pen / pen-deep / pen-tint (the one action colour), answered / notfound / danger with `-tint`.
Never raw hex in components (the seven-segment display and code blocks are the only drawings).

## Rules
- One primary action per screen: "Ask" in the workspace, "Ask about something at home" on the front door.
- Depth from hairlines and whitespace. Shadows only on the hero example and popovers.
- Icons: `lucide-react` only, through `components/Icons.tsx`, `aria-hidden`, one stroke weight. No emoji.
- Touch targets at least 44 px. Visible focus. Motion only answers an action, except the hero example.
- Plain words from the renter's side: "Check for danger", not "safety_check".
- Responsive from 375 px with no horizontal scroll.
- Keep the SSE contract (`src/contract.ts`), the `aria-busy` on `.turn`, and the roles tests use.
