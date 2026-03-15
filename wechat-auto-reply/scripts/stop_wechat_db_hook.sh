#!/usr/bin/env bash
set -euo pipefail

WECHAT_APP_EX="${WECHAT_APP_EX:-/opt/wechat/RadiumWMPF/runtime/WeChatAppEx}"
WECHAT_APP_EX_REAL="${WECHAT_APP_EX_REAL:-/opt/wechat/RadiumWMPF/runtime/WeChatAppEx.real}"

systemctl --user stop wechat-db-hook-app.service >/dev/null 2>&1 || true
pkill -x wechat >/dev/null 2>&1 || true
sleep 1

if [[ -e "$WECHAT_APP_EX_REAL" ]]; then
  sudo rm -f "$WECHAT_APP_EX"
  sudo mv "$WECHAT_APP_EX_REAL" "$WECHAT_APP_EX"
fi

echo "wechat db hook stopped"
