#!/usr/bin/env bash

set -euo pipefail

readonly BASE_SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
readonly CUSTOM_SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
readonly STATE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/split6"
readonly DEFAULT_OUTPUT="${STATE_DIR}/hotkeys_backup.txt"

usage() {
  cat <<'EOF'
Usage: export_split6_hotkeys.sh [output_file]

Export the current split6-related GNOME hotkeys and terminal binding.
If no output_file is provided, the backup is written to:
  ~/.cache/split6/hotkeys_backup.txt
EOF
}

main() {
  local output_file="${1:-$DEFAULT_OUTPUT}"
  local custom_paths path

  case "${1:-}" in
    --help|-h)
      usage
      exit 0
      ;;
  esac

  mkdir -p "$STATE_DIR"

  {
    printf '# split6 hotkey backup\n'
    printf '# generated_at=%s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')"
    printf '\n'

    printf '[terminal]\n'
    printf 'schema=%s\n' "$BASE_SCHEMA"
    printf 'key=terminal\n'
    printf 'value=%s\n' "$(gsettings get "$BASE_SCHEMA" terminal)"
    printf '\n'

    printf '[custom-keybindings]\n'
    printf 'schema=%s\n' "$BASE_SCHEMA"
    printf 'key=custom-keybindings\n'
    custom_paths="$(gsettings get "$BASE_SCHEMA" custom-keybindings)"
    printf 'value=%s\n' "$custom_paths"
    printf '\n'

    while read -r path; do
      [[ -n "$path" ]] || continue
      printf '[%s]\n' "$path"
      printf 'name=%s\n' "$(gsettings get "$CUSTOM_SCHEMA:$path" name 2>/dev/null || true)"
      printf 'command=%s\n' "$(gsettings get "$CUSTOM_SCHEMA:$path" command 2>/dev/null || true)"
      printf 'binding=%s\n' "$(gsettings get "$CUSTOM_SCHEMA:$path" binding 2>/dev/null || true)"
      printf '\n'
    done < <(printf '%s\n' "$custom_paths" | grep -oE '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom[0-9]+/' || true)
  } >"$output_file"

  printf 'Exported split6 hotkeys to %s\n' "$output_file"
}

main "$@"
