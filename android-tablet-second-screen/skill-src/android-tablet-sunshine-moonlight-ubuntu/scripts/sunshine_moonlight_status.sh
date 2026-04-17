#!/usr/bin/env bash
set -euo pipefail

echo "== Sunshine service =="
systemctl --user is-enabled sunshine 2>/dev/null || true
systemctl --user is-active sunshine 2>/dev/null || true

echo
echo "== Sunshine web UI =="
http_code="$(curl -k -s -o /dev/null -w '%{http_code}' https://127.0.0.1:47990 || true)"
if [[ "${http_code}" == "200" || "${http_code}" == "401" || "${http_code}" == "403" ]]; then
  echo "reachable: https://127.0.0.1:47990 (http ${http_code})"
else
  echo "not reachable: https://127.0.0.1:47990 (http ${http_code:-000})"
fi

echo
echo "== Host displays =="
xrandr --query | sed -n '1,160p'

echo
echo "== Host IPs =="
ip -brief addr

echo
echo "== Android focus and packages =="
if adb get-state >/dev/null 2>&1; then
  adb shell dumpsys window 2>/dev/null | rg -n "mCurrentFocus|mFocusedApp" -m 10 || true
  echo
  adb shell pm list packages 2>/dev/null | rg -i "moonlight|avnc" || true
else
  echo "No authorized Android device is connected."
fi

echo
echo "== Sunshine recent log =="
journalctl --user -u sunshine -n 80 --no-pager 2>/dev/null | sed -n '1,160p' || true
