#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="2560x1600"
launch_moonlight=0

for arg in "$@"; do
  case "${arg}" in
    --launch-moonlight)
      launch_moonlight=1
      ;;
    *)
      mode="${arg}"
      ;;
  esac
done

echo "[1/4] Enabling virtual monitor at ${mode}..."
"${repo_root}/scripts/enable_vkms_virtual_monitor.sh" "${mode}"

echo
echo "[2/4] Restarting Sunshine..."
systemctl --user restart sunshine

echo
echo "[3/4] Waiting for Sunshine to become active..."
for _ in $(seq 1 20); do
  if systemctl --user is-active --quiet sunshine; then
    break
  fi
  sleep 0.5
done

if ! systemctl --user is-active --quiet sunshine; then
  echo "Sunshine did not become active in time." >&2
  exit 1
fi

echo
echo "[4/4] Checking ADB and optional Moonlight launch..."
device_serial="$(adb devices | awk 'NR>1 && $2=="device" {print $1; exit}')"
if [[ -n "${device_serial}" ]]; then
  echo "Detected Android device: ${device_serial}"
  if [[ "${launch_moonlight}" -eq 1 ]]; then
    adb -s "${device_serial}" shell monkey -p com.limelight -c android.intent.category.LAUNCHER 1 >/dev/null
    echo "Moonlight launch intent sent."
  fi
else
  echo "No authorized Android device found via adb."
fi

echo
"${repo_root}/scripts/second_screen_status.sh"
