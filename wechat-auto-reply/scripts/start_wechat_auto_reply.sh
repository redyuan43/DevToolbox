#!/usr/bin/env bash
set -euo pipefail

systemctl --user start wechat-auto-reply.service
systemctl --user --no-pager --full status wechat-auto-reply.service
