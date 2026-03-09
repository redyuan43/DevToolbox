#!/usr/bin/env bash
set -euo pipefail

MODEL_KEY="${MODEL_KEY:-qwen/qwen3.5-35b-a3b}"
MODEL_IDENTIFIER="${MODEL_IDENTIFIER:-qwen/qwen3.5-35b-a3b}"
SERVER_HOST="${SERVER_HOST:-127.0.0.1}"
SERVER_PORT="${SERVER_PORT:-1234}"
DISPLAY_VALUE="${DISPLAY_VALUE:-${DISPLAY:-:1}}"
XAUTHORITY_VALUE="${XAUTHORITY_VALUE:-${XAUTHORITY:-/run/user/$(id -u)/gdm/Xauthority}}"
LM_STUDIO_APPIMAGE="${LM_STUDIO_APPIMAGE:-/home/dgx/Downloads/LM-Studio-0.4.6-1-arm64.AppImage}"
LM_STUDIO_EXTRA_ARGS="${LM_STUDIO_EXTRA_ARGS:---no-sandbox}"
EXTRACT_ROOT="${EXTRACT_ROOT:-$HOME/.cache/lm-studio-appimage}"
EXTRACTED_DIR="${EXTRACTED_DIR:-$EXTRACT_ROOT/squashfs-root}"
SYSTEMD_UNIT_NAME="${SYSTEMD_UNIT_NAME:-lmstudio-app.service}"
LOAD_TTL_SECONDS="${LOAD_TTL_SECONDS:-0}"
LOAD_GPU_RATIO="${LOAD_GPU_RATIO:-max}"
LOAD_CONTEXT_LENGTH="${LOAD_CONTEXT_LENGTH:-}"
LOAD_PARALLEL="${LOAD_PARALLEL:-}"
WAIT_SECONDS="${WAIT_SECONDS:-90}"

log() {
  printf '[lm-studio-bootstrap] %s\n' "$*"
}

fail() {
  printf '[lm-studio-bootstrap] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

require_cmd curl
require_cmd lms
require_cmd systemctl
require_cmd systemd-run

health_url="http://${SERVER_HOST}:${SERVER_PORT}/v1/models"

server_ready() {
  curl -fsS --max-time 2 "$health_url" >/dev/null 2>&1
}

wait_for_server() {
  local deadline
  deadline=$((SECONDS + WAIT_SECONDS))
  while (( SECONDS < deadline )); do
    if server_ready; then
      return 0
    fi
    sleep 1
  done
  return 1
}

extract_app_if_needed() {
  if [[ ! -x "$LM_STUDIO_APPIMAGE" ]]; then
    fail "LM Studio AppImage not found or not executable: $LM_STUDIO_APPIMAGE"
  fi

  mkdir -p "$EXTRACT_ROOT"

  if [[ -x "$EXTRACTED_DIR/lm-studio" && "$EXTRACTED_DIR/lm-studio" -nt "$LM_STUDIO_APPIMAGE" ]]; then
    return 0
  fi

  log "Extracting LM Studio AppImage into $EXTRACT_ROOT"
  rm -rf "$EXTRACT_ROOT"
  mkdir -p "$EXTRACT_ROOT"
  (
    cd "$EXTRACT_ROOT"
    "$LM_STUDIO_APPIMAGE" --appimage-extract >/tmp/lm-studio-app-extract.log 2>&1
  ) || fail "failed to extract AppImage; see /tmp/lm-studio-app-extract.log"
  [[ -x "$EXTRACTED_DIR/lm-studio" ]] || fail "extracted LM Studio binary not found: $EXTRACTED_DIR/lm-studio"
}

start_app_if_needed() {
  if server_ready; then
    log "LM Studio server already responding on ${SERVER_HOST}:${SERVER_PORT}"
    return 0
  fi

  extract_app_if_needed

  if systemctl --user --quiet is-active "$SYSTEMD_UNIT_NAME"; then
    log "LM Studio app unit already active: $SYSTEMD_UNIT_NAME"
  else
    log "Starting LM Studio app via systemd --user: $SYSTEMD_UNIT_NAME"
    systemd-run --user \
      --unit "$SYSTEMD_UNIT_NAME" \
      --property=WorkingDirectory="$EXTRACTED_DIR" \
      --setenv=DISPLAY="$DISPLAY_VALUE" \
      --setenv=XAUTHORITY="$XAUTHORITY_VALUE" \
      "$EXTRACTED_DIR/lm-studio" $LM_STUDIO_EXTRA_ARGS >/tmp/lm-studio-app-launch.log 2>&1 \
      || fail "failed to launch LM Studio user service; see /tmp/lm-studio-app-launch.log"
  fi
}

ensure_server_started() {
  if server_ready; then
    return 0
  fi

  log "Starting LM Studio local server on ${SERVER_HOST}:${SERVER_PORT}"
  timeout 45s lms server start --bind "$SERVER_HOST" --port "$SERVER_PORT" \
    >/tmp/lm-studio-server-start.log 2>&1 || true
  wait_for_server || fail "LM Studio API server failed to start on ${SERVER_HOST}:${SERVER_PORT}"
}

ensure_model_loaded() {
  if lms ps 2>/dev/null | rg -F " ${MODEL_IDENTIFIER} " >/dev/null 2>&1; then
    log "Model already loaded: ${MODEL_IDENTIFIER}"
    return 0
  fi

  local load_args=("$MODEL_KEY" "--identifier" "$MODEL_IDENTIFIER" "--gpu" "$LOAD_GPU_RATIO" "-y")
  if [[ "$LOAD_TTL_SECONDS" != "0" ]]; then
    load_args+=("--ttl" "$LOAD_TTL_SECONDS")
  fi
  if [[ -n "$LOAD_CONTEXT_LENGTH" ]]; then
    load_args+=("-c" "$LOAD_CONTEXT_LENGTH")
  fi
  if [[ -n "$LOAD_PARALLEL" ]]; then
    load_args+=("--parallel" "$LOAD_PARALLEL")
  fi

  log "Loading model: ${MODEL_KEY}"
  lms load "${load_args[@]}" >/tmp/lm-studio-model-load.log 2>&1 || fail "failed to load model ${MODEL_KEY}"
}

verify_model_visible() {
  local response
  response="$(curl -fsS --max-time 5 "$health_url")" || fail "failed to query LM Studio models endpoint"
  printf '%s' "$response" | rg -F "\"id\": \"${MODEL_IDENTIFIER}\"" >/dev/null 2>&1 \
    || printf '%s' "$response" | rg -F "\"id\": \"${MODEL_KEY}\"" >/dev/null 2>&1 \
    || fail "model not visible from /v1/models: ${MODEL_IDENTIFIER}"
}

main() {
  start_app_if_needed
  ensure_server_started
  ensure_model_loaded
  verify_model_visible
  log "Ready: ${MODEL_IDENTIFIER} on http://${SERVER_HOST}:${SERVER_PORT}/v1"
}

main "$@"
