# HomeFix

A fully local multimodal assistant (image, audio, text, code, video) for students renting their
first apartment. IEEE AI Hackathon 2026. Runs on Apple Silicon with native Ollama, Wi-Fi off.
Two profiles: `full` (M4, 16 GB) and `lite` (M2, 8 GB). See [docs/PLAN.md](docs/PLAN.md) for
deadlines and [docs/TEAM.md](docs/TEAM.md) for who owns what.

## Commands
| What | Command |
|---|---|
| Install deps | `uv sync` (Python 3.11, pinned by `uv.lock`) |
| Unit + hard-rule tests | `uv run pytest` (skips tests marked `model`) |
| Tests that need a real model | `uv run pytest -m model` |
| Lint | `uv run ruff check .` |
| Machine smoke test | `uv run python scripts/go_no_go.py [--profile lite]` |
| Offline check | `bash scripts/offline_check.sh full` (run with Wi-Fi off) |
| Eval (Phase 3, not built yet) | `uv run python -m eval.run --profile full --modality all` |

## Hard rules (breaking one can disqualify us)
- Practice pack data (`items.json`, `answers.json`, its media) never enters the repo, not even
  quoted in a doc, a test fixture or a commit message. Refer to pack items by ID only.
- Only `eval/grade.py` may read `answers.json`. `tests/test_hard_rules.py` checks this.
- No copyrighted manuals in git (`data/manuals/` is gitignored).
- The sound vocabulary is the AudioSet-derived list, never the ESC-50 class list.
- No network calls at runtime.

## Docs conventions

### Specs: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- First line under the title: `Date: YYYY-MM-DD · Status: draft | approved design, ready to plan`
- **Intent**: the problem as the user sees it today, and what should change.
- **Goals**: concrete bullets. Name exact endpoints (`POST /api/chat`), SSE event types,
  pipeline modules (`app/pipelines/<modality>`), profiles (`full` / `lite`) and behaviors.
- **Non-goals**: what this deliberately doesn't touch.
- **Anti-goals**: things that would be a failure even if the feature works. For HomeFix these
  always include: a network call at runtime, a text answer shown without a verified quote, a
  repair step given after the safety filter matched, and generated code run in the main process.
- **Constraints**: technical and policy limits. Include memory per profile (target ≤ 11 GB of
  models on `full`, one LLM at a time on `lite`), latency targets and any hard rule it touches.
- Then the design: data shapes, flows and UI states (loading, empty, error, fallback). For a
  backend feature, list every SSE event it emits and its fields.

### Plans: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- Header: the superpowers "For agentic workers" line, then **Goal**, **Architecture**
  (2–3 sentences), **Tech Stack**, **Spec** (path).
- **Global Constraints**: every exact name, enum value, limit, default, file location and rule
  that more than one task depends on, such as SSE event names, `refusal` reasons, profile YAML
  keys and thresholds (`quote_fuzz_threshold: 92`). Also note anything uncommitted in the
  working tree that must not be staged.
- **Review Focus**: numbered edge cases, each naming the task that tests it. Cover at least:
  empty input, unsupported file type, malformed model output (no code block, invalid JSON),
  a model that is not loaded or times out, `lite` memory pressure, and partial failure (one
  modality fails, the others keep serving).
- **Tasks**, each with:
  - **Files**: Create / Modify / Test, with exact paths.
  - **Interfaces**: Consumes / Produces, with exact signatures, types and return shapes.
  - Checkbox steps:
    `- [ ] Step 1: Write the failing tests` (name each test and what it asserts) →
    `Step 2: Run uv run pytest tests/test_<x>.py -v → FAIL` →
    `Step 3: Implement` (specific) →
    `Step 4: Run uv run pytest tests/test_<x>.py -v → PASS` →
    `Step 5: Commit <conventional message>` (say exactly what to stage).
  - A test that needs a real model gets `@pytest.mark.model` and is run with `-m model`.
- Keep tasks small enough to review on their own. Order them so each builds on committed work.

### Bug and quality logs: `docs/<AREA>_BUGS.md`
- How the test set was built. Answers are worked out independently of our code.
- **Baseline (date): X/Y**, the scoring rule (the metric from [docs/EVAL.md](docs/EVAL.md)) and
  the exact command to re-run it, e.g.
  `uv run python -m eval.run --profile full --modality text`.
- Rule: every fix starts with a failing test, and parallel code paths get the same fix (for
  example both profiles, or both the API and the eval path).
- Tables are grouped by severity, worst first (confident wrong answers come first):
  `# | Input | We say | Truth | Cause (file/function)`.
- For practice pack items, the `Input` column holds the item ID only, and `Truth` is a short
  paraphrase of our own, never the reference answer (hard rule 1).

### Writing style (all docs and commits)
- Plain words, short sentences, no marketing language.
- Concrete over vague: real numbers, file paths, commands, expected output.
- Say what is NOT done, cut or known to be broken.
- Conventional commits (`feat:`, `fix:`, `docs:`, `feat(scope):`, scopes like `image`,
  `audio`, `text`, `code`, `video`, `api`, `ui`, `eval`). Describe what the user can now see or
  do, e.g. "feat(text): answers show the manual page and quote, or say it isn't there", not
  "update verifier".
- Don't add AI attribution lines to commits.
- Run `uv run pytest` before every commit. Merge to `main` only when it is green.
