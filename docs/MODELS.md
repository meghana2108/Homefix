# Models

All tags verified on 2026-11-18 against `registry.ollama.ai` (manifest HTTP 200) and `huggingface.co/api/models` (HTTP 200). Sizes are download sizes.

## Candidates
| Role | Candidate | Size | Profile | Runtime | Why consider |
|---|---|---|---|---|---|
| Vision + text brain | `qwen3-vl:8b-instruct` | 6.2 GB | full | Ollama | Strong OCR and counting for its size; native multi-image. Instruct tag: the plain tag thinks by default (D14) |
| | `gemma4:e4b` | 9.5 GB on disk | full | Ollama | Multimodal Gemma, efficient "effective 4B". ⚠️ 9.5 GB next to the coder and Whisper is over the 11 GB target |
| | `qwen3-vl:4b` | 3.3 GB | full / lite stretch | Ollama | Leaves headroom for 7B coder on full |
| | `qwen3-vl:2b-instruct` | 1.9 GB | lite | Ollama | Fits 8 GB next to Whisper + CLAP. Instruct tag: the plain tag ignores think=False with images (D11) |
| | `gemma4:e2b` | 7.5 GB on disk | lite | Ollama | ⚠️ 7.5 GB on disk; does not fit 8 GB with the rest |
| Code | `qwen2.5-coder:3b` | 1.9 GB | both | Ollama | Small, good HumanEval for size, can stay resident |
| | `qwen2.5-coder:7b` | 4.7 GB | full (swap) | Ollama | Higher pass@1; costs a swap |
| | *the brain itself* | — | both | Ollama | Zero swap; check its pass@1 |
| ASR (files) | `mlx-community/whisper-large-v3-turbo` | 1.6 GB | full | mlx-whisper | Near large-v3 accuracy, much faster |
| ASR (live + lite) | `mlx-community/whisper-small.en-mlx` | 0.5 GB | both | mlx-whisper | Fast enough for 3 s chunks. *(`mlx-community/whisper-small.en` does not exist; `-mlx` suffix is the real repo.)* |
| Sound ID | `laion/clap-htsat-unfused` | 0.6 GB | both | transformers `zero-shot-audio-classification` | Zero-shot over our own vocabulary, no training |
| Embeddings | `BAAI/bge-small-en-v1.5` | 0.4 GB | both | sentence-transformers | Small, strong retrieval; manuals only |

## Bake-off method
1. Run `python -m eval.run --profile <p> --modality <m> --model <tag>` for each candidate on the practice pack items of that modality.
2. Record accuracy (metric per [EVAL.md](EVAL.md)), p50 / p95 latency, peak memory.
3. Pick the best accuracy that meets the latency target in the README; ties go to the smaller model.
4. Practice-pack items may be used as few-shot examples (allowed), but measure on items **not** used as shots.

## Results (measured 2026-11-19 and 2026-11-20)
These are the chosen models only. We did **not** run the other candidates on the whole practice pack: the
bake-off rows below are what we measured or ruled out, and why.

| Modality | Model | Profile | Accuracy | p50 s | p95 s | Notes |
|---|---|---|---|---|---|---|
| Image (count / read) | qwen3-vl:8b-instruct | full | 14/15 · 8/10 | 9.2 | 14.5 | |
| | qwen3-vl:2b-instruct | lite | 14/15 · 9/10 | 14.9 | 19.7 | |
| Video (count / direction / qa) | qwen3-vl:8b-instruct, 16 frames | full | 2/4 · 2/2 · 7/9 | 38.8 | 54.8 | over the 25 s target |
| | qwen3-vl:2b-instruct, 8 frames | lite | 1/4 · 2/2 · 2/9 | 22.5 | 50.5 | |
| Speech (transcript fuzzy) | whisper-large-v3-turbo | full | 8/10 | 2.9* | 6.1* | *audio p50 covers speech and sounds |
| | whisper-small.en | lite | 6/10 | 22.7* | 33.7* | over target; cause not measured |
| Sounds (top-1 / top-3) | CLAP htsat-unfused | both | 8/10 · 9/10 | (above) | (above) | same model on both |
| Text (answer / refusal recall) | qwen3-vl:8b-instruct + verifier | full | 15/15 · 3/5 | 3.6 | 10.2 | refusal precision 1.00 |
| | qwen3-vl:2b-instruct + verifier | lite | 14/15 · 2/5 | 5.1 | 8.5 | refusal precision 1.00 |
| Code (pass@1) | qwen2.5-coder:7b | full | 20/20 | 12.7 | 27.4 | swapped in, brain unloaded |
| | qwen2.5-coder:3b | lite | 17/20 | 24.3 | 58.6 | |

Peak memory: 7.2 GB on `full`, 3.0 GB on `lite` (Ollama's loaded models plus the eval process).

### What we compared, and what we didn't
| Choice | Compared with | Result | Source |
|---|---|---|---|
| `qwen3-vl:8b-instruct` over `qwen3-vl:8b` | the plain tag | `ollama show` lists "thinking", on by default, for the plain tag; the instruct tag has none, and `go_no_go.py --profile full` prints GO with it | DECISIONS D14 |
| `qwen3-vl:2b-instruct` over `qwen3-vl:2b` | the plain tag | The plain tag ignores `think=False` with an image: one video question made 4,264 hidden tokens and took 247 s. With the instruct tag, JSON answers went from 63 s to 15 s on the M2 | DECISIONS D11 |
| `qwen2.5-coder:7b` on `full` | `qwen2.5-coder:3b` | On our CSV demo (G6) the 3b passed about half the time, the 7b 3 of 3 | `config/profiles/full.yaml` |
| No `gemma4:e4b` / `gemma4:e2b` | — | Not benchmarked: 9.5 GB and 7.5 GB on disk break the 11 GB (`full`) and 8 GB (`lite`) budgets next to Whisper and CLAP | sizes above |
| No `qwen3-vl:4b` | — | Not benchmarked on the pack | — |

The text verifier threshold stays at 92 (`partial_ratio`, quotes of 8+ words). We did not sweep other values.

## Final choices (one line each)
- **Brain (full):** `qwen3-vl:8b-instruct`. The largest qwen3-vl that fits under 11 GB with Whisper and CLAP, without the thinking delay (D14); 87/100 on the pack. Other brains not benchmarked.
- **Brain (lite):** `qwen3-vl:2b-instruct`. Fits 8 GB next to Whisper small and CLAP; 75/100 overall on the pack.
- **Coder:** `qwen2.5-coder:7b` on `full`, `qwen2.5-coder:3b` on `lite`, each swapped in with the brain unloaded.
- **ASR:** `whisper-large-v3-turbo` for files on `full`, `whisper-small.en` for live mic and everything on `lite`.
- **Sound ID:** CLAP htsat-unfused, zero-shot over AudioSet-derived vocabulary + appliance labels.
- **Embeddings:** bge-small-en-v1.5, only for manuals longer than the full-doc limit.
