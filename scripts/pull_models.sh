#!/usr/bin/env bash
# Download every model a profile needs, so runtime can be 100% offline.
#   bash scripts/pull_models.sh full     # M4 16 GB  (~23 GB incl. bake-off candidates)
#   bash scripts/pull_models.sh lite     # M2 8 GB   (~10 GB incl. bake-off candidates)
#   bash scripts/pull_models.sh full --final   # only the models named in the profile
# Tags verified against registry.ollama.ai and huggingface.co on 2026-11-18.
set -euo pipefail
cd "$(dirname "$0")/.."
PROFILE="${1:-full}"; MODE="${2:-}"

# Ollama sizes (disk): gemma4:e4b 6.6G, qwen3-vl:4b 3.3G, qwen3-vl:8b 6.2G,
#                      gemma4:e2b 4.6G, qwen3-vl:2b 1.9G, qwen2.5-coder:3b 1.9G, qwen2.5-coder:7b 4.7G
if [[ "$PROFILE" == "full" ]]; then
  OLLAMA_MODELS_LIST=(qwen3-vl:8b qwen3-vl:4b gemma4:e4b qwen2.5-coder:3b qwen2.5-coder:7b)
  HF_MODELS=(mlx-community/whisper-large-v3-turbo mlx-community/whisper-small.en-mlx laion/clap-htsat-unfused BAAI/bge-small-en-v1.5)
elif [[ "$PROFILE" == "lite" ]]; then
  OLLAMA_MODELS_LIST=(qwen3-vl:2b gemma4:e2b qwen2.5-coder:3b)
  HF_MODELS=(mlx-community/whisper-small.en-mlx laion/clap-htsat-unfused BAAI/bge-small-en-v1.5)
else
  echo "usage: $0 <full|lite> [--final]"; exit 1
fi

if [[ "$MODE" == "--final" ]]; then
  # Only what the profile yaml names (after the bake-off is decided).
  # (macOS ships bash 3.2: no mapfile)
  OLLAMA_MODELS_LIST=($(uv run python -c "import yaml;m=yaml.safe_load(open('config/profiles/$PROFILE.yaml'))['models'];print(*sorted({m['brain'],m['coder']}))"))
fi

curl -s --max-time 3 http://127.0.0.1:11434/api/version >/dev/null || { echo "Ollama is not running. Start it (open Ollama.app or 'ollama serve')."; exit 1; }

echo "== Ollama models: ${OLLAMA_MODELS_LIST[*]}"
for m in "${OLLAMA_MODELS_LIST[@]}"; do ollama pull "$m"; done

# HF: whisper turbo 1.6G, small.en 0.5G, CLAP 0.6G, bge-small 0.4G
echo "== Hugging Face models: ${HF_MODELS[*]}"
for m in "${HF_MODELS[@]}"; do
  HF_HUB_OFFLINE=0 uv run python -c "from huggingface_hub import snapshot_download as s; print(s('$m'))"
done

echo "== Done. Installed Ollama models:"; ollama list
