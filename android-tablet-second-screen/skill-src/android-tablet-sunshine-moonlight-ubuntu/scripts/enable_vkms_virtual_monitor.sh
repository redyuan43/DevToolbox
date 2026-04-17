#!/usr/bin/env bash
set -euo pipefail

preferred_mode="${1:-2560x1600}"
anchor_output="${ANCHOR_OUTPUT:-HDMI-A-0}"
virtual_output="${VIRTUAL_OUTPUT:-Virtual-1-1}"

echo "[1/4] Loading vkms kernel module..."
if ! lsmod | awk '{print $1}' | grep -qx "vkms"; then
  sudo modprobe vkms enable_cursor=1
fi

echo "[2/4] Waiting for ${virtual_output} to appear in xrandr..."
for _ in $(seq 1 20); do
  if xrandr --query | awk '{print $1}' | grep -qx "${virtual_output}"; then
    break
  fi
  sleep 0.5
done

if ! xrandr --query | awk '{print $1}' | grep -qx "${virtual_output}"; then
  echo "Virtual output ${virtual_output} did not appear."
  exit 1
fi

if ! xrandr --query | awk -v out="${anchor_output}" '$1==out {found=1} END {exit(found?0:1)}'; then
  echo "Anchor output ${anchor_output} not found."
  exit 1
fi

echo "[3/4] Selecting mode..."
available_modes="$(xrandr --query | awk -v out="${virtual_output}" '
  $1==out {in_block=1; next}
  in_block && $0 !~ /^ / {exit}
  in_block && $1 ~ /^[0-9]/ {print $1}
')"

if ! grep -qx "${preferred_mode}" <<<"${available_modes}"; then
  for fallback in 1920x1200 1920x1080 1600x900 1024x768; do
    if grep -qx "${fallback}" <<<"${available_modes}"; then
      preferred_mode="${fallback}"
      break
    fi
  done
fi

if ! grep -qx "${preferred_mode}" <<<"${available_modes}"; then
  echo "No usable mode found for ${virtual_output}."
  echo "Available modes:"
  echo "${available_modes}"
  exit 1
fi

echo "[4/4] Enabling ${virtual_output} at ${preferred_mode}, right of ${anchor_output}..."
xrandr --output "${virtual_output}" --mode "${preferred_mode}" --right-of "${anchor_output}"

echo
echo "Virtual monitor enabled."
xrandr --query | sed -n '1,140p'
