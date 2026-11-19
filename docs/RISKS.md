# Risks and pre-built fallbacks

| # | Risk | Likelihood | Impact | Fallback (built before it happens) |
|---|---|---|---|---|
| 1 | **Ollama runs in Docker on the M4** (found during Phase 0: Docker owns :11434). Docker on macOS has no Metal GPU, so CPU-only inference would be far slower | Found | High | Use native Ollama.app; stop the Docker container; `setup_mac.sh` and `go_no_go.py` warn if Docker owns the port |
| 2 | Brain model too slow / OOM on 16 GB with coder resident | Med | High | Drop to `qwen3-vl:4b` or swap the coder in on demand; memory manager supports both |
| 3 | 8 GB M2 runs out of memory | Med | Med | One LLM at a time (`OLLAMA_MAX_LOADED_MODELS=1`), small.en, 2B brain; reduce `num_ctx` to 4096 |
| 4 | Model fails or crashes mid-demo | Low | High | Graceful degradation: error event + message, the app keeps serving other modalities; switch to the M2 or the backup video |
| 5 | Something touches the network at runtime | Low | **DQ** | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`; `offline_check.sh` run with Wi-Fi off on both Macs |
| 6 | Hard-rule violation (pack data committed, answers.json read) | Low | **DQ** | `.gitignore` first commit; `tests/test_hard_rules.py` checks both; run before every merge |
| 7 | Sound vocabulary questioned as "ESC-50 lookup" | Med | **DQ** | Vocabulary derived from the AudioSet ontology by a script; confirm with organizers (DECISIONS.md D3) |
| 8 | Text verifier rejects correct answers (low recall) | Med | Med | Threshold tuned on the 20 practice items; second chance: re-prompt once asking for a shorter verbatim quote |
| 9 | Generated code hangs or does something harmful | Low | Med | Subprocess, 10 s timeout, temp dir, no network env, never in the main process |
| 10 | Phone demo: camera/mic need HTTPS; venue is Wi-Fi off | High | Low (bonus) | `scripts/https_dev.sh` (mkcert) for LAN; if organizers don't allow a no-internet hotspot, play the pre-recorded phone clip |
| 11 | Live mic latency too high on the M2 | Med | Low | Mic is P2; file upload of a recording is always available |
| 12 | Running out of time | **High** | High | Priority order in PLAN.md; freeze at 14:00 Thu; tag by 22:00 |
