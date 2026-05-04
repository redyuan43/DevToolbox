#!/usr/bin/env python3
"""Web dashboard for gpu-memory-guard.service across local and SSH hosts."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HOSTS = [
    {"id": "spark", "label": "spark", "ssh": None, "kind": "GB10 unified"},
    {"id": "edge", "label": "edge", "ssh": "edge", "kind": "GB10 unified"},
    {"id": "amd", "label": "AMD", "ssh": "AMD", "kind": "AMD unified"},
    {"id": "ivan", "label": "ivan", "ssh": "ivan", "kind": "2x RTX 3060 12G"},
]
SERVICE = "gpu-memory-guard.service"
DEFAULT_PORT = int(os.environ.get("GPU_GUARD_DASHBOARD_PORT", "8765"))
COMMAND_TIMEOUT = float(os.environ.get("GPU_GUARD_DASHBOARD_TIMEOUT", "8"))


@dataclass
class CommandResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int | None
    elapsed_ms: int


def run_command(command: str, ssh: str | None = None, timeout: float = COMMAND_TIMEOUT) -> CommandResult:
    if ssh:
        args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", ssh, command]
    else:
        args = ["bash", "-lc", command]
    started = time.monotonic()
    try:
        completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return CommandResult(
            ok=completed.returncode == 0,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            returncode=completed.returncode,
            elapsed_ms=elapsed_ms,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return CommandResult(
            ok=False,
            stdout=(exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            stderr=f"timeout after {timeout}s",
            returncode=None,
            elapsed_ms=elapsed_ms,
        )


def q(text: str) -> str:
    return shlex.quote(text)


def parse_key_value_lines(output: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def parse_latest_sample(journal: str) -> dict[str, object]:
    latest = ""
    for line in journal.splitlines():
        if " sample " in line:
            latest = line
    data: dict[str, object] = {"raw": latest}
    if not latest:
        return data

    for key in ("mem_used", "gpu_used", "processes", "threshold", "reason", "devices"):
        match = re.search(rf"{key}=([^ ]+(?: [^=]+?)?)(?= \w+=|$)", latest)
        if match:
            data[key] = match.group(1).strip()

    mem_match = re.search(r"mem_used=(\d+)MiB/(\d+)MiB", latest)
    if mem_match:
        used = int(mem_match.group(1))
        total = int(mem_match.group(2))
        data["mem_used_mib"] = used
        data["mem_total_mib"] = total
        data["mem_percent"] = round(used / total * 100, 1) if total else None

    gpu_match = re.search(r"gpu_used=(\d+)MiB", latest)
    if gpu_match:
        data["gpu_used_mib"] = int(gpu_match.group(1))

    threshold_match = re.search(r"threshold=(\d+)MiB", latest)
    if threshold_match:
        data["threshold_mib"] = int(threshold_match.group(1))

    device_text = str(data.get("devices", ""))
    devices = []
    for item in device_text.split(";"):
        match = re.match(r"(.+):(\d+)/(\d+)MiB", item)
        if not match:
            continue
        used = int(match.group(2))
        total = int(match.group(3))
        devices.append(
            {
                "label": match.group(1),
                "used_mib": used,
                "total_mib": total,
                "percent": round(used / total * 100, 1) if total else None,
            }
        )
    data["device_list"] = devices
    return data


def parse_events(journal: str) -> dict[str, object]:
    lines = [line for line in journal.splitlines() if line.strip()]
    kill_words = ("victim ", "SIGTERM", "SIGKILL", "threshold reached")
    protected_words = ("skip protected",)
    kills = [line for line in lines if any(word in line for word in kill_words)]
    protected = [line for line in lines if any(word in line for word in protected_words)]
    return {
        "kill_count": len(kills),
        "protected_count": len(protected),
        "recent_kills": kills[-8:],
        "recent_protected": protected[-8:],
    }


def collect_host(host: dict[str, str | None]) -> dict[str, object]:
    ssh = host["ssh"]
    command = f"""
