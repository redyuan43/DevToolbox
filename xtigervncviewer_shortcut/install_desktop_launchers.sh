#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}/desktop"
TARGET_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
INSTALL_DIR="${XTIGERVNCVIEWER_SHORTCUT_DIR:-${SCRIPT_DIR}}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "missing launcher source dir: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g'
}

INSTALL_DIR_ESCAPED="$(escape_sed_replacement "$INSTALL_DIR")"

for src in "$SOURCE_DIR"/*.desktop; do
  dest="${TARGET_DIR}/$(basename "$src")"
  sed "s|__INSTALL_DIR__|${INSTALL_DIR_ESCAPED}|g" "$src" > "$dest"
  chmod 755 "$dest"
  gio set "$dest" metadata::trusted true >/dev/null 2>&1 || true
  echo "installed: $dest"
done
