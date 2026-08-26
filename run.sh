#!/bin/bash
# PDM one-command bootstrap (Linux)
# Usage: bash run.sh          — prepares the environment and launches PDM
#        bash run.sh --live   — also runs the live self-test before launching

set -e
cd "$(dirname "$0")"

echo "==> PDM setup"

# 1. Python 3.10+
PY=python3
if ! command -v $PY >/dev/null 2>&1; then
    PY=python
fi
if ! command -v $PY >/dev/null 2>&1; then
    echo "ERROR: Python 3 not found. Install python3 first: sudo apt install python3 python3-venv"
    exit 1
fi
if ! $PY -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "ERROR: Python 3.10+ required (found $($PY --version 2>&1))."
    exit 1
fi

# 2. venv
if [ ! -x ".venv/bin/python" ]; then
    echo "==> Creating virtual environment (.venv)"
    $PY -m venv .venv || { echo "ERROR: venv failed. Try: sudo apt install python3-venv"; exit 1; }
fi
VPY=".venv/bin/python"

# 3. Dependencies
echo "==> Installing dependencies"
"$VPY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
"$VPY" -m pip install --quiet -r requirements.txt

# 4. PySide6 (heavy; only if missing)
"$VPY" - <<'EOF' >/dev/null 2>&1 || "$VPY" -m pip install --quiet PySide6-Essentials
import PySide6
EOF

# 5. ffmpeg + ffprobe (static build via pip package; system ffmpeg also fine)
"$VPY" - <<'EOF' >/dev/null 2>&1 || "$VPY" -m pip install --quiet static-ffmpeg && "$VPY" -c "import static_ffmpeg_paths" >/dev/null 2>&1 || true
from static_ffmpeg_paths import get_ffmpeg_paths  # noqa
EOF

# 6. N_m3u8DL-RE (optional OTT downloader; auto-install for current user)
BIN_DIR="$HOME/.local/bin"
NRE="$BIN_DIR/N_m3u8DL-RE"
if [ ! -x "$NRE" ] && ! command -v N_m3u8DL-RE >/dev/null 2>&1; then
    echo "==> Fetching N_m3u8DL-RE (OTT/HLS engine)"
    URL=$(curl -sL https://api.github.com/repos/nilaoda/N_m3u8DL-RE/releases/latest \
        | grep -o 'https://[^"]*linux-x64[^"]*\.tar\.gz' | head -1)
    if [ -n "$URL" ]; then
        mkdir -p "$BIN_DIR" /tmp/pdm_nre
        curl -sL -o /tmp/pdm_nre/nre.tar.gz "$URL" \
            && tar -xzf /tmp/pdm_nre/nre.tar.gz -C /tmp/pdm_nre \
            && find /tmp/pdm_nre -name 'N_m3u8DL-RE*' -type f -exec chmod +x {} \; -exec mv {} "$NRE" \; \
            && echo "    installed -> $NRE" \
            || echo "    WARN: could not fetch N_m3u8DL-RE (PDM will use its built-in HLS engine)"
        rm -rf /tmp/pdm_nre
    else
        echo "    WARN: release lookup failed (PDM will use its built-in HLS engine)"
    fi
else
    echo "==> N_m3u8DL-RE already present"
fi

# 7. JS runtime hint (optional, enables full YouTube extraction)
command -v node >/dev/null 2>&1 || command -v deno >/dev/null 2>&1 || {
    echo "    NOTE: no node/deno found - YouTube still works in most cases."
    echo "          For maximum compatibility: sudo apt install nodejs"
}

# 8. Self-test (offline always; --live passes through)
export PATH="$BIN_DIR:$PATH"
if [ "${1:-}" = "--live" ] || [ "${1:-}" = "--test" ]; then
    echo "==> Running self-test"
    QT_QPA_PLATFORM=offscreen "$VPY" scripts/selftest.py ${1:+--live} && echo "==> Self-test PASSED"
fi

# 9. Launch (strip test flags from app args)
echo "==> Launching PDM"
ARGS=""
for a in "$@"; do
    [ "$a" = "--live" ] || [ "$a" = "--test" ] || ARGS="$ARGS $a"
done
exec "$VPY" pdm.py $ARGS
