#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

host="${GPU_GUARD_DASHBOARD_HOST:-127.0.0.1}"
port="${GPU_GUARD_DASHBOARD_PORT:-8765}"

echo "GPU Memory Guard dashboard: http://${host}:${port}"
exec python3 app.py
