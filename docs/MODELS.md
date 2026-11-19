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

## Results (fill in during Phase 3)
| Modality | Model | Profile | Accuracy | p50 s | p95 s | Peak mem GB | Notes |
|---|---|---|---|---|---|---|---|
| Image (count/read/describe) | | | | | | | |
| Video | | | | | | | |
| Speech (WER / answer acc) | | | | | | | |
| Sounds (top-1 / top-3) | | | | | | | |
| Text (ans acc / refusal P / R) | | | | | | | |
| Code (pass@1) | | | | | | | |

### Text verifier threshold
| `partial_ratio` threshold | Answer acc | Refusal precision | Refusal recall |
|---|---|---|---|
| 85 | | | |
| 92 (default) | | | |
| 96 | | | |

## Final choices (one line each)
- **Brain (full):** _TBD after bake-off_
- **Brain (lite):** _TBD_
- **Coder:** _TBD_
- **ASR:** _TBD_
- **Sound ID:** CLAP htsat-unfused, zero-shot over AudioSet-derived vocabulary + appliance labels.
- **Embeddings:** bge-small-en-v1.5, only for manuals longer than the full-doc limit.
