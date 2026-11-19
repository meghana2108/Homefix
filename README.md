# HomeFix 🔧

**A private, fully local multimodal assistant for students renting their first apartment, built for the moment an appliance breaks.**
Play the beep, snap the error code, ask your manual, upload a video of the drum not spinning. HomeFix answers on your own laptop with open-weight models, **with Wi-Fi off**.

> IEEE AI Hackathon 2026, Multimodal LLM Challenge ("Build AI we own"). Team: Meghana R, Akshayaa Mahesh.

![demo](docs/img/demo.gif) <!-- placeholder: add after Phase 4 -->

## What it does
| Input | Capability |
|---|---|
| 🖼️ Image | Describe a photo, count objects, read text (error codes, labels) |
| 🔊 Audio | Transcribe speech and answer questions; identify sounds (beeps, grinding, alarms) |
| 📄 Text | Answer from a document with a verified word-for-word quote and page, or say it isn't there |
| 💻 Code | Write a Python function, run its examples in a sandbox, retry once on failure |
| 🎬 Video | Describe a short clip: count, follow motion, read signs |
| ⚠️ Safety | Gas, sparks, smoke, exposed wires, water near outlets → fixed safety message, before any model runs |

## Hardware
| Profile | Machine | Brain | Notes |
|---|---|---|---|
| `full` | MacBook Pro M4, 16 GB | qwen3-vl:8b (TBD by bake-off) | Demo inference server |
| `lite` | MacBook Air M2, 8 GB | qwen3-vl:2b | Proves it runs on 8 GB; one LLM resident at a time |

Requires Apple Silicon (mlx-whisper) and **native** Ollama (not Docker: no GPU on macOS).

## Quickstart
```bash
bash scripts/setup_mac.sh            # ffmpeg, Ollama, uv, Python 3.11, Node 20, deps
cp .env.example .env                 # set PRACTICE_PACK_DIR and PROFILE
bash scripts/pull_models.sh full     # or: lite   (~23 GB / ~10 GB incl. bake-off candidates)
uv run python scripts/go_no_go.py    # GO / NO-GO table
uv run pytest                        # unit + hard-rule tests
```
Run the app: _Phase 4_. Run the eval: `uv run python -m eval.run --profile full --modality all` (_Phase 3_).

## Results
_Filled in after Phase 3. See [docs/EVAL.md](docs/EVAL.md) and `results/summary_*.md`._

## Docs
[Plan](docs/PLAN.md) · [Team](docs/TEAM.md) · [Architecture](docs/ARCHITECTURE.md) · [Models](docs/MODELS.md) · [Eval](docs/EVAL.md) · [Demo](docs/DEMO.md) · [Risks](docs/RISKS.md) · [Decisions](docs/DECISIONS.md) · [Assets](docs/ASSETS.md)

## Limits
See [ARCHITECTURE.md § Limits](docs/ARCHITECTURE.md#limits-we-name-openly).

## License
MIT for our code. Models and datasets keep their own licenses ([docs/ASSETS.md](docs/ASSETS.md)).
