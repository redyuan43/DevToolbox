#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NUM=8
COUNT=""
WORKDIR="$HOME"
SETTLE_SECONDS="1.2"
VERBOSE=0

readonly EXIT_ENV=1
readonly EXIT_USAGE=2

usage() {
  cat <<'EOF'
Usage: split --num 3|4|8|16 [--count N] [--workdir DIR] [--settle SECONDS] [--verbose] [--help]

Open multiple Ptyxis windows and arrange them with the matching split script.

Options:
  --num N          Number of split windows: 3, 4, 8, or 16. Default: 8
  --layout N       Backward-compatible alias for --num
  --count N        Number of Ptyxis windows to open. Default: --num value
  --workdir DIR    Working directory for new Ptyxis windows. Default: $HOME
  --settle SECONDS Wait after launching windows before the final arrange. Default: 1.2
  --verbose        Print launch details
  --help           Show this help text
EOF
}

log() {
  printf '%s\n' "$*"
}

debug() {
  if [[ "$VERBOSE" -eq 1 ]]; then
    printf '[debug] %s\n' "$*" >&2
  fi
}

die() {
  local code="$1"
  shift
  printf '%s: %s\n' "$SCRIPT_NAME" "$*" >&2
  exit "$code"
}

require_cmd() {
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || die "$EXIT_ENV" "missing dependency: $cmd"
  done
}

slot_count_for_layout() {
  case "$1" in
    3) printf '3\n' ;;
    4) printf '4\n' ;;
    8) printf '8\n' ;;
    16) printf '16\n' ;;
    *) return 1 ;;
  esac
}

split_script_for_layout() {
  case "$1" in
    3) printf '%s/split3.sh\n' "$SCRIPT_DIR" ;;
    4) printf '%s/split4.sh\n' "$SCRIPT_DIR" ;;
    8) printf '%s/split8.sh\n' "$SCRIPT_DIR" ;;
    16) printf '%s/split16.sh\n' "$SCRIPT_DIR" ;;
    *) return 1 ;;
  esac
}

validate_positive_int() {
  local value="$1"
  [[ "$value" =~ ^[1-9][0-9]*$ ]]
}

launch_ptyxis_window() {
  local dir="$1"

  # Ptyxis accepts DIR as the argument to --new-window.
  ptyxis --new-window "$dir" >/dev/null 2>&1 &
}

while (( $# > 0 )); do
  case "$1" in
    --num|--layout)
      [[ $# -ge 2 ]] || die "$EXIT_USAGE" "$1 requires a value"
      NUM="$2"
      shift 2
      ;;
    --num=*)
      NUM="${1#*=}"
      shift
      ;;
    --layout=*)
      NUM="${1#*=}"
      shift
      ;;
    --count)
      [[ $# -ge 2 ]] || die "$EXIT_USAGE" "--count requires a value"
      COUNT="$2"
      shift 2
      ;;
    --count=*)
      COUNT="${1#*=}"
      shift
      ;;
    --workdir)
      [[ $# -ge 2 ]] || die "$EXIT_USAGE" "--workdir requires a value"
      WORKDIR="$2"
      shift 2
      ;;
    --workdir=*)
      WORKDIR="${1#*=}"
      shift
      ;;
    --settle)
      [[ $# -ge 2 ]] || die "$EXIT_USAGE" "--settle requires a value"
      SETTLE_SECONDS="$2"
      shift 2
      ;;
    --settle=*)
      SETTLE_SECONDS="${1#*=}"
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "$EXIT_USAGE" "unknown option: $1"
      ;;
  esac
done

slot_count="$(slot_count_for_layout "$NUM")" || die "$EXIT_USAGE" "unsupported --num value: $NUM"
split_script="$(split_script_for_layout "$NUM")" || die "$EXIT_USAGE" "unsupported --num value: $NUM"

[[ -x "$split_script" ]] || die "$EXIT_ENV" "split script is not executable: $split_script"
[[ -d "$WORKDIR" ]] || die "$EXIT_ENV" "working directory does not exist: $WORKDIR"
validate_positive_int "${COUNT:-$slot_count}" || die "$EXIT_USAGE" "--count must be a positive integer"
COUNT="${COUNT:-$slot_count}"

require_cmd ptyxis xdotool xprop xwininfo xrandr

if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
  die "$EXIT_ENV" "Wayland session is not supported; use Ubuntu on X11"
fi

debug "num=$NUM count=$COUNT workdir=$WORKDIR split_script=$split_script"

if [[ "$NUM" == "4" || "$NUM" == "8" || "$NUM" == "16" ]]; then
  "$split_script" --daemon >/dev/null 2>&1 || true
fi

for (( i=1; i<=COUNT; i++ )); do
  debug "launch Ptyxis window $i/$COUNT"
  launch_ptyxis_window "$WORKDIR"
  sleep 0.08
done

sleep "$SETTLE_SECONDS"
"$split_script"

log "opened $COUNT Ptyxis window(s) and applied split --num $NUM"
