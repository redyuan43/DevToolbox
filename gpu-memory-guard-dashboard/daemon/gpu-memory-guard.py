#!/usr/bin/env python3
"""Guard unified-memory GPU machines from runaway GPU processes."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROTECTED_NAMES = {
    "Xorg",
    "Xwayland",
    "gnome-shell",
    "gdm",
    "gdm3",
    "kwin_x11",
    "kwin_wayland",
    "plasmashell",
    "v2rayN",
    "gpu-memory-guard.py",
}
GPU_FD_MARKERS = (
    "/dev/nvidia",
    "/dev/dri/render",
    "/dev/kfd",
)


@dataclass(frozen=True)
class MemInfo:
    total_mib: int
    available_mib: int

    @property
    def used_mib(self) -> int:
        return max(0, self.total_mib - self.available_mib)


@dataclass
class GpuProcess:
    pid: int
    name: str
    used_mib: int
    source: str
    command: str = ""


@dataclass
class GpuDeviceMemory:
    label: str
    used_mib: int
    total_mib: int
    source: str


@dataclass
class Sample:
    meminfo: MemInfo
    processes: list[GpuProcess]
    gpu_used_mib: int
    devices: list[GpuDeviceMemory]
    details: list[str]


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", flush=True)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def read_meminfo(path: str = "/proc/meminfo") -> MemInfo:
    values: dict[str, int] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            key, raw_value = line.split(":", 1)
            values[key] = int(raw_value.strip().split()[0]) // 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    if total <= 0:
        raise RuntimeError("MemTotal is unavailable")
    return MemInfo(total_mib=total, available_mib=available)


def run_command(args: list[str], timeout: float = 2.0) -> str | None:
    try:
        return subprocess.check_output(args, text=True, timeout=timeout, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def process_name(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def process_command(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").strip()
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def process_rss_mib(pid: int) -> int:
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return 0
    return 0


def parse_nvidia_smi_processes(output: str) -> list[GpuProcess]:
    processes: list[GpuProcess] = []
    pattern = re.compile(r"^\s*\|?\s*\d+\s+\S+\s+\S+\s+(\d+)\s+\S+\s+(.+?)\s+(\d+)MiB\s*\|?\s*$")
    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        pid = int(match.group(1))
        name = Path(match.group(2).strip()).name or process_name(pid) or match.group(2).strip()
        used_mib = int(match.group(3))
        processes.append(
            GpuProcess(
                pid=pid,
                name=name,
                used_mib=used_mib,
                source="nvidia-smi",
                command=process_command(pid),
            )
        )
    return processes


def read_nvidia_processes() -> list[GpuProcess]:
    output = run_command(["nvidia-smi"])
    if not output:
        return []
    return parse_nvidia_smi_processes(output)


def parse_nvidia_gpu_memory(output: str) -> list[GpuDeviceMemory]:
    devices: list[GpuDeviceMemory] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        index, name, total, used = parts[:4]
        total_mib = _as_int(total)
        used_mib = _as_int(used)
        if total_mib is None or used_mib is None or total_mib <= 0:
            continue
        devices.append(
            GpuDeviceMemory(
                label=f"nvidia:{index}:{name}",
                used_mib=used_mib,
                total_mib=total_mib,
                source="nvidia-smi",
            )
        )
    return devices


def read_nvidia_gpu_memory() -> list[GpuDeviceMemory]:
    output = run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used",
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return []
    return parse_nvidia_gpu_memory(output)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
        if not match:
            return None
        number = float(match.group(1))
        lowered = cleaned.lower()
        if "gib" in lowered or "gb" in lowered:
            return int(number * 1024)
        if "mib" in lowered or "mb" in lowered:
            return int(number)
        if "kib" in lowered or "kb" in lowered:
            return int(number / 1024)
        if "byte" in lowered or lowered.endswith(" b"):
            return int(number / 1024 / 1024)
        return int(number)
    return None


def _find_key(data: dict[str, object], fragments: tuple[str, ...]) -> object | None:
    for key, value in data.items():
        normalized = key.lower().replace("_", " ").replace("-", " ")
        if all(fragment in normalized for fragment in fragments):
            return value
    return None


def _iter_dicts(data: object):
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from _iter_dicts(value)
    elif isinstance(data, list):
        for value in data:
            yield from _iter_dicts(value)


def parse_amd_smi_processes(output: str) -> list[GpuProcess]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    processes: dict[int, GpuProcess] = {}
    for item in _iter_dicts(data):
        pid_value = _find_key(item, ("pid",))
        pid = _as_int(pid_value)
        if pid is None or pid <= 0:
            continue

        name_value = (
            _find_key(item, ("process", "name"))
            or _find_key(item, ("name",))
            or process_name(pid)
            or str(pid)
        )
        memory_value = (
            _find_key(item, ("memory", "usage"))
            or _find_key(item, ("mem", "usage"))
            or _find_key(item, ("vram", "usage"))
            or _find_key(item, ("memory",))
        )
        used_mib = _as_int(memory_value) or process_rss_mib(pid)
        current = processes.get(pid)
        if current is None or used_mib > current.used_mib:
            processes[pid] = GpuProcess(
                pid=pid,
                name=Path(str(name_value)).name,
                used_mib=used_mib,
                source="amd-smi",
                command=process_command(pid),
            )
    return list(processes.values())


def read_amd_processes() -> list[GpuProcess]:
    output = run_command(["amd-smi", "process", "--general", "--json"])
    if not output:
        return []
    return parse_amd_smi_processes(output)


def read_amd_sysfs_memory_mib(base: str = "/sys/class/drm") -> int:
    return sum(device.used_mib for device in read_amd_sysfs_gpu_memory(base))


def read_amd_sysfs_gpu_memory(base: str = "/sys/class/drm") -> list[GpuDeviceMemory]:
    devices: list[GpuDeviceMemory] = []
    for card_dir in sorted(Path(base).glob("card*/device")):
        used = 0
        total = 0
        for memory_name in ("mem_info_vram", "mem_info_gtt"):
            used_path = card_dir / f"{memory_name}_used"
            total_path = card_dir / f"{memory_name}_total"
            if not used_path.exists() or not total_path.exists():
                continue
            try:
                used += int(used_path.read_text(encoding="utf-8").strip()) // 1024 // 1024
                total += int(total_path.read_text(encoding="utf-8").strip()) // 1024 // 1024
            except (OSError, ValueError):
                continue
        if total > 0:
            devices.append(
                GpuDeviceMemory(
                    label=f"amd:{card_dir.parent.name}",
                    used_mib=used,
                    total_mib=total,
                    source="amdgpu-sysfs",
                )
            )
    return devices


def parse_rocm_smi_gpu_memory(output: str) -> list[GpuDeviceMemory]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    devices: list[GpuDeviceMemory] = []
    for label, values in data.items() if isinstance(data, dict) else []:
        if not isinstance(values, dict):
            continue
        used = 0
        total = 0
        for key, value in values.items():
            lowered = key.lower()
            parsed = _as_int(value)
            if parsed is None:
                continue
            if "(b)" in lowered or "bytes" in lowered:
                parsed = parsed // 1024 // 1024
            if "used memory" in lowered:
                used += parsed
            elif "total memory" in lowered:
                total += parsed
        if total > 0:
            devices.append(GpuDeviceMemory(label=f"rocm:{label}", used_mib=used, total_mib=total, source="rocm-smi"))
    return devices


def read_rocm_smi_gpu_memory() -> list[GpuDeviceMemory]:
    output = run_command(["rocm-smi", "--showmeminfo", "all", "--json"])
    if not output:
        return []
    return parse_rocm_smi_gpu_memory(output)


def read_rocm_smi_memory_mib() -> int:
    devices = read_rocm_smi_gpu_memory()
    if devices:
        return sum(device.used_mib for device in devices)
    output = run_command(["rocm-smi", "--showmeminfo", "all", "--json"])
    if not output:
        return 0
    return parse_rocm_smi_memory_mib(output)


def parse_rocm_smi_memory_mib(output: str) -> int:
    devices = parse_rocm_smi_gpu_memory(output)
    if devices:
        return sum(device.used_mib for device in devices)

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return 0

    total = 0
    for item in _iter_dicts(data):
        for key, value in item.items():
            lowered = key.lower()
            if "used memory" not in lowered:
                continue
            parsed = _as_int(value)
            if parsed is not None:
                if "(b)" in lowered or "bytes" in lowered:
                    parsed = parsed // 1024 // 1024
                total += parsed
    return total


def read_gpu_fd_processes() -> list[GpuProcess]:
    processes: dict[int, GpuProcess] = {}
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        pid = int(proc_dir.name)
        fd_dir = proc_dir / "fd"
        try:
            fd_paths = list(fd_dir.iterdir())
        except OSError:
            continue
        matched = False
        for fd_path in fd_paths:
            try:
                target = os.readlink(fd_path)
            except OSError:
                continue
            if any(marker in target for marker in GPU_FD_MARKERS):
                matched = True
                break
        if matched:
            processes[pid] = GpuProcess(
                pid=pid,
                name=process_name(pid) or str(pid),
                used_mib=process_rss_mib(pid),
                source="proc-fd-rss",
                command=process_command(pid),
            )
    return list(processes.values())


def merge_processes(groups: list[list[GpuProcess]]) -> list[GpuProcess]:
    merged: dict[int, GpuProcess] = {}
    source_rank = {"nvidia-smi": 3, "amd-smi": 3, "proc-fd-rss": 1}
    for group in groups:
        for proc in group:
            current = merged.get(proc.pid)
            if current is None:
                merged[proc.pid] = proc
                continue
            if proc.used_mib > current.used_mib or source_rank.get(proc.source, 0) > source_rank.get(current.source, 0):
                if not proc.command:
                    proc.command = current.command
                merged[proc.pid] = proc
    return sorted(merged.values(), key=lambda item: item.used_mib, reverse=True)


def collect_sample() -> Sample:
    meminfo = read_meminfo()
    nvidia_processes = read_nvidia_processes()
    amd_processes = read_amd_processes()
    fd_processes = read_gpu_fd_processes()
    processes = merge_processes([nvidia_processes, amd_processes, fd_processes])
    devices = read_nvidia_gpu_memory() + read_amd_sysfs_gpu_memory()
    if not devices:
        devices = read_rocm_smi_gpu_memory()

    nvidia_used = sum(proc.used_mib for proc in nvidia_processes)
    amd_global_used = sum(device.used_mib for device in devices if device.source in {"amdgpu-sysfs", "rocm-smi"})
    gpu_used_mib = max(nvidia_used, amd_global_used, sum(proc.used_mib for proc in processes))
    details = [
        f"mem_used={meminfo.used_mib}MiB/{meminfo.total_mib}MiB",
        f"gpu_used={gpu_used_mib}MiB",
        f"processes={len(processes)}",
    ]
    if nvidia_processes:
        details.append(f"nvidia_processes={len(nvidia_processes)}")
    if amd_processes:
        details.append(f"amd_processes={len(amd_processes)}")
    if amd_global_used:
        details.append(f"amd_global_used={amd_global_used}MiB")
    if devices:
        details.append(
            "devices="
            + ";".join(f"{device.label}:{device.used_mib}/{device.total_mib}MiB" for device in devices)
        )
    return Sample(meminfo=meminfo, processes=processes, gpu_used_mib=gpu_used_mib, devices=devices, details=details)


def protected_names_from_env() -> set[str]:
    raw = os.environ.get("GPU_GUARD_PROTECTED_NAMES", "")
    names = {item.strip() for item in raw.split(",") if item.strip()}
    return DEFAULT_PROTECTED_NAMES | names


def is_protected(proc: GpuProcess, protected_names: set[str]) -> bool:
    names = {proc.name, Path(proc.name).name, process_name(proc.pid)}
    command = proc.command or process_command(proc.pid)
    if any(name in protected_names for name in names if name):
        return True
    return any(f"/{name}" in command or command.startswith(name) for name in protected_names)


def choose_victim(processes: list[GpuProcess], protected_names: set[str]) -> GpuProcess | None:
    for proc in sorted(processes, key=lambda item: item.used_mib, reverse=True):
        if proc.pid == os.getpid():
            continue
        if is_protected(proc, protected_names):
            log(f"skip protected pid={proc.pid} name={proc.name} used={proc.used_mib}MiB source={proc.source}")
            continue
        return proc
    return None


def terminate_process(proc: GpuProcess, grace_seconds: int, dry_run: bool) -> None:
    command = proc.command or process_command(proc.pid)
    log(
        "victim "
        f"pid={proc.pid} name={proc.name} used={proc.used_mib}MiB source={proc.source} "
        f"dry_run={int(dry_run)} cmd={command}"
    )
    if dry_run:
        return
    try:
        os.kill(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        log(f"pid={proc.pid} already exited before SIGTERM")
        return
    except PermissionError as exc:
        log(f"failed to SIGTERM pid={proc.pid}: {exc}")
        return

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not Path(f"/proc/{proc.pid}").exists():
            log(f"pid={proc.pid} exited after SIGTERM")
            return
        time.sleep(0.5)

    try:
        os.kill(proc.pid, signal.SIGKILL)
        log(f"sent SIGKILL pid={proc.pid}")
    except ProcessLookupError:
        log(f"pid={proc.pid} exited before SIGKILL")
    except PermissionError as exc:
        log(f"failed to SIGKILL pid={proc.pid}: {exc}")


def should_trigger(sample: Sample, threshold_mib: int, threshold_percent: float = 90) -> tuple[bool, str]:
    for device in sample.devices:
        device_threshold_mib = int(device.total_mib * threshold_percent / 100)
        if device.used_mib >= device_threshold_mib:
            return (
                True,
                f"{device.label} used {device.used_mib}MiB >= device threshold {device_threshold_mib}MiB",
            )
    if sample.gpu_used_mib >= threshold_mib:
        return True, f"gpu_used {sample.gpu_used_mib}MiB >= threshold {threshold_mib}MiB"
    if sample.meminfo.used_mib >= threshold_mib and sample.processes:
        return True, f"mem_used {sample.meminfo.used_mib}MiB >= threshold {threshold_mib}MiB"
    return False, "below threshold"


def main() -> int:
    parser = argparse.ArgumentParser(description="Kill runaway GPU processes on unified-memory machines.")
    parser.add_argument("--once", action="store_true", help="sample once and exit")
    args = parser.parse_args()

    threshold_percent = float(os.environ.get("GPU_GUARD_THRESHOLD_PERCENT", "90"))
    interval_seconds = max(1, int(os.environ.get("GPU_GUARD_INTERVAL_SECONDS", "2")))
    grace_seconds = max(1, int(os.environ.get("GPU_GUARD_GRACE_SECONDS", "10")))
    dry_run = env_bool("GPU_GUARD_DRY_RUN", False)
    protected_names = protected_names_from_env()

    while True:
        try:
            sample = collect_sample()
            threshold_mib = int(sample.meminfo.total_mib * threshold_percent / 100)
            trigger, reason = should_trigger(sample, threshold_mib, threshold_percent=threshold_percent)
            log("sample " + " ".join(sample.details) + f" threshold={threshold_mib}MiB reason={reason}")
            if trigger:
                victim = choose_victim(sample.processes, protected_names)
                if victim is None:
                    log("threshold reached but no killable GPU process was found")
                else:
                    terminate_process(victim, grace_seconds=grace_seconds, dry_run=dry_run)
        except Exception as exc:
            log(f"guard error: {type(exc).__name__}: {exc}")

        if args.once:
            return 0
        time.sleep(interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
