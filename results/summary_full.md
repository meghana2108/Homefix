# HomeFix eval summary: full

Run `20261120-1009-full-all` · 100 items · written 2026-11-20 10:30. Numbers only: no questions or answers (hard rule 1).
Brain `qwen3-vl:8b-instruct`, coder `qwen2.5-coder:7b`; overrides: none.

## Accuracy

### image

| metric | hits/total | score |
|---|---|---|
| count_exact | 14/15 | 0.93 |
| fuzzy | 8/10 | 90.71 |

### audio

| metric | hits/total | score |
|---|---|---|
| fuzzy | 8/10 | 91.70 |
| top1 | 8/10 | 69.85 |
| top3 | 9/10 | – |

### text

| metric | hits/total | score |
|---|---|---|
| answer_match | 15/15 | 100.00 |
| refusal | 3/5 | 0.60 |

Refusal precision 3/3 (1.00), recall 3/5 (0.60) (positive = refused as not in the document).

### code

| metric | hits/total | score |
|---|---|---|
| pass@1 | 20/20 | 1.00 |

### video

| metric | hits/total | score |
|---|---|---|
| count_exact | 2/4 | 0.50 |
| direction | 2/2 | 1.00 |
| fuzzy | 7/9 | 86.88 |

## Latency and memory

| modality | items | p50 | p95 | Target p50 |
|---|---|---|---|---|
| image | 25 | 9.2 s | 14.5 s | ≤ 8 s |
| audio | 20 | 2.9 s | 6.1 s | sound ≤ 3 s, speech ≤ 8 s |
| text | 20 | 3.6 s | 10.2 s | ≤ 12 s |
| code | 20 | 12.7 s | 27.4 s | ≤ 20 s |
| video | 15 | 38.8 s | 54.8 s | ≤ 25 s |

Latency is wall time from request to final, and includes loading each model the first time it is used in the run.
Peak memory: 7.2 GB (Ollama's loaded models + the eval process).
Refusals and errors: not_in_document 3.

Re-run: `uv run python -m eval.run --profile full --modality all` then `uv run python -m eval.report --run <run_id>`.
