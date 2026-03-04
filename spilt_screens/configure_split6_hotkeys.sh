#!/usr/bin/env bash

set -euo pipefail

readonly BASE_SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
readonly CUSTOM_SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
readonly MEDIA_KEYS_SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
readonly REPO_DIR="/home/dgx/github/DevToolbox/spilt_screens"
readonly SPLIT6_SCRIPT="${REPO_DIR}/split6.sh"
readonly FOCUS_SCRIPT="${REPO_DIR}/focus_split6_slot.sh"

declare -a EXISTING_PATHS

collect_existing_paths() {
  local raw
  raw="$(gsettings get "$BASE_SCHEMA" custom-keybindings)"
  mapfile -t EXISTING_PATHS < <(
    printf '%s\n' "$raw" |
      grep -oE '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom[0-9]+/' || true
  )
}

find_existing_path_by_command() {
  local target_command="$1"
  local path command
  for path in "${EXISTING_PATHS[@]:-}"; do
    command="$(gsettings get "$CUSTOM_SCHEMA:$path" command 2>/dev/null | sed -n "s/^'\\(.*\\)'$/\\1/p" || true)"
    if [[ "$command" == "$target_command" ]]; then
      printf '%s\n' "$path"
      return 0
    fi
  done
  return 1
}

next_free_path() {
  local idx=0
  local path joined
  joined=" ${EXISTING_PATHS[*]:-} "
  while :; do
    path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom${idx}/"
    if [[ "$joined" != *" $path "* ]]; then
      printf '%s\n' "$path"
      return 0
    fi
    idx=$((idx + 1))
  done
}

append_path_if_missing() {
  local path="$1"
  local existing
  for existing in "${EXISTING_PATHS[@]:-}"; do
    if [[ "$existing" == "$path" ]]; then
      return 0
    fi
  done
  EXISTING_PATHS+=( "$path" )
}

set_custom_binding() {
  local path="$1"
  local name="$2"
  local command="$3"
  local binding="$4"

  gsettings set "$CUSTOM_SCHEMA:$path" name "$name"
  gsettings set "$CUSTOM_SCHEMA:$path" command "$command"
  gsettings set "$CUSTOM_SCHEMA:$path" binding "$binding"
  append_path_if_missing "$path"
}

ensure_binding() {
  local name="$1"
  local command="$2"
  local binding="$3"
  local path

  path="$(find_existing_path_by_command "$command" || true)"
  if [[ -z "$path" ]]; then
    path="$(next_free_path)"
  fi

  set_custom_binding "$path" "$name" "$command" "$binding"
}

write_path_list() {
  local value="["
  local idx
  for idx in "${!EXISTING_PATHS[@]}"; do
    if (( idx > 0 )); then
      value+=", "
    fi
    value+="'${EXISTING_PATHS[$idx]}'"
  done
  value+="]"
  gsettings set "$BASE_SCHEMA" custom-keybindings "$value"
}

configure_focus_binding() {
  local slot="$1"
  local name="$2"
  local binding="$3"
  local path command

  command="${FOCUS_SCRIPT} ${slot}"
  path="$(find_existing_path_by_command "$command" || true)"
  if [[ -z "$path" ]]; then
    path="$(next_free_path)"
  fi

  set_custom_binding "$path" "$name" "$command" "$binding"
}

print_summary() {
  local path
  printf 'Configured split6 hotkeys:\n'
  for path in "${EXISTING_PATHS[@]}"; do
    if gsettings get "$CUSTOM_SCHEMA:$path" name >/dev/null 2>&1; then
      printf '%s\n' "$path"
      printf '  name=%s\n' "$(gsettings get "$CUSTOM_SCHEMA:$path" name)"
      printf '  command=%s\n' "$(gsettings get "$CUSTOM_SCHEMA:$path" command)"
      printf '  binding=%s\n' "$(gsettings get "$CUSTOM_SCHEMA:$path" binding)"
    fi
  done
}

main() {
  command -v gsettings >/dev/null 2>&1 || { echo "missing dependency: gsettings" >&2; exit 1; }

  collect_existing_paths

  # Free Ctrl+Alt+1 for slot focus and keep a terminal shortcut on a nearby key.
  gsettings set "$MEDIA_KEYS_SCHEMA" terminal "['<Control><Alt>7']"

  ensure_binding "Split6 Arrange" "$SPLIT6_SCRIPT" "<Control><Alt>0"
  ensure_binding "Split6 Daemon Start" "$SPLIT6_SCRIPT --daemon" "<Control><Alt><Shift>6"
  ensure_binding "Split6 Daemon Stop" "$SPLIT6_SCRIPT --stop" "<Control><Alt><Shift>5"

  configure_focus_binding 1 "Split6 Focus 1" "<Control><Alt>1"
  configure_focus_binding 2 "Split6 Focus 2" "<Control><Alt>2"
  configure_focus_binding 3 "Split6 Focus 3" "<Control><Alt>3"
  configure_focus_binding 4 "Split6 Focus 4" "<Control><Alt>4"
  configure_focus_binding 5 "Split6 Focus 5" "<Control><Alt>5"
  configure_focus_binding 6 "Split6 Focus 6" "<Control><Alt>6"

  write_path_list
  print_summary
}

main "$@"
