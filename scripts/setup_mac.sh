#!/usr/bin/env bash
# One-time machine setup for HomeFix on Apple Silicon. Idempotent: safe to re-run.
#   bash scripts/setup_mac.sh
# Installs (only if missing): ffmpeg (~100 MB with deps), Ollama app/CLI (~500 MB), gh, uv,
# Python 3.11 (via uv, ~60 MB), Node 20 (via brew node@20, ~70 MB), then Python + frontend deps.
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }
need() { command -v "$1" >/dev/null 2>&1; }

[[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]] || { echo "Apple Silicon macOS required (mlx-whisper)."; exit 1; }

say "Homebrew"
need brew || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
brew --version | head -1

say "ffmpeg"
need ffmpeg || brew install ffmpeg
ffmpeg -version | head -1

say "Ollama (must be NATIVE for Metal GPU - Docker on macOS is CPU-only)"
if lsof -nP -iTCP:11434 -sTCP:LISTEN 2>/dev/null | grep -qi docker; then
  echo "WARNING: port 11434 is owned by a Docker container. Docker Ollama on macOS has no GPU access."
  echo "Stop it ('docker ps' then 'docker stop <id>') before starting native Ollama."
fi
if ! need ollama; then brew install --cask ollama || brew install ollama; fi
ollama --version || true

say "GitHub CLI"
need gh || brew install gh

say "uv + Python 3.11"
need uv || brew install uv
uv python install 3.11

say "Node 20"
if ! need node || [[ "$(node -v | cut -d. -f1)" != "v20" ]]; then
  brew list node@20 >/dev/null 2>&1 || brew install node@20
  echo "Node 20 is at $(brew --prefix node@20)/bin. If 'node -v' is not v20, run:"
  echo "  export PATH=\"$(brew --prefix node@20)/bin:\$PATH\""
fi

say "Python deps (uv sync, ~1.5 GB incl. torch)"
uv sync

if [[ -f frontend/package.json ]]; then
  say "Frontend deps"
  (cd frontend && npm install)
fi

[[ -f .env ]] || { cp .env.example .env; echo "Created .env - set PRACTICE_PACK_DIR and PROFILE."; }

say "Done. Next: start Ollama ('ollama serve' or open the app), then: bash scripts/pull_models.sh <full|lite>"
