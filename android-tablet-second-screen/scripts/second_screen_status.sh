#!/usr/bin/env bash
set -euo pipefail

echo "== ADB =="
adb devices -l

echo
echo "== Network Interfaces =="
ip -brief addr

echo
echo "== USB Tethering =="
if ip -brief addr | awk '{print $1}' | grep -qx "usb0"; then
  ip -brief addr show usb0
else
  echo "usb0 is not present"
fi

echo
echo "== Displays =="
xrandr --query | sed -n '1,120p'

echo
echo "== Sunshine Service =="
systemctl --user is-enabled sunshine 2>/dev/null || true
systemctl --user is-active sunshine 2>/dev/null || true

echo
echo "== Sunshine Web UI =="
if curl -fkSs https://127.0.0.1:47990 >/dev/null 2>&1; then
  echo "Sunshine is reachable on https://127.0.0.1:47990"
else
  echo "Sunshine is not reachable on https://127.0.0.1:47990"
fi
