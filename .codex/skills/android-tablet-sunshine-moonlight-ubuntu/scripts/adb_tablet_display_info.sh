#!/usr/bin/env bash
set -euo pipefail

echo "== ADB devices =="
adb devices -l

if ! adb get-state >/dev/null 2>&1; then
  echo
  echo "No authorized Android device is connected."
  exit 1
fi

echo
echo "== Device identity =="
adb shell getprop ro.product.manufacturer 2>/dev/null | tr -d '\r' | sed 's/^/manufacturer=/'
adb shell getprop ro.product.model 2>/dev/null | tr -d '\r' | sed 's/^/model=/'
adb shell getprop ro.build.version.release 2>/dev/null | tr -d '\r' | sed 's/^/android=/'

echo
echo "== Window manager =="
adb shell wm size 2>/dev/null | tr -d '\r'
adb shell wm density 2>/dev/null | tr -d '\r'

echo
echo "== Display summary =="
adb shell dumpsys display 2>/dev/null | rg -n "DisplayDeviceInfo|mViewports=|logicalWidth|logicalHeight|rotation" -m 20 || true

echo
echo "== Focused app =="
adb shell dumpsys window 2>/dev/null | rg -n "mCurrentFocus|mFocusedApp" -m 10 || true

echo
echo "== Installed clients =="
adb shell pm list packages 2>/dev/null | rg -i "moonlight|avnc" || true
