#!/usr/bin/env bash
set -euo pipefail

echo "== Kernel modules =="
lsmod | rg 'vkms|amdgpu' || true

echo
echo "== DRM connectors =="
for f in /sys/class/drm/*/status; do
  echo "[$(basename "$(dirname "$f")")] $(cat "$f")"
done

echo
echo "== Xrandr =="
xrandr --query | sed -n '1,160p'

echo
echo "== Sunshine recent log =="
journalctl --user -u sunshine -n 80 --no-pager | sed -n '1,160p' || true
