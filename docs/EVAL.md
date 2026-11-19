# Evaluation

`python -m eval.run --profile <full|lite> --modality <image|audio|text|code|video|all>` calls the **same pipeline functions the API uses**, writes `results/raw/<run_id>.jsonl` (gitignored), and `python -m eval.report` writes `results/summary_<profile>.md` (committable: numbers only, no pack content).

## Running it
```bash
# PRACTICE_PACK_DIR=/abs/path/to/practice_pack in .env (outside the repo), Ollama running
uv run python -m eval.run --profile lite --modality all            # every item
uv run python -m eval.run --profile lite --modality image --limit 2  # quick check: 2 items per modality
uv run python -m eval.run --profile full --modality text --set text.quote_fuzz_threshold=85   # bake-off
uv run python -m eval.report --run <run_id>                         # -> results/summary_<profile>.md
```
Flow: `eval/pack.py` loads `items.json` → each item goes through `app.orchestrate.handle()` (same
safety filter, router and pipelines as the API) → one `RunRecord` per item is appended to
`results/raw/<run_id>.jsonl` as soon as it finishes → if the pack has reference answers,
`eval/grade.py` grades the run (`<run_id>_graded.jsonl`, plus `<run_id>_review.csv` for a human
pass) → `eval/report.py` writes the summary.

- `run_id` = `<YYYYmmdd-HHMM>-<profile>-<modality>`; a second run in the same minute gets `-2`.
- `--limit N` is per modality. `--set key.path=value` overrides any profile key (value parsed as
  YAML); an unknown key stops with `Unknown setting: <key>`. `--no-grade` skips grading.
- `results/raw/` is gitignored: it holds our answers and, in the review CSV, the reference answers.
  Only `results/summary_<profile>.md` is committed (counts and scores, no questions or answers).
- Latency includes loading each model the first time it is used in a run. Peak memory is sampled
  every 0.5 s while each item runs (Ollama's loaded models + the eval process).
- Not done: the pack's real key names are still guesses (constants at the top of `eval/pack.py`,
  `REF_KEYS` in `eval/types.py`) until the pack is downloaded. Image, text and code graders are
  stubs until M11, so their rows show `todo`.

**Only `eval/grade.py` reads `answers.json`** (HARD RULE 4, enforced by `tests/test_hard_rules.py`).

## Metrics
| Modality | Metric | How it's computed |
|---|---|---|
| Image, count questions | Exact number match | First integer (digits or number words → int) in our answer == reference integer |
| Image, other | Fuzzy match + manual review | `rapidfuzz.fuzz.token_set_ratio(norm(ours), norm(ref)) ≥ 80` counts as a hit; every item is also written to `results/raw/<run_id>_review.csv` for a human pass |
| Video | Same as image | Count → exact number; motion → direction keyword match (left/right/up/down/toward/away/clockwise); read → fuzzy |
| Speech | WER + answer accuracy | `jiwer.wer(norm(ref_transcript), norm(ours))` with lowercasing + punctuation strip; answer judged like image "other" |
| Sounds | Top-1 / top-3 accuracy | Our top-k labels fuzzy-matched to the reference label (`token_set_ratio ≥ 80`, plus a manual synonym review in the CSV, e.g. "bow-wow" ≈ "dog") |
| Text, answerable | Answer accuracy | Fuzzy / SQuAD-style normalized contains-match against the reference |
| Text, unanswerable | Refusal precision & recall | Positive class = "refused". Precision = refused∧unanswerable / refused; recall = refused∧unanswerable / unanswerable |
| Code | pass@1 | Run `code/tests/<id>_test.py` against our single generated function in a subprocess (import style matched to the test file) |
| All | Latency p50 / p95, peak memory, swap time | Wall-clock per item from request to `final` event; peak = max(Ollama `ps` size + Python RSS); swap time from `memory.py` |

`norm()` = lowercase, strip punctuation and articles, collapse whitespace.

## Reporting
- `results/summary_full.md` and `results/summary_lite.md`: one table per modality, plus the latency targets table with actuals.
- Numbers go into the README and the "results" slide.
