#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="xtigervncviewer_shortcut"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/${APP_NAME}"
STATE_FILE="${XTIGERVNCVIEWER_STATE_FILE:-${CONFIG_DIR}/last-target.conf}"
VIEWER_BIN="${XTIGERVNCVIEWER_BIN:-xtigervncviewer}"
DEFAULT_HOST="${XTIGERVNCVIEWER_DEFAULT_HOST:-192.168.100.137}"
DEFAULT_DISPLAY="${XTIGERVNCVIEWER_DEFAULT_DISPLAY:-2}"

usage() {
  cat <<'EOF'
Usage:
  xtigervncviewer_shortcut.sh [HOST DISPLAY]
  xtigervncviewer_shortcut.sh [HOST:DISPLAY]
  xtigervncviewer_shortcut.sh --host HOST --display DISPLAY
  xtigervncviewer_shortcut.sh --target HOST:DISPLAY
  xtigervncviewer_shortcut.sh [--no-save] [--help]

When no arguments are provided, the script prompts for host/IP and display.
It prefers zenity when available and falls back to terminal prompts.
EOF
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

prompt_value() {
  local prompt="$1"
  local default_value="${2:-}"

  if command -v zenity >/dev/null 2>&1 && { [[ -n "${DISPLAY:-}" ]] || [[ -n "${WAYLAND_DISPLAY:-}" ]]; }; then
    if [[ -n "$default_value" ]]; then
      zenity --entry \
        --title="TigerVNC Viewer" \
        --text="$prompt" \
        --entry-text="$default_value"
    else
      zenity --entry \
        --title="TigerVNC Viewer" \
        --text="$prompt"
    fi
    return
  fi

  if [[ ! -t 0 ]]; then
    echo "No prompt backend available. Install zenity or run in a terminal." >&2
    return 1
  fi

  local input=""
  if [[ -n "$default_value" ]]; then
    read -r -p "${prompt} [${default_value}]: " input
    printf '%s\n' "${input:-$default_value}"
  else
    read -r -p "${prompt}: " input
    printf '%s\n' "$input"
  fi
}

load_last_target() {
  LAST_VNC_HOST="$DEFAULT_HOST"
  LAST_VNC_DISPLAY="$DEFAULT_DISPLAY"

  if [[ ! -r "$STATE_FILE" ]]; then
    return
  fi

  while IFS='=' read -r key value; do
    case "$key" in
      LAST_VNC_HOST)
        LAST_VNC_HOST="${value:-$LAST_VNC_HOST}"
        ;;
      LAST_VNC_DISPLAY)
        LAST_VNC_DISPLAY="${value:-$LAST_VNC_DISPLAY}"
        ;;
    esac
  done <"$STATE_FILE"
}

save_last_target() {
  mkdir -p "$CONFIG_DIR"
  {
    printf 'LAST_VNC_HOST=%s\n' "$HOST"
    printf 'LAST_VNC_DISPLAY=%s\n' "$DISPLAY_VALUE"
  } >"$STATE_FILE"
  chmod 600 "$STATE_FILE" 2>/dev/null || true
}

split_target() {
  local target="$1"
  local host="${target%:*}"
  local display="${target##*:}"

  if [[ "$host" == "$target" || ! "$display" =~ ^[0-9]+$ ]]; then
    return 1
  fi

  HOST="$host"
  DISPLAY_VALUE="$display"
  return 0
}

TARGET=""
HOST=""
DISPLAY_VALUE=""
NO_SAVE=0
POSITIONAL=()

while (($#)); do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --no-save)
      NO_SAVE=1
      shift
      ;;
    --target)
      if (($# < 2)); then
        echo "Missing value for --target" >&2
        exit 2
      fi
      TARGET="$2"
      shift 2
      ;;
    --host)
      if (($# < 2)); then
        echo "Missing value for --host" >&2
        exit 2
      fi
      HOST="$2"
      shift 2
      ;;
    --display)
      if (($# < 2)); then
        echo "Missing value for --display" >&2
        exit 2
      fi
      DISPLAY_VALUE="$2"
      shift 2
      ;;
    --)
      shift
      POSITIONAL+=("$@")
      break
      ;;
    --*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

if [[ -n "$TARGET" && ( -n "$HOST" || -n "$DISPLAY_VALUE" || ${#POSITIONAL[@]} -gt 0 ) ]]; then
  echo "Do not mix --target with host/display arguments." >&2
  exit 2
fi

if (( ${#POSITIONAL[@]} > 2 )); then
  echo "Too many positional arguments." >&2
  usage >&2
  exit 2
fi

if (( ${#POSITIONAL[@]} == 1 )); then
  if [[ "${POSITIONAL[0]}" == *:* ]]; then
    TARGET="${POSITIONAL[0]}"
  else
    HOST="${POSITIONAL[0]}"
  fi
elif (( ${#POSITIONAL[@]} == 2 )); then
  HOST="${POSITIONAL[0]}"
  DISPLAY_VALUE="${POSITIONAL[1]}"
fi

if ! command -v "$VIEWER_BIN" >/dev/null 2>&1; then
  echo "Cannot find viewer binary: $VIEWER_BIN" >&2
  echo "Set XTIGERVNCVIEWER_BIN or install TigerVNC Viewer." >&2
  exit 1
fi

if [[ -n "$TARGET" ]]; then
  if split_target "$TARGET"; then
    :
  fi
else
  load_last_target
  HOST="$(trim "${HOST:-$LAST_VNC_HOST}")"
  DISPLAY_VALUE="$(trim "${DISPLAY_VALUE:-$LAST_VNC_DISPLAY}")"

  HOST="$(prompt_value "请输入 VNC 服务器 IP 或主机名" "$HOST")" || exit 0
  DISPLAY_VALUE="$(prompt_value "请输入显示号，例如 2" "$DISPLAY_VALUE")" || exit 0
  HOST="$(trim "$HOST")"
  DISPLAY_VALUE="$(trim "$DISPLAY_VALUE")"
  TARGET="${HOST}:${DISPLAY_VALUE}"
fi

TARGET="$(trim "$TARGET")"

if [[ -z "$TARGET" ]]; then
  echo "Empty target." >&2
  exit 1
fi

if [[ -z "$HOST" || -z "$DISPLAY_VALUE" ]]; then
  if ! split_target "$TARGET"; then
    echo "Invalid target format. Expected HOST:DISPLAY." >&2
    exit 1
  fi
fi

if [[ -z "$HOST" || ! "$DISPLAY_VALUE" =~ ^[0-9]+$ ]]; then
  echo "Invalid host or display value." >&2
  exit 1
fi

if (( NO_SAVE == 0 )); then
  save_last_target
fi

exec "$VIEWER_BIN" "${HOST}:${DISPLAY_VALUE}"
