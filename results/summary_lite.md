# HomeFix eval summary: lite

Run `20261119-1404-lite-all` · 100 items · written 2026-11-19 14:48. Numbers only: no questions or answers (hard rule 1).
Brain `qwen3-vl:2b-instruct`, coder `qwen2.5-coder:3b`; overrides: none.

## Accuracy

### image

| metric | hits/total | score |
|---|---|---|
| count_exact | 14/15 | 0.93 |
| fuzzy | 9/10 | 92.21 |

### audio

| metric | hits/total | score |
|---|---|---|
| fuzzy | 6/10 | 80.12 |
| top1 | 8/10 | 69.85 |
| top3 | 9/10 | – |

### text

| metric | hits/total | score |
|---|---|---|
| answer_match | 14/15 | 94.38 |
| refusal | 2/5 | 0.40 |

Refusal precision 2/2 (1.00), recall 2/5 (0.40) (positive = refused as not in the document).

### code

| metric | hits/total | score |
|---|---|---|
| pass@1 | 17/20 | 0.85 |

### video

| metric | hits/total | score |
|---|---|---|
| count_exact | 1/4 | 0.25 |
| direction | 2/2 | 1.00 |
| fuzzy | 2/9 | 51.89 |

## Latency and memory

| modality | items | p50 | p95 | Target p50 |
|---|---|---|---|---|
| image | 25 | 14.9 s | 19.7 s | ≤ 15 s |
| audio | 20 | 22.7 s | 33.7 s | sound ≤ 4 s, speech ≤ 15 s |
| text | 20 | 5.1 s | 8.5 s | ≤ 20 s |
| code | 20 | 24.3 s | 58.6 s | ≤ 35 s (incl. swap) |
| video | 15 | 22.5 s | 50.5 s | ≤ 40 s |

Latency is wall time from request to final, and includes loading each model the first time it is used in the run.
Peak memory: 3.0 GB (Ollama's loaded models + the eval process).
Refusals and errors: not_in_document 2.

Re-run: `uv run python -m eval.run --profile lite --modality all` then `uv run python -m eval.report --run <run_id>`.
