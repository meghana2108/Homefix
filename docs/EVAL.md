# Evaluation

`python -m eval.run --profile <full|lite> --modality <image|audio|text|code|video|all>` calls the **same pipeline functions the API uses**, writes `results/raw/<run_id>.jsonl` (gitignored), and `python -m eval.report` writes `results/summary_<profile>.md` (committable: numbers only, no pack content).

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
