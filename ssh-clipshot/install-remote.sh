#!/usr/bin/env bash
set -euo pipefail

die() {
  printf 'install-remote: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  ./install-remote.sh SSH_HOST [--bashrc]

Install clipshot-pull and the Bash keybinding helper to a remote SSH host.
With --bashrc, append a guarded source block to ~/.bashrc on the remote host.
EOF
}

[ "$#" -ge 1 ] || { usage; exit 1; }
host=$1
shift
edit_bashrc=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --bashrc)
      edit_bashrc=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ssh "$host" 'mkdir -p "$HOME/.local/bin" "$HOME/.config/clipshot"'
scp -q "$repo_dir/bin/clipshot-pull" "$host:~/.local/bin/clipshot-pull"
scp -q "$repo_dir/shell/clipshot.bash" "$host:~/.config/clipshot/clipshot.bash"
ssh "$host" 'chmod 0755 "$HOME/.local/bin/clipshot-pull"'

if [ "$edit_bashrc" -eq 1 ]; then
  ssh "$host" 'grep -q ">>> clipshot >>>" "$HOME/.bashrc" 2>/dev/null || cat >> "$HOME/.bashrc" <<'"'"'REMOTE_EOF'"'"'

# >>> clipshot >>>
if [ -f "$HOME/.config/clipshot/clipshot.bash" ]; then
  . "$HOME/.config/clipshot/clipshot.bash"
fi
# <<< clipshot <<<
REMOTE_EOF'
fi

printf 'installed remote clipshot tools on %s\n' "$host"
if [ "$edit_bashrc" -eq 1 ]; then
  printf 'enabled Bash binding on %s: Ctrl+x Ctrl+s\n' "$host"
else
  printf 'to enable the binding on %s, run: source ~/.config/clipshot/clipshot.bash\n' "$host"
fi
