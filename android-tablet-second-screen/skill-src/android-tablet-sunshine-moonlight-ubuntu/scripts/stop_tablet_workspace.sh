#!/usr/bin/env bash
set -euo pipefail

display_num="${DISPLAY_NUM:-2}"

if tigervncserver -list 2>/dev/null | rg -q "^:${display_num}\\b"; then
  exec tigervncserver -kill ":${display_num}"
fi

echo "TigerVNC display :${display_num} is not running."
