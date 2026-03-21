#!/usr/bin/env bash
set -euo pipefail

GPU_UUID="${1:-GPU-4c63c711-9570-75db-760d-c6679c760754}"
DROPIN_DIR="/etc/systemd/system/ollama.service.d"
DROPIN_FILE="${DROPIN_DIR}/10-gpu-selection.conf"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo --preserve-env=PATH bash "$0" "$@"
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found"
  exit 1
fi

if ! systemctl cat "ollama.service" >/dev/null 2>&1; then
  echo "ollama.service not found"
  exit 1
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  if ! nvidia-smi -L | grep -Fq "${GPU_UUID}"; then
    echo "GPU UUID not found: ${GPU_UUID}"
    exit 1
  fi
fi

mkdir -p "${DROPIN_DIR}"

cat > "${DROPIN_FILE}" <<EOF
[Service]
Environment="CUDA_VISIBLE_DEVICES=${GPU_UUID}"
EOF

systemctl daemon-reload
systemctl restart "ollama"

echo "Applied GPU pinning for ollama.service"
echo "CUDA_VISIBLE_DEVICES=${GPU_UUID}"
echo "Drop-in file: ${DROPIN_FILE}"
