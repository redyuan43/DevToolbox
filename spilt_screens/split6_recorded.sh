#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
DRY_RUN=0
VERBOSE=0

readonly EXIT_ENV=1
readonly EXIT_NO_WINDOWS=2
readonly EXIT_MOVE_FAILED=3
readonly XDO_SETTLE_DELAY="0.05"
readonly SLOT_COUNT=6

readonly RECORDED_WORKAREA_X=66
readonly RECORDED_WORKAREA_Y=32
readonly RECORDED_WORKAREA_W=3374
readonly RECORDED_WORKAREA_H=1408

declare -a RECORDED_SLOT_X
declare -a RECORDED_SLOT_Y
declare -a RECORDED_SLOT_W
declare -a RECORDED_SLOT_H

declare -a SLOT_WINDOWS
declare -a SLOT_X
declare -a SLOT_Y
declare -a SLOT_W
declare -a SLOT_H

usage() {
  cat <<'EOF'
Usage: split6_recorded.sh [--dry-run] [--verbose] [--help]

Arrange up to six terminal windows into the recorded layout captured from the
current screen on 2026-03-14.

Behavior:
  - Works on the current workspace and the monitor of the active window
  - Only manages terminal-like windows
  - When there are more than six terminal windows, only the leftmost six are moved
  - The recorded layout is scaled from the original work area when needed

Options:
  --dry-run   Print the selected windows and target geometry without moving them
  --verbose   Print filtering and geometry details
  --help      Show this help text
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

run_xdotool() {
  xdotool "$@" >/dev/null 2>&1
}

init_recorded_slots() {
  RECORDED_SLOT_X=()
  RECORDED_SLOT_Y=()
  RECORDED_SLOT_W=()
  RECORDED_SLOT_H=()

  RECORDED_SLOT_X[1]=97
  RECORDED_SLOT_Y[1]=27
  RECORDED_SLOT_W[1]=866
  RECORDED_SLOT_H[1]=736

  RECORDED_SLOT_X[2]=911
  RECORDED_SLOT_Y[2]=27
  RECORDED_SLOT_W[2]=866
  RECORDED_SLOT_H[2]=692

  RECORDED_SLOT_X[3]=1725
  RECORDED_SLOT_Y[3]=27
  RECORDED_SLOT_W[3]=866
  RECORDED_SLOT_H[3]=695

  RECORDED_SLOT_X[4]=97
  RECORDED_SLOT_Y[4]=670
  RECORDED_SLOT_W[4]=866
  RECORDED_SLOT_H[4]=761

  RECORDED_SLOT_X[5]=911
  RECORDED_SLOT_Y[5]=670
  RECORDED_SLOT_W[5]=866
  RECORDED_SLOT_H[5]=761

  RECORDED_SLOT_X[6]=1725
  RECORDED_SLOT_Y[6]=670
  RECORDED_SLOT_W[6]=866
  RECORDED_SLOT_H[6]=761
}

init_slot_arrays() {
  local i
  SLOT_WINDOWS=()
  SLOT_X=()
  SLOT_Y=()
  SLOT_W=()
  SLOT_H=()
  for (( i=1; i<=SLOT_COUNT; i++ )); do
    SLOT_WINDOWS[$i]=""
    SLOT_X[$i]=0
    SLOT_Y[$i]=0
    SLOT_W[$i]=0
    SLOT_H[$i]=0
  done
}

hex_to_dec() {
  local hex="$1"
  printf '%d\n' "$hex"
}

extract_first_hex() {
  sed -n 's/.*\(0x[0-9a-fA-F]\+\).*/\1/p' | head -n1
}

get_active_window_id() {
  local prop hex
  prop="$(xprop -root _NET_ACTIVE_WINDOW 2>/dev/null || true)"
  hex="$(printf '%s\n' "$prop" | extract_first_hex)"
  [[ -n "$hex" ]] || return 1
  hex_to_dec "$hex"
}

get_current_desktop() {
  local prop
  prop="$(xprop -root _NET_CURRENT_DESKTOP 2>/dev/null || true)"
  printf '%s\n' "$prop" | sed -n 's/.*= \([0-9]\+\).*/\1/p' | head -n1
}

get_workarea_rect() {
  local current_desktop
  local prop
  local -a values

  current_desktop="$(get_current_desktop)"
  [[ -n "$current_desktop" ]] || return 1

  prop="$(xprop -root _NET_WORKAREA 2>/dev/null || true)"
  mapfile -t values < <(printf '%s\n' "$prop" | grep -oE '[0-9]+')
  (( ${#values[@]} >= 4 )) || return 1

  local start=$(( current_desktop * 4 ))
  if (( start + 3 >= ${#values[@]} )); then
    start=0
  fi

  printf '%s %s %s %s\n' \
    "${values[$start]}" \
    "${values[$((start + 1))]}" \
    "${values[$((start + 2))]}" \
    "${values[$((start + 3))]}"
}

get_monitor_rects() {
  xrandr --query 2>/dev/null | awk '
    / connected/ {
      name = $1
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^[0-9]+x[0-9]+\+[0-9]+\+[0-9]+$/) {
          split($i, dims, /[x+]/)
          printf "%s %s %s %s %s\n", name, dims[3], dims[4], dims[1], dims[2]
          break
        }
      }
    }
  '
}

get_window_geometry() {
  local window_id="$1"
  local info
  local x y width height
  local map_state

  info="$(xwininfo -id "$window_id" 2>/dev/null || true)"
  [[ -n "$info" ]] || return 1

  map_state="$(printf '%s\n' "$info" | sed -n 's/^  Map State: \(.*\)$/\1/p' | head -n1)"
  x="$(printf '%s\n' "$info" | sed -n 's/^  Absolute upper-left X:  *\([-0-9]\+\)$/\1/p' | head -n1)"
  y="$(printf '%s\n' "$info" | sed -n 's/^  Absolute upper-left Y:  *\([-0-9]\+\)$/\1/p' | head -n1)"
  width="$(printf '%s\n' "$info" | sed -n 's/^  Width: \([0-9]\+\)$/\1/p' | head -n1)"
  height="$(printf '%s\n' "$info" | sed -n 's/^  Height: \([0-9]\+\)$/\1/p' | head -n1)"

  [[ -n "$map_state" && -n "$x" && -n "$y" && -n "$width" && -n "$height" ]] || return 1
  printf '%s %s %s %s %s\n' "$map_state" "$x" "$y" "$width" "$height"
}

get_window_desktop() {
  local window_id="$1"
  local prop
  prop="$(xprop -id "$window_id" _NET_WM_DESKTOP 2>/dev/null || true)"
  printf '%s\n' "$prop" | sed -n 's/.*= \([-0-9]\+\).*/\1/p' | head -n1
}

get_window_type() {
  local window_id="$1"
  xprop -id "$window_id" _NET_WM_WINDOW_TYPE 2>/dev/null || true
}

get_window_state() {
  local window_id="$1"
  xprop -id "$window_id" _NET_WM_STATE 2>/dev/null || true
}

get_window_class() {
  local window_id="$1"
  xprop -id "$window_id" WM_CLASS 2>/dev/null | sed -n 's/.*= \(.*\)$/\1/p' | tr '[:upper:]' '[:lower:]'
}

get_frame_extents() {
  local window_id="$1"
  local prop
  local -a values

  prop="$(xprop -id "$window_id" _NET_FRAME_EXTENTS 2>/dev/null || true)"
  mapfile -t values < <(printf '%s\n' "$prop" | grep -oE -- '-?[0-9]+')
  if (( ${#values[@]} >= 4 )); then
    printf '%s %s %s %s\n' "${values[0]}" "${values[1]}" "${values[2]}" "${values[3]}"
  else
    printf '0 0 0 0\n'
  fi
}

get_window_resize_hints() {
  local window_id="$1"
  local prop
  local base_w="" base_h="" inc_w="" inc_h="" min_w="" min_h=""

  prop="$(xprop -id "$window_id" WM_NORMAL_HINTS 2>/dev/null || true)"
  [[ -n "$prop" ]] || return 1

  base_w="$(printf '%s\n' "$prop" | sed -n 's/.*base size: \([0-9]\+\) by [0-9]\+.*/\1/p' | head -n1)"
  base_h="$(printf '%s\n' "$prop" | sed -n 's/.*base size: [0-9]\+ by \([0-9]\+\).*/\1/p' | head -n1)"
  inc_w="$(printf '%s\n' "$prop" | sed -n 's/.*resize increment: \([0-9]\+\) by [0-9]\+.*/\1/p' | head -n1)"
  inc_h="$(printf '%s\n' "$prop" | sed -n 's/.*resize increment: [0-9]\+ by \([0-9]\+\).*/\1/p' | head -n1)"
  min_w="$(printf '%s\n' "$prop" | sed -n 's/.*minimum size: \([0-9]\+\) by [0-9]\+.*/\1/p' | head -n1)"
  min_h="$(printf '%s\n' "$prop" | sed -n 's/.*minimum size: [0-9]\+ by \([0-9]\+\).*/\1/p' | head -n1)"

  [[ -n "$base_w" ]] || base_w="${min_w:-0}"
  [[ -n "$base_h" ]] || base_h="${min_h:-0}"
  [[ -n "$inc_w" ]] || inc_w=1
  [[ -n "$inc_h" ]] || inc_h=1
  [[ -n "$min_w" ]] || min_w="$base_w"
  [[ -n "$min_h" ]] || min_h="$base_h"

  printf '%s %s %s %s %s %s\n' "$base_w" "$base_h" "$inc_w" "$inc_h" "$min_w" "$min_h"
}

compute_hint_min_units() {
  local base="$1"
  local inc="$2"
  local min_size="$3"
  local min_units=1

  if (( inc <= 0 )); then
    printf '1\n'
    return 0
  fi

  if (( min_size > base )); then
    min_units=$(( (min_size - base + inc - 1) / inc ))
  fi

  (( min_units < 1 )) && min_units=1
  printf '%s\n' "$min_units"
}

pick_best_hinted_units() {
  local target_client="$1"
  local base="$2"
  local inc="$3"
  local min_size="$4"
  local min_units raw_units lower_units upper_units
  local -a candidates
  local candidate units size delta
  local best_units="" best_size="" best_delta=""

  min_units="$(compute_hint_min_units "$base" "$inc" "$min_size")"
  raw_units="$min_units"
  if (( target_client > base )); then
    raw_units=$(( (target_client - base) / inc ))
  fi

  lower_units="$raw_units"
  upper_units=$(( raw_units + 1 ))
  candidates=( "$min_units" "$lower_units" "$upper_units" )

  for candidate in "${candidates[@]}"; do
    units="$candidate"
    (( units < min_units )) && units="$min_units"
    size=$(( base + units * inc ))
    delta=$(( target_client - size ))
    delta="${delta#-}"
    if [[ -z "$best_delta" || "$delta" -lt "$best_delta" ]]; then
      best_delta="$delta"
      best_units="$units"
      best_size="$size"
    fi
  done

  printf '%s %s %s\n' "$best_units" "$best_size" "$min_units"
}

hint_unit_adjustment_for_delta() {
  local delta="$1"
  local inc="$2"
  local abs_delta steps

  abs_delta="${delta#-}"
  if (( abs_delta == 0 || inc <= 0 )); then
    printf '0\n'
    return 0
  fi

  steps=$(( (abs_delta + inc - 1) / inc ))
  if (( delta < 0 )); then
    steps=$(( -steps ))
  fi

  printf '%s\n' "$steps"
}

get_window_title() {
  local window_id="$1"
  local title
  title="$(xdotool getwindowname "$window_id" 2>/dev/null || true)"
  if [[ -z "$title" ]]; then
    title="$(xprop -id "$window_id" WM_NAME 2>/dev/null | sed -n 's/.*= "\(.*\)"/\1/p' | head -n1)"
  fi
  [[ -n "$title" ]] || title="Window $window_id"
  printf '%s\n' "$title"
}

get_outer_geometry() {
  local window_id="$1"
  local geometry extents
  local map_state x y w h
  local left right top bottom

  geometry="$(get_window_geometry "$window_id")" || return 1
  extents="$(get_frame_extents "$window_id")"
  read -r map_state x y w h <<<"$geometry"
  read -r left right top bottom <<<"$extents"

  printf '%s %s %s %s\n' \
    "$(( x - left ))" \
    "$(( y - top ))" \
    "$(( w + left + right ))" \
    "$(( h + top + bottom ))"
}

window_center_belongs_to_monitor() {
  local window_id="$1"
  local monitor_x="$2"
  local monitor_y="$3"
  local monitor_w="$4"
  local monitor_h="$5"
  local geometry
  local map_state x y w h
  local center_x center_y

  geometry="$(get_window_geometry "$window_id")" || return 1
  read -r map_state x y w h <<<"$geometry"
  center_x=$(( x + (w / 2) ))
  center_y=$(( y + (h / 2) ))

  (( center_x >= monitor_x &&
     center_x < monitor_x + monitor_w &&
     center_y >= monitor_y &&
     center_y < monitor_y + monitor_h ))
}

window_is_terminal() {
  local window_id="$1"
  local class_name

  class_name="$(get_window_class "$window_id")"
  [[ -n "$class_name" ]] || return 1
  [[ "$class_name" =~ gnome-terminal|kitty|wezterm|alacritty|tilix|konsole|xterm|terminal ]]
}

window_is_candidate() {
  local window_id="$1"
  local desktop_id="$2"
  local monitor_x="$3"
  local monitor_y="$4"
  local monitor_w="$5"
  local monitor_h="$6"

  local geometry
  local map_state x y w h
  local window_desktop
  local window_type
  local window_state

  geometry="$(get_window_geometry "$window_id")" || {
    debug "skip $window_id: cannot read geometry"
    return 1
  }
  read -r map_state x y w h <<<"$geometry"

  if [[ "$map_state" != "IsViewable" ]]; then
    debug "skip $window_id: map state=$map_state"
    return 1
  fi

  if (( w < 180 || h < 120 )); then
    debug "skip $window_id: too small (${w}x${h})"
    return 1
  fi

  window_desktop="$(get_window_desktop "$window_id")"
  if [[ -n "$window_desktop" && "$window_desktop" != "$desktop_id" && "$window_desktop" != "-1" ]]; then
    debug "skip $window_id: desktop=$window_desktop"
    return 1
  fi

  window_type="$(get_window_type "$window_id")"
  if [[ "$window_type" == *"_NET_WM_WINDOW_TYPE_DESKTOP"* ]] ||
     [[ "$window_type" == *"_NET_WM_WINDOW_TYPE_DOCK"* ]] ||
     [[ "$window_type" == *"_NET_WM_WINDOW_TYPE_TOOLBAR"* ]] ||
     [[ "$window_type" == *"_NET_WM_WINDOW_TYPE_MENU"* ]] ||
     [[ "$window_type" == *"_NET_WM_WINDOW_TYPE_UTILITY"* ]] ||
     [[ "$window_type" == *"_NET_WM_WINDOW_TYPE_SPLASH"* ]] ||
     [[ "$window_type" == *"_NET_WM_WINDOW_TYPE_DIALOG"* ]] ||
     [[ "$window_type" == *"_NET_WM_WINDOW_TYPE_NOTIFICATION"* ]]; then
    debug "skip $window_id: window type filtered"
    return 1
  fi

  window_state="$(get_window_state "$window_id")"
  if [[ "$window_state" == *"_NET_WM_STATE_HIDDEN"* ]]; then
    debug "skip $window_id: hidden"
    return 1
  fi

  if ! window_center_belongs_to_monitor "$window_id" "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h"; then
    debug "skip $window_id: not on target monitor"
    return 1
  fi

  if ! window_is_terminal "$window_id"; then
    debug "skip $window_id: not a terminal"
    return 1
  fi

  return 0
}

get_stacking_order() {
  local prop
  local token
  local -a ids=()

  prop="$(xprop -root _NET_CLIENT_LIST_STACKING 2>/dev/null || true)"
  while read -r token; do
    ids+=("$(hex_to_dec "$token")")
  done < <(printf '%s\n' "$prop" | grep -oE '0x[0-9a-fA-F]+')

  if (( ${#ids[@]} == 0 )); then
    return 1
  fi

  local i
  for (( i=${#ids[@]} - 1; i >= 0; i-- )); do
    printf '%s\n' "${ids[$i]}"
  done
}

pick_target_monitor() {
  local active_window_id="$1"
  local geometry
  local map_state x y w h
  local center_x center_y
  local name monitor_x monitor_y monitor_w monitor_h

  geometry="$(get_window_geometry "$active_window_id")" || return 1
  read -r map_state x y w h <<<"$geometry"
  center_x=$(( x + (w / 2) ))
  center_y=$(( y + (h / 2) ))

  while read -r name monitor_x monitor_y monitor_w monitor_h; do
    [[ -n "$name" ]] || continue
    if (( center_x >= monitor_x &&
          center_x < monitor_x + monitor_w &&
          center_y >= monitor_y &&
          center_y < monitor_y + monitor_h )); then
      printf '%s %s %s %s %s\n' "$name" "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h"
      return 0
    fi
  done < <(get_monitor_rects)

  return 1
}

intersect_rects() {
  local ax="$1" ay="$2" aw="$3" ah="$4"
  local bx="$5" by="$6" bw="$7" bh="$8"
  local left right top bottom
  local out_w out_h

  left=$(( ax > bx ? ax : bx ))
  top=$(( ay > by ? ay : by ))
  right=$(( (ax + aw) < (bx + bw) ? (ax + aw) : (bx + bw) ))
  bottom=$(( (ay + ah) < (by + bh) ? (ay + ah) : (by + bh) ))
  out_w=$(( right - left ))
  out_h=$(( bottom - top ))

  (( out_w > 0 && out_h > 0 )) || return 1
  printf '%s %s %s %s\n' "$left" "$top" "$out_w" "$out_h"
}

prepare_window() {
  local window_id="$1"
  xprop -id "$window_id" -remove _NET_WM_STATE >/dev/null 2>&1 || true
  run_xdotool windowmap "$window_id" || true
  sleep "$XDO_SETTLE_DELAY"
}

move_window_outer() {
  local window_id="$1"
  local target_outer_x="$2"
  local target_outer_y="$3"
  local geometry extents outer
  local map_state client_x client_y client_w client_h
  local left right top bottom
  local outer_x outer_y outer_w outer_h
  local corrected_client_x corrected_client_y
  local iteration delta_x delta_y

  for iteration in 1 2 3 4 5 6; do
    geometry="$(get_window_geometry "$window_id")" || return 1
    extents="$(get_frame_extents "$window_id")"
    outer="$(get_outer_geometry "$window_id")" || return 1

    read -r map_state client_x client_y client_w client_h <<<"$geometry"
    read -r left right top bottom <<<"$extents"
    read -r outer_x outer_y outer_w outer_h <<<"$outer"

    delta_x=$(( target_outer_x - outer_x ))
    delta_y=$(( target_outer_y - outer_y ))
    if (( delta_x == 0 && delta_y == 0 )); then
      debug "move $window_id iter=$iteration actual_outer=(${outer_x},${outer_y}) delta=0x0"
      return 0
    fi

    corrected_client_x=$(( client_x + delta_x ))
    corrected_client_y=$(( client_y + delta_y ))
    debug "move $window_id iter=$iteration target_outer=(${target_outer_x},${target_outer_y}) actual_outer=(${outer_x},${outer_y}) delta=${delta_x}x${delta_y} client=(${corrected_client_x},${corrected_client_y})"
    run_xdotool windowmove "$window_id" "$corrected_client_x" "$corrected_client_y"
    sleep "$XDO_SETTLE_DELAY"
  done

  return 0
}

resize_window_using_hints() {
  local window_id="$1"
  local target_outer_w="$2"
  local target_outer_h="$3"
  local left="$4"
  local right="$5"
  local top="$6"
  local bottom="$7"
  local base_w="$8"
  local base_h="$9"
  local inc_w="${10}"
  local inc_h="${11}"
  local min_w="${12}"
  local min_h="${13}"
  local target_client_w target_client_h
  local width_hint height_hint
  local width_units expected_client_w min_units_w
  local height_units expected_client_h min_units_h
  local best_units_w best_units_h
  local best_abs_delta=999999
  local outer
  local outer_x outer_y actual_outer_w actual_outer_h
  local iteration delta_w delta_h current_abs_delta
  local adjust_w adjust_h

  target_client_w=$(( target_outer_w - left - right ))
  target_client_h=$(( target_outer_h - top - bottom ))
  (( target_client_w < min_w )) && target_client_w="$min_w"
  (( target_client_h < min_h )) && target_client_h="$min_h"

  width_hint="$(pick_best_hinted_units "$target_client_w" "$base_w" "$inc_w" "$min_w")"
  height_hint="$(pick_best_hinted_units "$target_client_h" "$base_h" "$inc_h" "$min_h")"
  read -r width_units expected_client_w min_units_w <<<"$width_hint"
  read -r height_units expected_client_h min_units_h <<<"$height_hint"

  best_units_w="$width_units"
  best_units_h="$height_units"

  for iteration in 1 2 3 4 5 6; do
    debug "resize $window_id hints iter=$iteration request_units=${width_units}x${height_units} target_outer=${target_outer_w}x${target_outer_h}"
    run_xdotool windowsize --usehints "$window_id" "$width_units" "$height_units"
    sleep "$XDO_SETTLE_DELAY"
    outer="$(get_outer_geometry "$window_id")" || return 1
    read -r outer_x outer_y actual_outer_w actual_outer_h <<<"$outer"
    delta_w=$(( target_outer_w - actual_outer_w ))
    delta_h=$(( target_outer_h - actual_outer_h ))
    current_abs_delta=$(( ${delta_w#-} + ${delta_h#-} ))
    debug "resize $window_id hints iter=$iteration actual_outer=${actual_outer_w}x${actual_outer_h} delta=${delta_w}x${delta_h}"

    if (( current_abs_delta < best_abs_delta )); then
      best_abs_delta="$current_abs_delta"
      best_units_w="$width_units"
      best_units_h="$height_units"
    fi

    if (( delta_w == 0 && delta_h == 0 )); then
      return 0
    fi

    adjust_w="$(hint_unit_adjustment_for_delta "$delta_w" "$inc_w")"
    adjust_h="$(hint_unit_adjustment_for_delta "$delta_h" "$inc_h")"
    if (( adjust_w == 0 && adjust_h == 0 )); then
      break
    fi

    width_units=$(( width_units + adjust_w ))
    height_units=$(( height_units + adjust_h ))
    (( width_units < min_units_w )) && width_units="$min_units_w"
    (( height_units < min_units_h )) && height_units="$min_units_h"
  done

  debug "resize $window_id hints settle best_units=${best_units_w}x${best_units_h}"
  run_xdotool windowsize --usehints "$window_id" "$best_units_w" "$best_units_h"
  sleep "$XDO_SETTLE_DELAY"
  return 0
}

resize_window_to_outer_size() {
  local window_id="$1"
  local target_outer_w="$2"
  local target_outer_h="$3"
  local extents
  local left right top bottom
  local resize_hints
  local base_w base_h inc_w inc_h min_w min_h
  local requested_w requested_h
  local outer
  local outer_x outer_y actual_outer_w actual_outer_h
  local iteration delta_w delta_h
  local best_request_w best_request_h
  local best_abs_delta=999999
  local current_abs_delta

  extents="$(get_frame_extents "$window_id")"
  read -r left right top bottom <<<"$extents"

  resize_hints="$(get_window_resize_hints "$window_id" || true)"
  if [[ -n "$resize_hints" ]]; then
    read -r base_w base_h inc_w inc_h min_w min_h <<<"$resize_hints"
    if (( inc_w > 1 || inc_h > 1 )); then
      debug "resize $window_id using hints base=${base_w}x${base_h} inc=${inc_w}x${inc_h} min=${min_w}x${min_h}"
      resize_window_using_hints \
        "$window_id" "$target_outer_w" "$target_outer_h" \
        "$left" "$right" "$top" "$bottom" \
        "$base_w" "$base_h" "$inc_w" "$inc_h" "$min_w" "$min_h"
      return 0
    fi
  fi

  requested_w=$(( target_outer_w - left - right ))
  requested_h=$(( target_outer_h - top - bottom ))
  best_request_w="$requested_w"
  best_request_h="$requested_h"
  (( requested_w < 80 )) && requested_w=80
  (( requested_h < 80 )) && requested_h=80

  for iteration in 1 2 3 4 5 6; do
    debug "resize $window_id iter=$iteration request_client=${requested_w}x${requested_h} target_outer=${target_outer_w}x${target_outer_h}"
    run_xdotool windowsize "$window_id" "$requested_w" "$requested_h"
    sleep "$XDO_SETTLE_DELAY"
    outer="$(get_outer_geometry "$window_id")" || return 1
    read -r outer_x outer_y actual_outer_w actual_outer_h <<<"$outer"
    delta_w=$(( target_outer_w - actual_outer_w ))
    delta_h=$(( target_outer_h - actual_outer_h ))
    current_abs_delta=$(( ${delta_w#-} + ${delta_h#-} ))
    debug "resize $window_id iter=$iteration actual_outer=${actual_outer_w}x${actual_outer_h} delta=${delta_w}x${delta_h}"

    if (( current_abs_delta < best_abs_delta )); then
      best_abs_delta="$current_abs_delta"
      best_request_w="$requested_w"
      best_request_h="$requested_h"
    fi

    if (( delta_w == 0 && delta_h == 0 )); then
      return 0
    fi

    requested_w=$(( requested_w + delta_w ))
    requested_h=$(( requested_h + delta_h ))
    (( requested_w < 80 )) && requested_w=80
    (( requested_h < 80 )) && requested_h=80
  done

  if (( best_abs_delta < 999999 )); then
    debug "resize $window_id settle best_request=${best_request_w}x${best_request_h}"
    run_xdotool windowsize "$window_id" "$best_request_w" "$best_request_h"
    sleep "$XDO_SETTLE_DELAY"
  fi

  return 0
}

scale_unsigned_value() {
  local value="$1"
  local recorded_total="$2"
  local current_total="$3"
  printf '%s\n' $(( (value * current_total + (recorded_total / 2)) / recorded_total ))
}

scale_signed_value() {
  local value="$1"
  local recorded_total="$2"
  local current_total="$3"
  local abs_value scaled

  if (( value < 0 )); then
    abs_value=$(( -value ))
    scaled="$(scale_unsigned_value "$abs_value" "$recorded_total" "$current_total")"
    printf '%s\n' "$(( -scaled ))"
    return 0
  fi

  scale_unsigned_value "$value" "$recorded_total" "$current_total"
}

build_slots_from_recorded_layout() {
  local usable_x="$1"
  local usable_y="$2"
  local usable_w="$3"
  local usable_h="$4"
  local slot
  local recorded_dx recorded_dy
  local scaled_dx scaled_dy scaled_w scaled_h

  init_recorded_slots
  init_slot_arrays

  for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
    recorded_dx=$(( RECORDED_SLOT_X[$slot] - RECORDED_WORKAREA_X ))
    recorded_dy=$(( RECORDED_SLOT_Y[$slot] - RECORDED_WORKAREA_Y ))
    scaled_dx="$(scale_signed_value "$recorded_dx" "$RECORDED_WORKAREA_W" "$usable_w")"
    scaled_dy="$(scale_signed_value "$recorded_dy" "$RECORDED_WORKAREA_H" "$usable_h")"
    scaled_w="$(scale_unsigned_value "${RECORDED_SLOT_W[$slot]}" "$RECORDED_WORKAREA_W" "$usable_w")"
    scaled_h="$(scale_unsigned_value "${RECORDED_SLOT_H[$slot]}" "$RECORDED_WORKAREA_H" "$usable_h")"

    SLOT_X[$slot]=$(( usable_x + scaled_dx ))
    SLOT_Y[$slot]=$(( usable_y + scaled_dy ))
    SLOT_W[$slot]="$scaled_w"
    SLOT_H[$slot]="$scaled_h"
  done
}

collect_terminal_candidates() {
  local desktop_id="$1"
  local monitor_x="$2"
  local monitor_y="$3"
  local monitor_w="$4"
  local monitor_h="$5"
  local window_id
  local outer
  local outer_x outer_y outer_w outer_h

  while read -r window_id; do
    [[ -n "$window_id" ]] || continue
    if ! window_is_candidate "$window_id" "$desktop_id" "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h"; then
      continue
    fi
    outer="$(get_outer_geometry "$window_id")" || continue
    read -r outer_x outer_y outer_w outer_h <<<"$outer"
    debug "candidate window=$window_id outer=(${outer_x},${outer_y},${outer_w},${outer_h}) title=$(get_window_title "$window_id")"
    printf '%s %s %s\n' "$outer_x" "$outer_y" "$window_id"
  done < <(get_stacking_order || true)
}

select_target_windows() {
  local desktop_id="$1"
  local monitor_x="$2"
  local monitor_y="$3"
  local monitor_w="$4"
  local monitor_h="$5"

  collect_terminal_candidates "$desktop_id" "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h" \
    | sort -n -k1,1 -k2,2 \
    | head -n "$SLOT_COUNT" \
    | sort -n -k2,2 -k1,1 \
    | awk '{print $3}'
}

place_window_in_slot() {
  local slot="$1"
  local window_id="$2"
  local slot_x="${SLOT_X[$slot]}"
  local slot_y="${SLOT_Y[$slot]}"
  local slot_w="${SLOT_W[$slot]}"
  local slot_h="${SLOT_H[$slot]}"
  local actual_outer
  local actual_x actual_y actual_w actual_h

  if (( DRY_RUN == 1 )); then
    log "DRY-RUN slot=$slot window=$window_id x=$slot_x y=$slot_y w=$slot_w h=$slot_h title=$(get_window_title "$window_id")"
    SLOT_WINDOWS[$slot]="$window_id"
    return 0
  fi

  prepare_window "$window_id"
  resize_window_to_outer_size "$window_id" "$slot_w" "$slot_h" || return 1
  move_window_outer "$window_id" "$slot_x" "$slot_y" || return 1
  actual_outer="$(get_outer_geometry "$window_id")" || return 1
  read -r actual_x actual_y actual_w actual_h <<<"$actual_outer"
  SLOT_WINDOWS[$slot]="$window_id"
  debug "placed slot=$slot window=$window_id target_outer=(${slot_x},${slot_y},${slot_w},${slot_h}) actual_outer=(${actual_x},${actual_y},${actual_w},${actual_h})"
}

compute_layout_context() {
  local active_window_id
  local current_desktop
  local target_monitor
  local workarea
  local intersected_area

  active_window_id="$(get_active_window_id)" || die "$EXIT_ENV" "could not determine the active window"
  current_desktop="$(get_current_desktop)"
  [[ -n "$current_desktop" ]] || die "$EXIT_ENV" "could not determine the current desktop"

  target_monitor="$(pick_target_monitor "$active_window_id")" || die "$EXIT_ENV" "could not map the active window to a monitor"
  read -r MONITOR_NAME MONITOR_X MONITOR_Y MONITOR_W MONITOR_H <<<"$target_monitor"

  workarea="$(get_workarea_rect)" || die "$EXIT_ENV" "could not read the desktop work area"
  intersected_area="$(intersect_rects "$MONITOR_X" "$MONITOR_Y" "$MONITOR_W" "$MONITOR_H" $workarea)" || \
    die "$EXIT_ENV" "monitor $MONITOR_NAME has no usable work area"
  read -r USABLE_X USABLE_Y USABLE_W USABLE_H <<<"$intersected_area"

  WORKSPACE_ID="$current_desktop"
  build_slots_from_recorded_layout "$USABLE_X" "$USABLE_Y" "$USABLE_W" "$USABLE_H"
}

run_once() {
  local -a selected_windows=()
  local slot=1
  local window_id

  compute_layout_context
  mapfile -t selected_windows < <(select_target_windows "$WORKSPACE_ID" "$MONITOR_X" "$MONITOR_Y" "$MONITOR_W" "$MONITOR_H")

  (( ${#selected_windows[@]} > 0 )) || die "$EXIT_NO_WINDOWS" "no terminal windows matched the current monitor"

  for window_id in "${selected_windows[@]}"; do
    place_window_in_slot "$slot" "$window_id" || die "$EXIT_MOVE_FAILED" "failed to place window $window_id"
    slot=$(( slot + 1 ))
    if (( slot > SLOT_COUNT )); then
      break
    fi
  done

  log "usable area: (${USABLE_X},${USABLE_Y} ${USABLE_W}x${USABLE_H}) on ${MONITOR_NAME}"
  if (( USABLE_W != RECORDED_WORKAREA_W || USABLE_H != RECORDED_WORKAREA_H )); then
    log "layout scaled from recorded work area: (${RECORDED_WORKAREA_X},${RECORDED_WORKAREA_Y} ${RECORDED_WORKAREA_W}x${RECORDED_WORKAREA_H})"
  fi

  for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
    window_id="${SLOT_WINDOWS[$slot]:-}"
    if [[ -n "$window_id" ]]; then
      log "slot $slot: [$window_id] $(get_window_title "$window_id")"
    else
      log "slot $slot: empty"
    fi
  done
}

parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      --dry-run)
        DRY_RUN=1
        ;;
      --verbose)
        VERBOSE=1
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        usage >&2
        die "$EXIT_ENV" "unknown argument: $1"
        ;;
    esac
    shift
  done
}

main() {
  require_cmd xdotool xprop xwininfo xrandr
  if [[ "${XDG_SESSION_TYPE:-x11}" != "x11" ]]; then
    die "$EXIT_ENV" "Wayland is not supported; please run this under X11"
  fi

  parse_args "$@"
  run_once
}

main "$@"
