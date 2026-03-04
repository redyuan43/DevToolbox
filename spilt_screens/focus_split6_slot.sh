#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
readonly EXIT_ENV=1
readonly EXIT_USAGE=2
readonly EXIT_STATE=3
readonly EXIT_EMPTY=4
readonly EXIT_MISSING_WINDOW=5
readonly GRID_COLS=3
readonly GRID_ROWS=2
readonly INNER_SEAM_OVERLAP_X=12
readonly INNER_SEAM_OVERLAP_Y=12
readonly STATE_FILE="${XDG_CACHE_HOME:-$HOME/.cache}/split6/state.env"
readonly FOCUS_SETTLE_DELAY="0.05"

usage() {
  cat <<'EOF'
Usage: focus_split6_slot.sh SLOT
       focus_split6_slot.sh --status
       focus_split6_slot.sh --help

Focus a split6 slot window and move the mouse to that slot's center.
Slots:
  1 2 3
  4 5 6
EOF
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

window_exists() {
  local window_id="$1"
  xprop -id "$window_id" WM_CLASS >/dev/null 2>&1
}

declare -a SLOT_X
declare -a SLOT_Y
declare -a SLOT_W
declare -a SLOT_H

init_slot_arrays() {
  local i
  SLOT_X=()
  SLOT_Y=()
  SLOT_W=()
  SLOT_H=()
  for (( i=1; i<=6; i++ )); do
    SLOT_X[$i]=0
    SLOT_Y[$i]=0
    SLOT_W[$i]=0
    SLOT_H[$i]=0
  done
}

adjust_slot_rect_for_overlap() {
  local col="$1"
  local row="$2"
  local base_x="$3"
  local base_y="$4"
  local base_w="$5"
  local base_h="$6"
  local left_extra=0
  local right_extra=0
  local top_extra=0
  local bottom_extra=0
  local seam_left=$(( INNER_SEAM_OVERLAP_X / 2 ))
  local seam_right=$(( INNER_SEAM_OVERLAP_X - seam_left ))
  local seam_top=$(( INNER_SEAM_OVERLAP_Y / 2 ))
  local seam_bottom=$(( INNER_SEAM_OVERLAP_Y - seam_top ))
  local slot_x="$base_x"
  local slot_y="$base_y"
  local slot_w="$base_w"
  local slot_h="$base_h"

  if (( col > 1 )); then
    left_extra="$seam_left"
  fi
  if (( col < GRID_COLS )); then
    right_extra="$seam_right"
  fi
  if (( row > 1 )); then
    top_extra="$seam_top"
  fi
  if (( row < GRID_ROWS )); then
    bottom_extra="$seam_bottom"
  fi

  slot_x=$(( slot_x - left_extra ))
  slot_y=$(( slot_y - top_extra ))
  slot_w=$(( slot_w + left_extra + right_extra ))
  slot_h=$(( slot_h + top_extra + bottom_extra ))

  printf '%s %s %s %s\n' "$slot_x" "$slot_y" "$slot_w" "$slot_h"
}

build_slots() {
  local usable_x="$1"
  local usable_y="$2"
  local usable_w="$3"
  local usable_h="$4"
  local col1 col2 col3 row1 row2
  local slot_rect

  col1=$(( usable_w / GRID_COLS ))
  col2=$(( usable_w / GRID_COLS ))
  col3=$(( usable_w - col1 - col2 ))
  row1=$(( usable_h / GRID_ROWS ))
  row2=$(( usable_h - row1 ))

  slot_rect="$(adjust_slot_rect_for_overlap 1 1 "$usable_x" "$usable_y" "$col1" "$row1")"
  read -r SLOT_X[1] SLOT_Y[1] SLOT_W[1] SLOT_H[1] <<<"$slot_rect"

  slot_rect="$(adjust_slot_rect_for_overlap 2 1 $(( usable_x + col1 )) "$usable_y" "$col2" "$row1")"
  read -r SLOT_X[2] SLOT_Y[2] SLOT_W[2] SLOT_H[2] <<<"$slot_rect"

  slot_rect="$(adjust_slot_rect_for_overlap 3 1 $(( usable_x + col1 + col2 )) "$usable_y" "$col3" "$row1")"
  read -r SLOT_X[3] SLOT_Y[3] SLOT_W[3] SLOT_H[3] <<<"$slot_rect"

  slot_rect="$(adjust_slot_rect_for_overlap 1 2 "$usable_x" $(( usable_y + row1 )) "$col1" "$row2")"
  read -r SLOT_X[4] SLOT_Y[4] SLOT_W[4] SLOT_H[4] <<<"$slot_rect"

  slot_rect="$(adjust_slot_rect_for_overlap 2 2 $(( usable_x + col1 )) $(( usable_y + row1 )) "$col2" "$row2")"
  read -r SLOT_X[5] SLOT_Y[5] SLOT_W[5] SLOT_H[5] <<<"$slot_rect"

  slot_rect="$(adjust_slot_rect_for_overlap 3 2 $(( usable_x + col1 + col2 )) $(( usable_y + row1 )) "$col3" "$row2")"
  read -r SLOT_X[6] SLOT_Y[6] SLOT_W[6] SLOT_H[6] <<<"$slot_rect"
}

load_state() {
  [[ -f "$STATE_FILE" ]] || die "$EXIT_STATE" "state file not found: $STATE_FILE; run split6.sh first"
  # shellcheck disable=SC1090
  source "$STATE_FILE"
  [[ -n "${USABLE_X:-}" && -n "${USABLE_Y:-}" && -n "${USABLE_W:-}" && -n "${USABLE_H:-}" ]] || \
    die "$EXIT_STATE" "state file is incomplete: $STATE_FILE"
  init_slot_arrays
  build_slots "$USABLE_X" "$USABLE_Y" "$USABLE_W" "$USABLE_H"
}

slot_window_id() {
  local slot="$1"
  case "$slot" in
    1) printf '%s\n' "${SLOT_1_WINDOW_ID:-}" ;;
    2) printf '%s\n' "${SLOT_2_WINDOW_ID:-}" ;;
    3) printf '%s\n' "${SLOT_3_WINDOW_ID:-}" ;;
    4) printf '%s\n' "${SLOT_4_WINDOW_ID:-}" ;;
    5) printf '%s\n' "${SLOT_5_WINDOW_ID:-}" ;;
    6) printf '%s\n' "${SLOT_6_WINDOW_ID:-}" ;;
    *) return 1 ;;
  esac
}

