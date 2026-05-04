#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install_dir="/usr/local/lib/gpu-memory-guard"
config_file="/etc/default/gpu-memory-guard"
unit_file="/etc/systemd/system/gpu-memory-guard.service"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo --preserve-env=PATH bash "$0" "$@"
fi

install -d -m 0755 "${install_dir}"
install -m 0755 "${repo_dir}/scripts/gpu-memory-guard.py" "${install_dir}/gpu-memory-guard.py"

if [[ ! -f "${config_file}" ]]; then
  cat >"${config_file}" <<'EOF'
# Kill the largest non-protected GPU process when unified-memory pressure is too high.
GPU_GUARD_THRESHOLD_PERCENT=90
GPU_GUARD_INTERVAL_SECONDS=2
GPU_GUARD_GRACE_SECONDS=10
GPU_GUARD_DRY_RUN=0

# Comma-separated extra process names to protect.
# Built-in protected names include Xorg, Xwayland, gnome-shell, gdm, kwin, plasmashell, v2rayN.
GPU_GUARD_PROTECTED_NAMES=
EOF
fi

cat >"${unit_file}" <<EOF
[Unit]
Description=GPU unified-memory guard

[Service]
Type=simple
EnvironmentFile=-${config_file}
ExecStart=/usr/bin/python3 ${install_dir}/gpu-memory-guard.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gpu-memory-guard.service
systemctl restart gpu-memory-guard.service
systemctl is-active --quiet gpu-memory-guard.service

echo "Installed gpu-memory-guard.service"
echo "Logs: journalctl -u gpu-memory-guard.service -f"
