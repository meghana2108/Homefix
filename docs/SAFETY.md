# HomeFix safety design

Date: 2026-11-20 · Measured on the M2 MacBook Air (8 GB, `lite`, `qwen3-vl:2b-instruct`, `bge-small-en-v1.5`).

## The rule everything follows

**Fixed rules have the final say. AI can make HomeFix more careful (stop, ask, refuse), never less.**

A model can add a safety stop, a question back or a "look again". It can never remove a regex stop, skip the
quote check, or turn "I don't know" into an answer. If a model can't load, the fixed rules still run.

We don't ask the 2B model whether it is sure. We measured that it can't tell: told to reply "ASK:" when unsure,
it did so for every photo, clear ones included. So models are used for what they are good at (reading a display,
describing a photo, comparing meanings), and our code makes the decisions.

## The layers, in the order they run

| # | Layer | Code | What it catches | Fixed or AI |
|---|---|---|---|---|
| 1 | Danger words | `app/safety.py`, `config/safety_rules.yaml` | "I smell gas", "sparks", "water near the outlet" in a question or voice-note transcript | Fixed (regex) |
| 2 | Danger by meaning | `app/safety_semantic.py`, `config/safety_semantic.yaml` | Paraphrases the regex misses: "there's a weird sulfur smell by the oven" | AI (embeddings), can only add a stop |
| 3 | Danger seen in a photo | `app/pipelines/image.py` (`look_for_danger`), `safety.check_observation` | A vague or safety question ("What is this?", "Is this okay to use?") gets two focused looks for burn marks, melting, smoke, sparks, exposed wires, water near electrics; every description is scanned for those words | AI look + fixed scan, can only add a stop |
| 4 | Sound that might be an alarm | `app/pipelines/audio.py` (`_possible_alarm`) | An alarm label that isn't confidently first: asks "is anything like a kettle on?" and keeps "if unsure, treat it as an alarm" | Fixed rule on AI labels |
| 5 | Read twice | `app/clarify.py` (`reads_agree`), `image.answer_question`, `homefix.run` | A display read two ways (80 vs 60, E24 vs 624): shows both and asks | Fixed rule on two AI reads |
| 6 | Ask instead of guessing | `app/clarify.py` | Vague question about a display, a code that can't be read, two manuals that fit | Fixed rules |
| 7 | Intent by meaning | `app/intent.py`, `config/intent_examples.yaml` | "Is this a problem?" (escalation link) and "is this vague?" by meaning as well as words | Word rule OR AI, can only add |
| 8 | No verified quote, no answer | `app/text/verify.py` | A manual or lease answer whose quote isn't in the document (fuzzy match < 92) | Fixed |
| 9 | Code in a sandbox | `app/code/sandbox.py` | Generated code runs in a locked-down subprocess with a timeout, never in the app | Fixed |

## Measured

Every set is our own phrases. Thresholds were chosen on a tuning set and reported on a separate held-out set that
was never used for tuning. The practice pack was only used to check, never to tune, and is reported by item ID.

**Danger by meaning (layer 2).** Held-out `tests/data/safety_test.yaml`:

| | Dangerous ones caught | Ordinary ones wrongly stopped |
|---|---|---|
| Regex alone | 12/25 | 0/30 |
| Regex + meaning | **24/25** | **0/30** |

Missed: "the electric baseboard heater has scorch marks". Gallery: only the two real danger examples stop.
Practice pack: 0/100 questions wrongly stopped. Cost: about 150 ms per question once the model is warm; it warms at
API start.

**Danger seen in a photo (layer 3).** 4 real hazard photos (a burnt plug, a burnt wire ferrule, two exposed-wiring
photos; Wikimedia Commons) and 6 safe ones (glowing burner, breaker panel, two thermostats, microwave, cooktop),
each asked "What is this?" and "Is this okay to use?": **8/8 hazard questions stopped, 0/12 safe ones did.** One
cold look alone missed 3 of 4 hazards, which is why it looks twice. Practice pack: one photo was wrongly stopped
in 1 of 12 runs (`p_img_024`), 0 of the last 8. Cost: about 2 to 25 s more for vague or safety questions (the
first look at a new photo is the slow one).

**Read twice (layer 5).** Our clear displays (thermostat 68, washer E21, cooktop clock) answered 4/4 runs. One
practice photo (`p_img_021`) now asks in 3 of 4 runs: its reads give 390, 391, 598, 389 for the same digit, so the
model really can't read it. That costs the item; we keep it.

**Intent by meaning (layer 7).** Held-out `tests/data/intent_test.yaml`:

| | Found | Wrong |
|---|---|---|
| "Is this a problem?" words alone | 4/10 | 0/10 |
| words + meaning | **10/10** | 1/10 ("is the oven set to bake or broil?") |
| "Is this vague?" words alone | 2/6 | 0/6 |
| words + meaning | **6/6** | 0/6 |

## Re-run the numbers

```
uv run pytest -m model tests/test_safety_semantic.py tests/test_intent.py   # held-out sets, real model
uv run pytest tests/test_photo_danger.py tests/test_consistency.py tests/test_sound_hazard.py
uv run python -m eval.run --profile lite --modality all                     # practice pack
```

## Known gaps

- **"Is this okay to use?" can still get "Yes".** When the danger look finds nothing, the model may reassure
  ("Yes, the burner is working"). A photo can't prove something is safe; HomeFix should say what it didn't see
  instead. Not built yet.
- **Video and the audio track of a clip** are not danger-checked.
- **The danger look only runs for vague or safety questions**, to keep plain questions fast. "How many burners are
  on?" about a photo of a scorched outlet won't stop unless the answer itself mentions the damage.
- **Small sets.** The held-out sets are 25 + 30 (danger) and 20 + 12 (intent) phrases. They show the layers work;
  they don't prove a rate.
- **None of this replaces a real smoke or CO alarm.**
