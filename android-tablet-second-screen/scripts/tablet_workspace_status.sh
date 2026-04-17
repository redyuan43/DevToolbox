#!/usr/bin/env bash
set -euo pipefail

display_num="${DISPLAY_NUM:-2}"
rfb_port="${RFB_PORT:-5902}"

echo "== TigerVNC Sessions =="
tigervncserver -list || true

echo
echo "== Listening Ports =="
ss -ltn | awk 'NR==1 || /:590[0-9]/'

echo
echo "== Workspace Service =="
systemctl --user status tablet-workspace.service --no-pager --lines=20 || true

echo
echo "== Tablet Client =="
adb shell dumpsys window | rg -n 'mCurrentFocus|mFocusedApp' | sed -n '1,10p' || true

echo
echo "== Connect Target =="
host_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ -n "${host_ip}" ]]; then
  echo "VNC host: ${host_ip}:${rfb_port}"
fi
