# shellcheck shell=bash

clipshot_pull() {
  command clipshot-pull "$@"
}

clipshot_upload_from_source() {
  local source_target source_command ssh_opts extra_ssh_opts
  source_target=${CLIPSHOT_SOURCE:-"ivan@ivan-tm1613.taild500c8.ts.net"}
  source_command=${CLIPSHOT_UPLOAD_COMMAND:-"~/.local/bin/clipshot-upload"}
  ssh_opts=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=8)
  if [[ -n ${CLIPSHOT_SSH_OPTS:-} ]]; then
    # shellcheck disable=SC2206
    extra_ssh_opts=(${CLIPSHOT_SSH_OPTS})
    ssh_opts+=("${extra_ssh_opts[@]}")
  fi
  ssh "${ssh_opts[@]}" "$source_target" "$source_command" >/dev/null
}

clipshot_sync() {
  clipshot_upload_from_source && clipshot_pull "$@"
}

clipshot_insert() {
  local path
  if ! path=$(clipshot_sync); then
    return 1
  fi
  printf '\nclipshot: %s\n' "$path" >&2

  if [[ -n ${READLINE_LINE+x} ]]; then
    READLINE_LINE="${READLINE_LINE:0:READLINE_POINT}${path}${READLINE_LINE:READLINE_POINT}"
    READLINE_POINT=$((READLINE_POINT + ${#path}))
  else
    printf '%s\n' "$path"
  fi
}

if [[ $- == *i* ]]; then
  stty -ixon 2>/dev/null || true
  bind -x '"\C-x\C-s": clipshot_insert'
  bind -x '"\C-x\C-v": clipshot_insert'
  bind -x '"\C-xv": clipshot_insert'
  bind -x '"\e[24~": clipshot_insert'
fi
