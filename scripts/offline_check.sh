#!/usr/bin/env bash
# Prove the app works with Wi-Fi OFF. Turn Wi-Fi off first, then:
#   bash scripts/offline_check.sh [full|lite]
set -uo pipefail
cd "$(dirname "$0")/.."
PROFILE="${1:-${PROFILE:-full}}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PROFILE
fail=0
ok()  { printf "  \033[32mPASS\033[0m %s\n" "$*"; }
bad() { printf "  \033[31mFAIL\033[0m %s\n" "$*"; fail=1; }

echo "1) Network must be unreachable"
if ping -c1 -t2 8.8.8.8 >/dev/null 2>&1; then bad "8.8.8.8 is reachable - turn Wi-Fi off"; else ok "no internet"; fi

echo "2) Ollama models present locally"
for m in $(uv run python -c "import yaml;m=yaml.safe_load(open('config/profiles/$PROFILE.yaml'))['models'];print(m['brain'],m['coder'])"); do
  ollama list | awk '{print $1}' | grep -qx "$m" && ok "$m" || bad "$m missing"
done

echo "3) HF models in local cache"
for m in $(uv run python -c "import yaml;m=yaml.safe_load(open('config/profiles/$PROFILE.yaml'))['models'];print(m['whisper_file'],m['whisper_live'],m['clap'],m['embeddings'])" | tr ' ' '\n' | sort -u); do
  uv run python -c "from huggingface_hub import snapshot_download as s; s('$m', local_files_only=True)" >/dev/null 2>&1 && ok "$m" || bad "$m not cached"
done

echo "4) Five-modality smoke test (go/no-go)"
uv run python scripts/go_no_go.py --profile "$PROFILE" && ok "go/no-go" || bad "go/no-go"

# Phase 4+: also hit the running API with one request per modality.
if curl -s --max-time 2 http://127.0.0.1:8000/api/health >/dev/null; then
  echo "5) API health"; curl -s http://127.0.0.1:8000/api/health; echo
fi

[[ $fail == 0 ]] && echo "OFFLINE CHECK PASSED" || { echo "OFFLINE CHECK FAILED"; exit 1; }
