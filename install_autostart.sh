#!/bin/bash

set -eu

SERVICE_NAME="zubo-power.service"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_SRC="$REPO_ROOT/$SERVICE_NAME"
SERVICE_DST="/etc/systemd/system/$SERVICE_NAME"

if [ ! -f "$SERVICE_SRC" ]; then
  echo "[install] Missing service file: $SERVICE_SRC"
  exit 1
fi

echo "[install] Installing $SERVICE_NAME to $SERVICE_DST"
sudo cp "$SERVICE_SRC" "$SERVICE_DST"

echo "[install] Reloading systemd daemon"
sudo systemctl daemon-reload

echo "[install] Clearing failed state (if any)"
sudo systemctl reset-failed "$SERVICE_NAME" || true

echo "[install] Enabling service at boot"
sudo systemctl enable "$SERVICE_NAME"

echo "[install] Starting service now"
sudo systemctl restart "$SERVICE_NAME"

echo "[install] Done."
echo "[install] Check status with: sudo systemctl status $SERVICE_NAME"
echo "[install] Check logs with: sudo journalctl -u $SERVICE_NAME -f"
