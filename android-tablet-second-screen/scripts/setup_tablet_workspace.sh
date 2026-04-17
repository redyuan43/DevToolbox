#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vnc_dir="$HOME/.vnc"
mkdir -p "$vnc_dir"
secret_file="$repo_root/artifacts/tablet_workspace_secret.txt"

if [[ ! -f "$vnc_dir/passwd" || ! -f "$secret_file" ]]; then
  password="$(python3 - <<'PY'
import secrets, string
alphabet = string.ascii_letters + string.digits
print("VNC-" + "".join(secrets.choice(alphabet) for _ in range(12)))
PY
)"
  printf '%s\n%s\n\n' "$password" "$password" | tigervncpasswd "$vnc_dir/passwd" >/dev/null
  chmod 600 "$vnc_dir/passwd"
  printf 'tablet_workspace_vnc_password=%s\n' "$password" > "$secret_file"
  chmod 600 "$secret_file"
  echo "Created VNC password and saved it to artifacts/tablet_workspace_secret.txt"
else
  echo "Reusing existing $vnc_dir/passwd"
fi

cat > "$HOME/.config/systemd/user/tablet-workspace.service" <<EOF
[Unit]
Description=Independent TigerVNC workspace for Android tablet
After=graphical-session.target

[Service]
Type=forking
ExecStart=${repo_root}/scripts/start_tablet_workspace.sh
ExecStop=${repo_root}/scripts/stop_tablet_workspace.sh
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable tablet-workspace.service >/dev/null
echo "Installed user service: tablet-workspace.service"
