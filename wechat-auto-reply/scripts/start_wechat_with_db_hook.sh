#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${STATE_DIR:-$HOME/.local/state/wechat-auto-reply}"
HOOK_SRC="$REPO_ROOT/native/wechat_db_hook.c"
HOOK_SO="${HOOK_SO:-$STATE_DIR/libwechat_db_hook.so}"
HOOK_LOG="${HOOK_LOG:-$STATE_DIR/db_hook.jsonl}"
WECHAT_BIN="${WECHAT_BIN:-/usr/bin/wechat}"
WECHAT_APP_EX="${WECHAT_APP_EX:-/opt/wechat/RadiumWMPF/runtime/WeChatAppEx}"
WECHAT_APP_EX_REAL="${WECHAT_APP_EX_REAL:-/opt/wechat/RadiumWMPF/runtime/WeChatAppEx.real}"
DISPLAY_VALUE="${DISPLAY_VALUE:-${DISPLAY:-:1}}"
XAUTHORITY_VALUE="${XAUTHORITY_VALUE:-${XAUTHORITY:-/run/user/$(id -u)/gdm/Xauthority}}"

mkdir -p "$STATE_DIR"

if [[ ! -x "$WECHAT_BIN" ]]; then
  echo "wechat binary not found: $WECHAT_BIN" >&2
  exit 1
fi

if [[ ! -f "$HOOK_SO" || "$HOOK_SRC" -nt "$HOOK_SO" ]]; then
  gcc -shared -fPIC -O2 -o "$HOOK_SO" "$HOOK_SRC" -ldl -lpthread
fi

if [[ ! -e "$WECHAT_APP_EX_REAL" ]]; then
  sudo mv "$WECHAT_APP_EX" "$WECHAT_APP_EX_REAL"
fi

WRAPPER="$(mktemp)"
cat >"$WRAPPER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
HOOK_SO="\${HOOK_SO:-$HOOK_SO}"
HOOK_LOG="\${WECHAT_DB_HOOK_LOG:-$HOOK_LOG}"
exec /lib/ld-linux-aarch64.so.1 --preload "\$HOOK_SO" "$WECHAT_APP_EX_REAL" "\$@"
EOF
sudo install -m 0755 "$WRAPPER" "$WECHAT_APP_EX"
rm -f "$WRAPPER"

pkill -x wechat >/dev/null 2>&1 || true
sleep 1

touch "$HOOK_LOG"
systemctl --user stop wechat-db-hook-app.service >/dev/null 2>&1 || true
systemd-run --user \
  --unit wechat-db-hook-app.service \
  --property=WorkingDirectory="$HOME" \
  --setenv=DISPLAY="$DISPLAY_VALUE" \
  --setenv=XAUTHORITY="$XAUTHORITY_VALUE" \
  --setenv=LD_PRELOAD="$HOOK_SO" \
  --setenv=WECHAT_DB_HOOK_LOG="$HOOK_LOG" \
  "$WECHAT_BIN" >/tmp/wechat-db-hook.log 2>&1

echo "wechat started with db hook"
echo "hook library: $HOOK_SO"
echo "hook log: $HOOK_LOG"