set -o pipefail
echo __HOSTNAME__=$(hostname)
echo __ACTIVE__=$(systemctl is-active {q(SERVICE)} 2>/dev/null || true)
echo __ENABLED__=$(systemctl is-enabled {q(SERVICE)} 2>/dev/null || true)
systemctl show {q(SERVICE)} -p ActiveEnterTimestamp -p ExecMainStartTimestamp -p MainPID -p NRestarts -p SubState -p ActiveState --no-page 2>/dev/null | sed 's/^/__SHOW__/'
echo __CONFIG_START__
sed -n '1,120p' /etc/default/gpu-memory-guard 2>/dev/null || true
echo __CONFIG_END__
echo __FREE_START__
free -h 2>/dev/null || true
echo __FREE_END__
echo __NVIDIA_START__
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || true
echo __NVIDIA_END__
echo __ROCM_START__
rocm-smi --showmeminfo all --json 2>/dev/null || true
echo __ROCM_END__
echo __JOURNAL_START__
journalctl -u {q(SERVICE)} --since '24 hours ago' -n 240 --no-pager 2>/dev/null || true
echo __JOURNAL_END__
"""
    result = run_command(command, ssh=ssh)
    output = result.stdout

    def section(name: str) -> str:
        start = f"__{name}_START__"
        end = f"__{name}_END__"
        if start not in output or end not in output:
            return ""
        return output.split(start, 1)[1].split(end, 1)[0].strip()

    simple: dict[str, str] = {}
    show_lines = []
    for line in output.splitlines():
        if line.startswith("__HOSTNAME__="):
            simple["hostname"] = line.split("=", 1)[1]
        elif line.startswith("__ACTIVE__="):
            simple["active"] = line.split("=", 1)[1]
        elif line.startswith("__ENABLED__="):
            simple["enabled"] = line.split("=", 1)[1]
        elif line.startswith("__SHOW__"):
            show_lines.append(line.removeprefix("__SHOW__"))

    show = parse_key_value_lines("\n".join(show_lines))
    journal = section("JOURNAL")
    latest = parse_latest_sample(journal)
    events = parse_events(journal)
    config = section("CONFIG")
    config_map = {}
    for line in config.splitlines():
        if line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config_map[key.strip()] = value.strip()

    health = "ok"
    active = simple.get("active", "unknown")
    enabled = simple.get("enabled", "unknown")
    if not result.ok and not output:
        health = "unreachable"
    elif active != "active":
        health = "down"
    elif events["kill_count"]:
        health = "protected"
    elif latest.get("reason") and latest.get("reason") != "below threshold":
        health = "warning"

    return {
        "id": host["id"],
        "label": host["label"],
        "kind": host["kind"],
        "ssh": ssh,
        "health": health,
        "command": {
            "ok": result.ok,
            "stderr": result.stderr[-500:],
            "returncode": result.returncode,
            "elapsed_ms": result.elapsed_ms,
        },
        "hostname": simple.get("hostname", ""),
        "active": active,
        "enabled": enabled,
        "show": show,
        "config": config_map,
        "free": section("FREE"),
        "nvidia": section("NVIDIA"),
        "rocm": section("ROCM"),
        "latest": latest,
        "events": events,
    }


def collect_all() -> dict[str, object]:
    started = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=len(HOSTS)) as pool:
        futures = [pool.submit(collect_host, host) for host in HOSTS]
        for future in as_completed(futures):
            results.append(future.result())
    order = {host["id"]: index for index, host in enumerate(HOSTS)}
    results.sort(key=lambda item: order.get(str(item["id"]), 999))
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "hosts": results,
    }


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GPU Memory Guard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101214;
      --panel: #181b1f;
      --panel-2: #20242a;
      --text: #f2f5f7;
      --muted: #9ca7b2;
      --line: #343a42;
      --ok: #2ed47a;
      --warn: #f7c948;
      --bad: #ff5c6c;
      --info: #58a6ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: #14171a;
      position: sticky;
      top: 0;
      z-index: 3;
    }
    h1 { margin: 0; font-size: 22px; font-weight: 700; }
    .sub { color: var(--muted); font-size: 13px; margin-top: 4px; }
    button {
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--text);
      height: 36px;
      padding: 0 12px;
      border-radius: 6px;
      cursor: pointer;
    }
    main { padding: 20px 24px 28px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(230px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-width: 0;
    }
    .card-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .name { font-size: 18px; font-weight: 700; }
    .kind { color: var(--muted); font-size: 12px; margin-top: 2px; }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      white-space: nowrap;
    }
    .ok { color: var(--ok); border-color: rgba(46,212,122,.45); }
    .warn { color: var(--warn); border-color: rgba(247,201,72,.45); }
    .bad { color: var(--bad); border-color: rgba(255,92,108,.45); }
    .metric { margin: 10px 0; }
    .metric-row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .bar {
      height: 9px;
      background: #0e1012;
      border: 1px solid #2c3238;
      border-radius: 999px;
      overflow: hidden;
    }
    .fill { height: 100%; background: var(--info); width: 0; }
    .fill.warn { background: var(--warn); }
    .fill.bad { background: var(--bad); }
    .facts {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 12px;
    }
    .fact { background: var(--panel-2); border-radius: 6px; padding: 8px; min-width: 0; }
    .fact span { display: block; color: var(--muted); font-size: 11px; }
    .fact b { display: block; font-size: 13px; margin-top: 3px; overflow-wrap: anywhere; }
    section { margin-top: 18px; }
    h2 { font-size: 16px; margin: 0 0 10px; }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      color: #d8dee9;
      font-size: 12px;
      line-height: 1.45;
      max-height: 260px;
      overflow: auto;
    }
    .events {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    .empty { color: var(--muted); font-size: 13px; }
    @media (max-width: 1200px) { .grid { grid-template-columns: repeat(2, minmax(230px, 1fr)); } }
    @media (max-width: 640px) {
      header { align-items: flex-start; flex-direction: column; padding: 16px; }
      main { padding: 14px; }
      .grid, .events { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>GPU Memory Guard</h1>
      <div class="sub" id="summary">加载中</div>
    </div>
    <button id="refresh">刷新</button>
  </header>
  <main>
    <div class="grid" id="hosts"></div>
    <section>
      <h2>处理记录</h2>
      <div class="events" id="events"></div>
    </section>
  </main>
<script>
const fmtMiB = (mib) => {
  if (mib === undefined || mib === null) return "n/a";
  return `${(mib / 1024).toFixed(1)} GiB`;
};
const cls = (p) => p >= 90 ? "bad" : p >= 75 ? "warn" : "";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function statusClass(host) {
  if (host.health === "ok") return "ok";
  if (host.health === "protected" || host.health === "warning") return "warn";
  return "bad";
}
function bar(label, used, total, percent) {
  const p = percent ?? (total ? Math.round(used / total * 1000) / 10 : 0);
  return `<div class="metric">
    <div class="metric-row"><span>${esc(label)}</span><b>${esc(fmtMiB(used))} / ${esc(fmtMiB(total))} · ${esc(p ?? "n/a")}%</b></div>
    <div class="bar"><div class="fill ${cls(p || 0)}" style="width:${Math.min(100, p || 0)}%"></div></div>
  </div>`;
}
function renderHost(host) {
  const latest = host.latest || {};
  const devices = latest.device_list || [];
  const memBar = latest.mem_total_mib ? bar("系统内存", latest.mem_used_mib, latest.mem_total_mib, latest.mem_percent) : "";
  const deviceBars = devices.map(d => bar(d.label, d.used_mib, d.total_mib, d.percent)).join("");
  const gpuFallback = !deviceBars && latest.gpu_used_mib ? `<div class="metric-row"><span>GPU 进程占用</span><b>${fmtMiB(latest.gpu_used_mib)}</b></div>` : "";
  return `<article class="card">
    <div class="card-head">
      <div><div class="name">${esc(host.label)}</div><div class="kind">${esc(host.kind)} · ${esc(host.hostname)}</div></div>
      <div class="pill ${statusClass(host)}">${esc(host.active)} / ${esc(host.enabled)}</div>
    </div>
    ${memBar}${deviceBars}${gpuFallback}
    <div class="facts">
      <div class="fact"><span>阈值</span><b>${esc(latest.threshold || "n/a")}</b></div>
      <div class="fact"><span>最近原因</span><b>${esc(latest.reason || "n/a")}</b></div>
      <div class="fact"><span>主进程</span><b>${esc(host.show?.MainPID || "n/a")}</b></div>
      <div class="fact"><span>启动时间</span><b>${esc(host.show?.ExecMainStartTimestamp || host.show?.ActiveEnterTimestamp || "n/a")}</b></div>
      <div class="fact"><span>保护次数</span><b>${esc(host.events?.protected_count ?? 0)}</b></div>
      <div class="fact"><span>处理次数</span><b>${esc(host.events?.kill_count ?? 0)}</b></div>
    </div>
  </article>`;
}
function renderEvents(hosts) {
  return hosts.map(host => {
    const kills = host.events?.recent_kills || [];
    const protectedLines = host.events?.recent_protected || [];
    return `<div class="card">
      <h2>${esc(host.label)}</h2>
      <div class="metric-row"><span>最近处理</span><b>${kills.length}</b></div>
      ${kills.length ? `<pre>${esc(kills.join("\n"))}</pre>` : `<div class="empty">最近 24 小时没有处理记录</div>`}
      <div class="metric-row" style="margin-top:12px"><span>最近白名单保护</span><b>${protectedLines.length}</b></div>
      ${protectedLines.length ? `<pre>${esc(protectedLines.join("\n"))}</pre>` : `<div class="empty">最近 24 小时没有白名单保护记录</div>`}
    </div>`;
  }).join("");
}
async function load() {
  document.getElementById("summary").textContent = "刷新中";
  const res = await fetch("/api/status", {cache: "no-store"});
  const data = await res.json();
  document.getElementById("summary").textContent = `更新时间 ${data.generated_at} · 拉取耗时 ${data.elapsed_ms}ms`;
  document.getElementById("hosts").innerHTML = data.hosts.map(renderHost).join("");
  document.getElementById("events").innerHTML = renderEvents(data.hosts);
}
document.getElementById("refresh").addEventListener("click", load);
load();
setInterval(load, 15000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            raw = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self.send_text(HTML, "text/html; charset=utf-8")
            return
        if path == "/api/status":
            self.send_json(collect_all())
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {self.address_string()} {fmt % args}", flush=True)

    def send_text(self, body: str, content_type: str) -> None:
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_json(self, data: object) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> int:
    host = os.environ.get("GPU_GUARD_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("GPU_GUARD_DASHBOARD_PORT", str(DEFAULT_PORT)))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"GPU Memory Guard dashboard: http://{host}:{port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
