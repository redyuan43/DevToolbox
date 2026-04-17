#!/usr/bin/env bash
set -euo pipefail

virtual_output="${VIRTUAL_OUTPUT:-Virtual-1-1}"

if xrandr --query | awk '{print $1}' | grep -qx "${virtual_output}"; then
  xrandr --output "${virtual_output}" --off || true
fi

if lsmod | awk '{print $1}' | grep -qx "vkms"; then
  sudo modprobe -r vkms || true
fi

echo "Virtual monitor disabled (best effort)."
xrandr --query | sed -n '1,120p'
