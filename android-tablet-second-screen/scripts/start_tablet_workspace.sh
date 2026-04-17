#!/usr/bin/env bash
set -euo pipefail

display_num="${DISPLAY_NUM:-2}"
geometry="${GEOMETRY:-2960x1848}"
desktop_name="${DESKTOP_NAME:-Tablet Workspace}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/android-tablet-second-screen"
mkdir -p "$state_dir" "$HOME/.vnc"

xstartup="${state_dir}/xstartup-tablet-workspace.sh"
cat >"$xstartup" <<'EOF'
#!/usr/bin/env bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XDG_CURRENT_DESKTOP=XFCE
export XDG_SESSION_DESKTOP=xfce
export XDG_SESSION_TYPE=x11
export DESKTOP_SESSION=xfce
exec dbus-run-session startxfce4
EOF
chmod +x "$xstartup"

if [[ ! -f "$HOME/.vnc/passwd" ]]; then
  echo "Missing $HOME/.vnc/passwd. Run scripts/setup_tablet_workspace.sh first." >&2
  exit 1
fi

if tigervncserver -list 2>/dev/null | rg -q "^:${display_num}\\b"; then
  echo "TigerVNC display :${display_num} is already running."
  exit 0
fi

log_file="$HOME/.vnc/$(hostname):${display_num}.log"
echo "Starting TigerVNC desktop :${display_num} (${geometry})..."
exec tigervncserver \
  ":${display_num}" \
  -geometry "${geometry}" \
  -depth 24 \
  -desktop "${desktop_name}" \
  -localhost no \
  -SecurityTypes VncAuth \
  -xstartup "$xstartup"
