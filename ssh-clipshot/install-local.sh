#!/usr/bin/env bash
set -euo pipefail

die() {
  printf 'install-local: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  ./install-local.sh [--shortcut]

Install clipshot-upload to ~/.local/bin.
With --shortcut, also register Super+Ctrl+V as a GNOME custom shortcut.
EOF
}

install_shortcut=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --shortcut)
      install_shortcut=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
target_dir="$HOME/.local/bin"
mkdir -p "$target_dir"
install -m 0755 "$repo_dir/bin/clipshot-upload" "$target_dir/clipshot-upload"
install -m 0755 "$repo_dir/bin/clipshot-send" "$target_dir/clipshot-send"

if [ "$install_shortcut" -eq 1 ]; then
  command -v gsettings >/dev/null 2>&1 || die "gsettings is required for --shortcut"
  key_path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/clipshot-upload/"
  current=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)
  case "$current" in
    *"$key_path"*)
      new="$current"
      ;;
    "@as []")
      new="['$key_path']"
      ;;
    \[*\])
      new="${current%]}, '$key_path']"
      ;;
    *)
      die "unexpected custom-keybindings value: $current"
      ;;
  esac

  if [ "$new" != "$current" ]; then
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$new"
  fi
  gsettings set "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$key_path" name "Clipshot Send"
  gsettings set "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$key_path" command "$target_dir/clipshot-send --paste nx1"
  gsettings set "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$key_path" binding "<Super><Control>v"
fi

printf 'installed %s/clipshot-upload\n' "$target_dir"
printf 'installed %s/clipshot-send\n' "$target_dir"
if [ "$install_shortcut" -eq 1 ]; then
  printf 'registered GNOME shortcut: Super+Ctrl+V\n'
fi
