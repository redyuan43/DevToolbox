#!/usr/bin/env bash

set -euo pipefail

readonly BASE_SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
readonly CUSTOM_SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SPLIT_SCRIPT="${REPO_DIR}/split.sh"

declare -a EXISTING_PATHS

collect_existing_paths() {
  local raw
  raw="$(gsettings get "$BASE_SCHEMA" custom-keybindings)"
  mapfile -t EXISTING_PATHS < <(
    printf '%s\n' "$raw" |
      grep -oE '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom[0-9]+/' || true
  )
}

get_binding_name() {
  local path="$1"
  gsettings get "$CUSTOM_SCHEMA:$path" name 2>/dev/null | sed -n "s/^'\\(.*\\)'$/\\1/p" || true
}

get_binding_command() {
  local path="$1"
  gsettings get "$CUSTOM_SCHEMA:$path" command 2>/dev/null | sed -n "s/^'\\(.*\\)'$/\\1/p" || true
}

find_existing_path_by_name() {
  local target_name="$1"
  local path
  for path in "${EXISTING_PATHS[@]:-}"; do
    if [[ "$(get_binding_name "$path")" == "$target_name" ]]; then
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
    [[ "$existing" == "$path" ]] && return 0
  done
  EXISTING_PATHS+=( "$path" )
}

remove_path_from_list() {
  local remove_path="$1"
  local path
  local -a kept=()
  for path in "${EXISTING_PATHS[@]:-}"; do
    [[ "$path" == "$remove_path" ]] && continue
    kept+=( "$path" )
  done
  EXISTING_PATHS=( "${kept[@]}" )
}

reset_binding_path() {
  local path="$1"
  gsettings reset "$CUSTOM_SCHEMA:$path" name >/dev/null 2>&1 || true
  gsettings reset "$CUSTOM_SCHEMA:$path" command >/dev/null 2>&1 || true
  gsettings reset "$CUSTOM_SCHEMA:$path" binding >/dev/null 2>&1 || true
  remove_path_from_list "$path"
}

is_managed_split_binding() {
  local path="$1"
  local name command
  name="$(get_binding_name "$path")"
  command="$(get_binding_command "$path")"

  [[ "$name" =~ ^Split(3|4|6|8|16|43)( |$) ]] && return 0
  [[ "$command" == "${REPO_DIR}/split3.sh"* ]] && return 0
  [[ "$command" == "${REPO_DIR}/split4.sh"* ]] && return 0
  [[ "$command" == "${REPO_DIR}/split6.sh"* ]] && return 0
  [[ "$command" == "${REPO_DIR}/split8.sh"* ]] && return 0
  [[ "$command" == "${REPO_DIR}/split16.sh"* ]] && return 0
  [[ "$command" == "${REPO_DIR}/split.sh"* ]] && return 0
  [[ "$command" == "${REPO_DIR}/launch_ptyxis_split.sh"* ]] && return 0
  [[ "$command" == "${REPO_DIR}/focus_split6_slot.sh"* ]] && return 0
  return 1
}

prune_old_split_bindings() {
  local path
  local -a paths_snapshot=( "${EXISTING_PATHS[@]:-}" )
  for path in "${paths_snapshot[@]}"; do
    if is_managed_split_binding "$path"; then
      reset_binding_path "$path"
    fi
  done
}

set_custom_binding() {
  local name="$1"
  local command="$2"
  local binding="$3"
  local path

  path="$(find_existing_path_by_name "$name" || true)"
  [[ -n "$path" ]] || path="$(next_free_path)"

  gsettings set "$CUSTOM_SCHEMA:$path" name "$name"
  gsettings set "$CUSTOM_SCHEMA:$path" command "$command"
  gsettings set "$CUSTOM_SCHEMA:$path" binding "$binding"
  append_path_if_missing "$path"
}

write_path_list() {
  local value="["
  local idx
  for idx in "${!EXISTING_PATHS[@]}"; do
    (( idx > 0 )) && value+=", "
    value+="'${EXISTING_PATHS[$idx]}'"
  done
  value+="]"
  gsettings set "$BASE_SCHEMA" custom-keybindings "$value"
}

print_summary() {
  local path
  printf 'Configured split hotkeys:\n'
  for path in "${EXISTING_PATHS[@]}"; do
    if is_managed_split_binding "$path"; then
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
  prune_old_split_bindings

  set_custom_binding "Split 3" "$SPLIT_SCRIPT --num 3" "<Control><Alt>3"
  set_custom_binding "Split 4" "$SPLIT_SCRIPT --num 4" "<Control><Alt>4"
  set_custom_binding "Split 8" "$SPLIT_SCRIPT --num 8" "<Control><Alt>8"
  set_custom_binding "Split 16" "$SPLIT_SCRIPT --num 16" "<Control><Alt><Shift>8"

  write_path_list
  print_summary
}

main "$@"
