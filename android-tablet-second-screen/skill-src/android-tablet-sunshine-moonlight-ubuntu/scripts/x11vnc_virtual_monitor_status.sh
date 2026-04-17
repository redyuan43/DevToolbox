#!/usr/bin/env bash
set -euo pipefail

rfbport="${RFB_PORT:-5903}"
log_file="${LOG_FILE:-$HOME/.cache/x11vnc-virtual-monitor.log}"

echo "== x11vnc processes =="
ps -ef | rg 'x11vnc' | rg -v rg || true

echo
echo "== listening port =="
ss -ltnp | rg ":${rfbport}\\b" || true

echo
echo "== recent log =="
tail -n 40 "${log_file}" 2>/dev/null || echo "No log yet: ${log_file}"
