#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NUM=8
OPEN_WINDOWS=0
PASSTHROUGH_ARGS=()

readonly EXIT_USAGE=2

usage() {
  cat <<'EOF'
Usage: split --num 3|4|8|16 [--open] [split options]

Arrange existing windows on the current desktop. Use --open to create Ptyxis
windows first, then arrange them.

Options:
  --num N       Split count: 3, 4, 8, or 16. Default: 8
  --layout N    Backward-compatible alias for --num
  --open        Open Ptyxis windows before arranging
  --help        Show this help text

Examples:
  split --num 4
  split --num 16
  split --num 8 --open
EOF
}

die() {
  local code="$1"
  shift
  printf '%s: %s\n' "$SCRIPT_NAME" "$*" >&2
  exit "$code"
}

split_script_for_num() {
  case "$1" in
    3) printf '%s/split3.sh\n' "$SCRIPT_DIR" ;;
    4) printf '%s/split4.sh\n' "$SCRIPT_DIR" ;;
    8) printf '%s/split8.sh\n' "$SCRIPT_DIR" ;;
    16) printf '%s/split16.sh\n' "$SCRIPT_DIR" ;;
    *) return 1 ;;
  esac
}

while (( $# > 0 )); do
  case "$1" in
    --num|--layout)
      [[ $# -ge 2 ]] || die "$EXIT_USAGE" "$1 requires a value"
      NUM="$2"
      shift 2
      ;;
    --num=*|--layout=*)
      NUM="${1#*=}"
      shift
      ;;
    --open)
      OPEN_WINDOWS=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      PASSTHROUGH_ARGS+=( "$1" )
      shift
      ;;
  esac
done

split_script="$(split_script_for_num "$NUM")" || die "$EXIT_USAGE" "unsupported --num value: $NUM"
[[ -x "$split_script" ]] || die 1 "split script is not executable: $split_script"

if (( OPEN_WINDOWS == 1 )); then
  exec "${SCRIPT_DIR}/launch_ptyxis_split.sh" --num "$NUM" "${PASSTHROUGH_ARGS[@]}"
fi

exec "$split_script" "${PASSTHROUGH_ARGS[@]}"
