#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <command> [args...]" >&2
  exit 1
fi

export DISPLAY="${DISPLAY_OVERRIDE:-:2}"
exec "$@"
