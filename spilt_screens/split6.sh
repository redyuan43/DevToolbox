#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
DRY_RUN=0
VERBOSE=0
MODE="once"

readonly EXIT_ENV=1
readonly EXIT_NO_WINDOWS=2
readonly EXIT_MOVE_FAILED=3
readonly EXIT_STATE=4
readonly XDO_SETTLE_DELAY="0.05"
readonly DAEMON_POLL_INTERVAL="0.6"
readonly SLOT_COUNT=6
readonly GRID_COLS=3
readonly GRID_ROWS=2
readonly INNER_SEAM_OVERLAP_X=12
readonly INNER_SEAM_OVERLAP_Y=12
readonly STATE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/split6"
readonly PID_FILE="${STATE_DIR}/daemon.pid"
readonly STATE_FILE="${STATE_DIR}/state.env"
readonly LOG_FILE="${STATE_DIR}/daemon.log"

usage() {
  cat <<'EOF'
Usage: split6.sh [--daemon|--status|--stop] [--dry-run] [--verbose] [--help]

Arrange windows into a fixed 3x2 grid on the current monitor's usable work area.

Options:
  --daemon    Start a background watcher that fills empty slots automatically
  --status    Show daemon and slot status
  --stop      Stop the running daemon
  --dry-run   Print target slots without moving windows
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

ensure_state_dir() {
  mkdir -p "$STATE_DIR"
}

pid_is_running() {
  local pid="$1"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

get_running_daemon_pid() {
  local pid
  [[ -f "$PID_FILE" ]] || return 1
  pid="$(<"$PID_FILE")"
  if pid_is_running "$pid"; then
    printf '%s\n' "$pid"
    return 0
  fi
  rm -f "$PID_FILE"
  return 1
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

window_exists() {
  local window_id="$1"
  xprop -id "$window_id" WM_CLASS >/dev/null 2>&1
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

declare -a SLOT_WINDOWS
declare -a SLOT_X
declare -a SLOT_Y
declare -a SLOT_W
declare -a SLOT_H

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

slot_is_empty() {
  local slot="$1"
  [[ -z "${SLOT_WINDOWS[$slot]:-}" ]]
}

find_first_empty_slot() {
  local slot
  for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
    if slot_is_empty "$slot"; then
      printf '%s\n' "$slot"
      return 0
    fi
  done
  return 1
}

window_in_slots() {
  local window_id="$1"
  local slot
  for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
    if [[ "${SLOT_WINDOWS[$slot]:-}" == "$window_id" ]]; then
      return 0
    fi
  done
  return 1
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

write_state_file() {
  ensure_state_dir
  {
    printf 'WORKSPACE_ID=%q\n' "$WORKSPACE_ID"
    printf 'MONITOR_NAME=%q\n' "$MONITOR_NAME"
    printf 'MONITOR_X=%q\n' "$MONITOR_X"
    printf 'MONITOR_Y=%q\n' "$MONITOR_Y"
    printf 'MONITOR_W=%q\n' "$MONITOR_W"
    printf 'MONITOR_H=%q\n' "$MONITOR_H"
    printf 'USABLE_X=%q\n' "$USABLE_X"
    printf 'USABLE_Y=%q\n' "$USABLE_Y"
    printf 'USABLE_W=%q\n' "$USABLE_W"
    printf 'USABLE_H=%q\n' "$USABLE_H"
    local slot
    for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
      printf 'SLOT_%d_WINDOW_ID=%q\n' "$slot" "${SLOT_WINDOWS[$slot]:-}"
    done
  } >"$STATE_FILE"
}

load_state_file() {
  [[ -f "$STATE_FILE" ]] || die "$EXIT_STATE" "state file not found: $STATE_FILE"
  # shellcheck disable=SC1090
  source "$STATE_FILE"
  init_slot_arrays
  local slot var_name
  for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
    var_name="SLOT_${slot}_WINDOW_ID"
    SLOT_WINDOWS[$slot]="${!var_name:-}"
  done
  build_slots "$USABLE_X" "$USABLE_Y" "$USABLE_W" "$USABLE_H"
}

print_status() {
  local pid
  if pid="$(get_running_daemon_pid 2>/dev/null)"; then
    log "daemon: running (pid $pid)"
  else
    log "daemon: not running"
  fi

  if [[ -f "$STATE_FILE" ]]; then
    load_state_file
    log "monitor: ${MONITOR_NAME} (${MONITOR_X},${MONITOR_Y} ${MONITOR_W}x${MONITOR_H})"
    log "usable: (${USABLE_X},${USABLE_Y} ${USABLE_W}x${USABLE_H})"
    log "workspace: ${WORKSPACE_ID}"
    local slot window_id title
    for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
      window_id="${SLOT_WINDOWS[$slot]:-}"
      if [[ -n "$window_id" ]]; then
        title="$(get_window_title "$window_id")"
        log "slot $slot: [$window_id] $title"
      else
        log "slot $slot: empty"
      fi
    done
  fi
}

stop_daemon() {
  local pid
  if ! pid="$(get_running_daemon_pid 2>/dev/null)"; then
    rm -f "$PID_FILE"
    log "daemon: not running"
    return 0
  fi

  kill "$pid" >/dev/null 2>&1 || true
  rm -f "$PID_FILE" "$STATE_FILE"
  log "daemon: stopped"
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
  init_slot_arrays
  build_slots "$USABLE_X" "$USABLE_Y" "$USABLE_W" "$USABLE_H"
}

collect_candidate_windows() {
  local desktop_id="$1"
  local monitor_x="$2"
  local monitor_y="$3"
  local monitor_w="$4"
  local monitor_h="$5"
  local include_active="${6:-1}"
  local active_window_id=""
  local stack_window_id
  local -A seen=()

  if [[ "$include_active" == "1" ]]; then
    active_window_id="$(get_active_window_id || true)"
    if [[ -n "$active_window_id" ]] && window_is_candidate "$active_window_id" "$desktop_id" "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h"; then
      printf '%s\n' "$active_window_id"
      seen["$active_window_id"]=1
    fi
  fi

  while read -r stack_window_id; do
    [[ -n "$stack_window_id" ]] || continue
    [[ -z "${seen[$stack_window_id]:-}" ]] || continue
    if window_is_candidate "$stack_window_id" "$desktop_id" "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h"; then
      printf '%s\n' "$stack_window_id"
      seen["$stack_window_id"]=1
    fi
  done < <(get_stacking_order || true)
}

fill_slots_from_candidates() {
  local candidate
  local slot
  local filled=0

  while read -r candidate; do
    [[ -n "$candidate" ]] || continue
    if window_in_slots "$candidate"; then
      continue
    fi
    slot="$(find_first_empty_slot || true)"
    [[ -n "$slot" ]] || break
    place_window_in_slot "$slot" "$candidate" || die "$EXIT_MOVE_FAILED" "failed to place window $candidate"
    filled=1
  done < <(collect_candidate_windows "$WORKSPACE_ID" "$MONITOR_X" "$MONITOR_Y" "$MONITOR_W" "$MONITOR_H")

  return "$filled"
}

render_empty_slots() {
  local slot
  for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
    if slot_is_empty "$slot"; then
      debug "slot $slot empty target=(${SLOT_X[$slot]},${SLOT_Y[$slot]},${SLOT_W[$slot]},${SLOT_H[$slot]})"
    fi
  done
}

refresh_managed_slots() {
  local slot window_id
  for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
    window_id="${SLOT_WINDOWS[$slot]:-}"
    [[ -n "$window_id" ]] || continue
    if ! window_exists "$window_id" || ! window_is_candidate "$window_id" "$WORKSPACE_ID" "$MONITOR_X" "$MONITOR_Y" "$MONITOR_W" "$MONITOR_H"; then
      debug "release slot $slot window=$window_id"
      SLOT_WINDOWS[$slot]=""
    fi
  done
}

initial_layout() {
  fill_slots_from_candidates || true
  render_empty_slots
  write_state_file
}

daemon_loop() {
  trap 'rm -f "$PID_FILE"; exit 0' INT TERM
  echo "$$" >"$PID_FILE"
  compute_layout_context
  initial_layout

  local last_active=""
  local last_stack=""
  local current_active current_stack

  while true; do
    refresh_managed_slots
    current_active="$(xprop -root _NET_ACTIVE_WINDOW 2>/dev/null || true)"
    current_stack="$(xprop -root _NET_CLIENT_LIST_STACKING 2>/dev/null || true)"

    if [[ "$current_active" != "$last_active" || "$current_stack" != "$last_stack" ]]; then
      fill_slots_from_candidates || true
      write_state_file
      last_active="$current_active"
      last_stack="$current_stack"
    else
      write_state_file
    fi

    sleep "$DAEMON_POLL_INTERVAL"
  done
}

start_daemon() {
  local pid
  local -a daemon_args
  ensure_state_dir
  if pid="$(get_running_daemon_pid 2>/dev/null)"; then
    log "daemon: already running (pid $pid)"
    return 0
  fi

  daemon_args=( "$0" --run-daemon )
  if (( VERBOSE == 1 )); then
    daemon_args+=( --verbose )
  fi

  nohup "${daemon_args[@]}" >"$LOG_FILE" 2>&1 &
  sleep 0.2
  pid="$(get_running_daemon_pid 2>/dev/null || true)"
  [[ -n "$pid" ]] || die "$EXIT_STATE" "failed to start daemon"
  log "daemon: started (pid $pid)"
  log "log: $LOG_FILE"
}

run_once() {
  compute_layout_context
  fill_slots_from_candidates || true
  render_empty_slots
  write_state_file

  local slotted=0
  local slot window_id
  for (( slot=1; slot<=SLOT_COUNT; slot++ )); do
    window_id="${SLOT_WINDOWS[$slot]:-}"
    if [[ -n "$window_id" ]]; then
      slotted=$(( slotted + 1 ))
    fi
  done

  (( slotted > 0 )) || die "$EXIT_NO_WINDOWS" "no windows matched the current monitor"

  log "usable area: (${USABLE_X},${USABLE_Y} ${USABLE_W}x${USABLE_H}) on ${MONITOR_NAME}"
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
      --daemon)
        MODE="daemon"
        ;;
      --run-daemon)
        MODE="run-daemon"
        ;;
      --status)
        MODE="status"
        ;;
      --stop)
        MODE="stop"
        ;;
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
        die "$EXIT_ENV" "unknown argument: $1"
        ;;
    esac
    shift
  done
}

main() {
  local session_type="${XDG_SESSION_TYPE:-}"

  parse_args "$@"
  require_cmd xdotool xprop xwininfo xrandr nohup

  if [[ -z "${DISPLAY:-}" ]]; then
    die "$EXIT_ENV" "DISPLAY is not set; this command must run inside an X11 session"
  fi

  if [[ "$session_type" == "wayland" ]]; then
    die "$EXIT_ENV" "Wayland is not supported; log in with Ubuntu on X11"
  fi

  xprop -root _NET_ACTIVE_WINDOW >/dev/null 2>&1 || die "$EXIT_ENV" "cannot access X11 display ${DISPLAY}"

  case "$MODE" in
    once)
      run_once
      ;;
    daemon)
      start_daemon
      ;;
    run-daemon)
      daemon_loop
      ;;
    status)
      print_status
      ;;
    stop)
      stop_daemon
      ;;
    *)
      die "$EXIT_ENV" "unsupported mode: $MODE"
      ;;
  esac
}

main "$@"
