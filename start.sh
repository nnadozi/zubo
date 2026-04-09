#!/bin/bash

set -eu

echo "[start] Launching Zubo power orchestrator..."

# Always run from this script's directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtualenv if present, but keep startup working without it.
if [ -f "venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "venv/bin/activate"
fi

# Local LLM defaults tuned for Raspberry Pi latency.
# You can override any of these before running start.sh.
# Best default speed/quality balance for Raspberry Pi local inference.
export ZUBO_MODEL="${ZUBO_MODEL:-smollm2:360m}"
export ZUBO_NUM_CTX="${ZUBO_NUM_CTX:-1024}"
export ZUBO_NUM_PREDICT="${ZUBO_NUM_PREDICT:-64}"
export ZUBO_HISTORY_TURNS="${ZUBO_HISTORY_TURNS:-4}"
export ZUBO_LLM_KEEP_ALIVE="${ZUBO_LLM_KEEP_ALIVE:-30m}"

# brain_power.py owns all lifecycle behavior for brain/face/volume.
exec python "brain_power.py"
