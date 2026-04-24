#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/3] Stopping Sunshine..."
systemctl --user stop sunshine || true

echo
echo "[2/3] Disabling virtual monitor..."
"${repo_root}/scripts/disable_vkms_virtual_monitor.sh"

echo
echo "[3/3] Final status..."
"${repo_root}/scripts/second_screen_status.sh"