focus_slot() {
  local slot="$1"
  local window_id center_x center_y

  window_id="$(slot_window_id "$slot")" || die "$EXIT_USAGE" "invalid slot: $slot"
  [[ -n "$window_id" ]] || die "$EXIT_EMPTY" "slot $slot is empty"
  window_exists "$window_id" || die "$EXIT_MISSING_WINDOW" "slot $slot window no longer exists: $window_id"

  center_x=$(( SLOT_X[$slot] + (SLOT_W[$slot] / 2) ))
  center_y=$(( SLOT_Y[$slot] + (SLOT_H[$slot] / 2) ))

  xdotool windowactivate "$window_id"
  sleep "$FOCUS_SETTLE_DELAY"
  xdotool mousemove "$center_x" "$center_y"

  printf 'Focused slot %s [%s] at (%s,%s)\n' "$slot" "$window_id" "$center_x" "$center_y"
}

print_status() {
  local slot window_id
  printf 'state: %s\n' "$STATE_FILE"
  printf 'usable: (%s,%s %sx%s)\n' "$USABLE_X" "$USABLE_Y" "$USABLE_W" "$USABLE_H"
  for slot in 1 2 3 4 5 6; do
    window_id="$(slot_window_id "$slot")"
    if [[ -n "$window_id" ]]; then
      printf 'slot %s: [%s] center=(%s,%s)\n' \
        "$slot" \
        "$window_id" \
        "$(( SLOT_X[$slot] + (SLOT_W[$slot] / 2) ))" \
        "$(( SLOT_Y[$slot] + (SLOT_H[$slot] / 2) ))"
    else
      printf 'slot %s: empty center=(%s,%s)\n' \
        "$slot" \
        "$(( SLOT_X[$slot] + (SLOT_W[$slot] / 2) ))" \
        "$(( SLOT_Y[$slot] + (SLOT_H[$slot] / 2) ))"
    fi
  done
}

main() {
  require_cmd xdotool xprop
  load_state

  case "${1:-}" in
    --help|-h|"")
      usage
      [[ $# -gt 0 ]] || exit "$EXIT_USAGE"
      ;;
    --status)
      print_status
      ;;
    1|2|3|4|5|6)
      focus_slot "$1"
      ;;
    *)
      die "$EXIT_USAGE" "invalid argument: $1"
      ;;
  esac
}

main "$@"
