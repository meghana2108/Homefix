#!/usr/bin/env bash
# Serve the HomeFix UI over https on this laptop's local network address, so a phone on the same
# network can use it (camera, mic and "Add to Home Screen" need https).
#
#   bash scripts/https_dev.sh          # production build + preview (service worker on)
#   bash scripts/https_dev.sh --dev    # dev server with hot reload (no service worker)
#
# The API keeps listening on 127.0.0.1 only. The phone calls /api on the UI's address and Vite forwards
# it. Start the API first, in another terminal:
#   uv run uvicorn app.api.main:app --port 8000
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v mkcert >/dev/null; then
  echo "mkcert is not installed. Run: brew install mkcert   (needs the network once)" >&2
  exit 1
fi

IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
if [ -z "$IP" ]; then
  echo "No local network address found (is Wi-Fi or Ethernet connected?)." >&2
  echo "Without a network, record the phone clip for the backup video instead (RISKS.md #10)." >&2
  exit 1
fi

CERT_DIR=frontend/.cert
mkdir -p "$CERT_DIR"
CERT="$CERT_DIR/$IP.pem"
KEY="$CERT_DIR/$IP-key.pem"
if [ ! -f "$CERT" ]; then
  # -install adds mkcert's local CA to this Mac's keychain (asks for your password once).
  mkcert -install
  mkcert -cert-file "$CERT" -key-file "$KEY" "$IP" localhost 127.0.0.1 >/dev/null
fi

if ! curl -s -m 2 http://127.0.0.1:8000/api/health >/dev/null; then
  echo "Note: the API isn't answering on 127.0.0.1:8000 yet. Start it: uv run uvicorn app.api.main:app --port 8000"
fi

cat <<EOF

  Open on the phone:  https://$IP:5173

  The phone must trust this Mac's certificate authority once:
    1. AirDrop or email the file  $(mkcert -CAROOT)/rootCA.pem  to the phone.
    2. iPhone: Settings > Profile Downloaded > Install, then
       Settings > General > About > Certificate Trust Settings > turn on "mkcert".
       Android: Settings > Security > Encryption & credentials > Install a certificate > CA certificate.
  Without that the phone shows a warning; you can still continue, but the mic and install may not work.

EOF

export HTTPS_CERT="$PWD/$CERT" HTTPS_KEY="$PWD/$KEY" VITE_API_URL=""
cd frontend
if [ "${1:-}" = "--dev" ]; then
  exec npx vite
fi
npm run build
exec npx vite preview
