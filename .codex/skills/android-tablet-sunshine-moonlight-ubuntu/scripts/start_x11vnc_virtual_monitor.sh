#!/usr/bin/env bash
set -euo pipefail

clip="${1:-2560x1600+3440+0}"
rfbport="${RFB_PORT:-5903}"
passwd_file="${PASSWORD_FILE:-$HOME/.vnc/passwd}"
log_file="${LOG_FILE:-$HOME/.cache/x11vnc-virtual-monitor.log}"

mkdir -p "$(dirname "${log_file}")"

if [[ ! -f "${passwd_file}" ]]; then
  echo "Missing VNC password file: ${passwd_file}"
  echo "Create one with: x11vnc -storepasswd"
  exit 1
fi

pkill -f "x11vnc.*${rfbport}" || true

nohup x11vnc \
  -display "${DISPLAY:-:0}" \
  -clip "${clip}" \
  -rfbport "${rfbport}" \
  -forever \
  -shared \
  -noxdamage \
  -passwdfile "${passwd_file}" \
  >"${log_file}" 2>&1 &

sleep 1
echo "x11vnc virtual monitor started on port ${rfbport}"
echo "clip=${clip}"
echo "log=${log_file}"
ss -ltnp | rg ":${rfbport}\\b" || true
