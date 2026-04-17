#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${script_dir}/adb_tablet_display_info.sh" || true
echo
"${script_dir}/sunshine_moonlight_status.sh" || true
echo
"${script_dir}/vkms_virtual_monitor_status.sh" || true
echo
"${script_dir}/tablet_workspace_status.sh" || true
