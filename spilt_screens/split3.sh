#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
DRY_RUN=0
VERBOSE=0

readonly EXIT_ENV=1
readonly EXIT_NO_WINDOWS=2
readonly EXIT_MOVE_FAILED=3
readonly XDO_SETTLE_DELAY="0.05"

usage() {
  cat <<'EOF'
Usage: split3.sh [--dry-run] [--verbose] [--help]

Tile the current monitor's windows into 1, 2, or 3 equal-width columns.

Options:
  --dry-run   Print the selected windows and target geometry without moving them
  --verbose   Print filtering details while collecting candidate windows
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

window_is_candidate() {
  local window_id="$1"
  local current_desktop="$2"
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

  if (( w < 200 || h < 120 )); then
    debug "skip $window_id: too small (${w}x${h})"
    return 1
  fi

  window_desktop="$(get_window_desktop "$window_id")"
  if [[ -n "$window_desktop" && "$window_desktop" != "$current_desktop" && "$window_desktop" != "-1" ]]; then
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

  debug "accept $window_id"
  return 0
}

get_stacking_order() {
  local prop
  local -a ids=()
  local token

  prop="$(xprop -root _NET_CLIENT_LIST_STACKING 2>/dev/null || true)"
  while read -r token; do
    ids+=("$(hex_to_dec "$token")")
  done < <(printf '%s\n' "$prop" | grep -oE '0x[0-9a-fA-F]+')

  if (( ${#ids[@]} == 0 )); then
    return 1
  fi

  local i
  for (( i=${#ids[@]}-1; i>=0; i-- )); do
    printf '%s\n' "${ids[$i]}"
  done
}

pick_target_monitor() {
  local active_window_id="$1"
  local geometry
  local map_state x y w h
  local center_x center_y
  local line
  local name monitor_x monitor_y monitor_w monitor_h

  geometry="$(get_window_geometry "$active_window_id")" || return 1
  read -r map_state x y w h <<<"$geometry"

  center_x=$(( x + (w / 2) ))
  center_y=$(( y + (h / 2) ))

  while read -r line; do
    read -r name monitor_x monitor_y monitor_w monitor_h <<<"$line"
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
  local ax="$1"
  local ay="$2"
  local aw="$3"
  local ah="$4"
  local bx="$5"
  local by="$6"
  local bw="$7"
  local bh="$8"

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

  geometry="$(get_window_geometry "$window_id")" || return 1
  extents="$(get_frame_extents "$window_id")"
  outer="$(get_outer_geometry "$window_id")" || return 1

  read -r map_state client_x client_y client_w client_h <<<"$geometry"
  read -r left right top bottom <<<"$extents"
  read -r outer_x outer_y outer_w outer_h <<<"$outer"

  corrected_client_x=$(( client_x + (target_outer_x - outer_x) ))
  corrected_client_y=$(( client_y + (target_outer_y - outer_y) ))
  debug "move $window_id target_outer=(${target_outer_x},${target_outer_y}) client=(${corrected_client_x},${corrected_client_y})"
  run_xdotool windowmove "$window_id" "$corrected_client_x" "$corrected_client_y"
  sleep "$XDO_SETTLE_DELAY"
}

resize_window_to_outer_size() {
  local window_id="$1"
  local target_outer_w="$2"
  local target_outer_h="$3"
  local extents
  local left right top bottom
  local requested_w requested_h
  local outer
  local outer_x outer_y actual_outer_w actual_outer_h
  local iteration delta_w delta_h

  extents="$(get_frame_extents "$window_id")"
  read -r left right top bottom <<<"$extents"

  requested_w=$(( target_outer_w - left - right ))
  requested_h=$(( target_outer_h - top - bottom ))
  (( requested_w < 50 )) && requested_w=50
  (( requested_h < 50 )) && requested_h=50

  for iteration in 1 2 3 4 5 6; do
    debug "resize $window_id iter=$iteration request_client=${requested_w}x${requested_h} target_outer=${target_outer_w}x${target_outer_h}"
    run_xdotool windowsize "$window_id" "$requested_w" "$requested_h"
    sleep "$XDO_SETTLE_DELAY"
    outer="$(get_outer_geometry "$window_id")" || return 1
    read -r outer_x outer_y actual_outer_w actual_outer_h <<<"$outer"
    debug "resize $window_id iter=$iteration actual_outer=${actual_outer_w}x${actual_outer_h}"

    delta_w=$(( target_outer_w - actual_outer_w ))
    delta_h=$(( target_outer_h - actual_outer_h ))

    if (( delta_w == 0 && delta_h == 0 )); then
      return 0
    fi

    requested_w=$(( requested_w + delta_w ))
    requested_h=$(( requested_h + delta_h ))
    (( requested_w < 50 )) && requested_w=50
    (( requested_h < 50 )) && requested_h=50
  done

  return 0
}

tile_windows() {
  local area_x="$1"
  local area_y="$2"
  local area_w="$3"
  local area_h="$4"
  shift 4
  local -a windows=( "$@" )
  local count="${#windows[@]}"
  local i window_id
  local current_x remaining_w remaining_count target_outer_w
  local outer
  local outer_x outer_y outer_w outer_h

  current_x="$area_x"
  remaining_w="$area_w"

  for (( i=0; i<count; i++ )); do
    window_id="${windows[$i]}"
    remaining_count=$(( count - i ))
    target_outer_w=$(( remaining_w / remaining_count ))

    if (( i == count - 1 )); then
      target_outer_w="$remaining_w"
    fi

    if (( DRY_RUN == 1 )); then
      log "DRY-RUN window=$window_id x=$current_x y=$area_y w=$target_outer_w h=$area_h title=$(get_window_title "$window_id")"
      current_x=$(( current_x + target_outer_w ))
      remaining_w=$(( area_x + area_w - current_x ))
      continue
    fi

    prepare_window "$window_id"
    resize_window_to_outer_size "$window_id" "$target_outer_w" "$area_h"
    move_window_outer "$window_id" "$current_x" "$area_y"

    outer="$(get_outer_geometry "$window_id")" || return 1
    read -r outer_x outer_y outer_w outer_h <<<"$outer"
    debug "placed $window_id outer=(${outer_x},${outer_y},${outer_w},${outer_h})"

    current_x=$(( outer_x + outer_w ))
    remaining_w=$(( area_x + area_w - current_x ))
    if (( remaining_w < 0 )); then
      remaining_w=0
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
        die "$EXIT_ENV" "unknown argument: $1"
        ;;
    esac
    shift
  done
}

main() {
  local session_type="${XDG_SESSION_TYPE:-}"
  local active_window_id
  local current_desktop
  local target_monitor
  local monitor_name monitor_x monitor_y monitor_w monitor_h
  local workarea
  local intersected_area
  local area_x area_y area_w area_h
  local stack_window_id
  local -a selected_windows=()
  local -A seen=()
  local title

  parse_args "$@"
  require_cmd xdotool xprop xwininfo xrandr

  if [[ -z "${DISPLAY:-}" ]]; then
    die "$EXIT_ENV" "DISPLAY is not set; this command must run inside an X11 session"
  fi

  if [[ "$session_type" == "wayland" ]]; then
    die "$EXIT_ENV" "Wayland is not supported; log in with Ubuntu on X11"
  fi

  xprop -root _NET_ACTIVE_WINDOW >/dev/null 2>&1 || die "$EXIT_ENV" "cannot access X11 display ${DISPLAY}"

  active_window_id="$(get_active_window_id)" || die "$EXIT_ENV" "could not determine the active window"
  current_desktop="$(get_current_desktop)"
  [[ -n "$current_desktop" ]] || die "$EXIT_ENV" "could not determine the current desktop"

  target_monitor="$(pick_target_monitor "$active_window_id")" || die "$EXIT_ENV" "could not map the active window to a monitor"
  read -r monitor_name monitor_x monitor_y monitor_w monitor_h <<<"$target_monitor"

  workarea="$(get_workarea_rect)" || die "$EXIT_ENV" "could not read the desktop work area"
  intersected_area="$(intersect_rects "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h" $workarea)" || \
    die "$EXIT_ENV" "monitor $monitor_name has no usable work area"
  read -r area_x area_y area_w area_h <<<"$intersected_area"

  if window_is_candidate "$active_window_id" "$current_desktop" "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h"; then
    selected_windows+=("$active_window_id")
    seen["$active_window_id"]=1
  else
    die "$EXIT_NO_WINDOWS" "the active window is not a supported top-level window"
  fi

  while read -r stack_window_id; do
    [[ -n "$stack_window_id" ]] || continue
    [[ -z "${seen[$stack_window_id]:-}" ]] || continue
    if window_is_candidate "$stack_window_id" "$current_desktop" "$monitor_x" "$monitor_y" "$monitor_w" "$monitor_h"; then
      selected_windows+=("$stack_window_id")
      seen["$stack_window_id"]=1
    fi
    if (( ${#selected_windows[@]} == 3 )); then
      break
    fi
  done < <(get_stacking_order || true)

  (( ${#selected_windows[@]} > 0 )) || die "$EXIT_NO_WINDOWS" "no windows matched the current monitor"

  if ! tile_windows "$area_x" "$area_y" "$area_w" "$area_h" "${selected_windows[@]}"; then
    die "$EXIT_MOVE_FAILED" "window move or resize failed"
  fi

  log "Tiled ${#selected_windows[@]} window(s) on ${monitor_name}"
  for stack_window_id in "${selected_windows[@]}"; do
    title="$(get_window_title "$stack_window_id")"
    log " - [$stack_window_id] $title"
  done
}

main "$@"
