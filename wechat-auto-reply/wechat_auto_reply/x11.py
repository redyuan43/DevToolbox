from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Iterable

from .config import Roi, WindowConfig


WINDOW_RE = re.compile(
    r"^\s*(0x[0-9a-f]+)\s+\"(?P<title>[^\"]*)\":\s+\(\"(?P<class1>[^\"]*)\"\s+\"(?P<class2>[^\"]*)\"\)\s+"
    r"(?P<width>\d+)x(?P<height>\d+)\+(?P<rel_x>-?\d+)\+(?P<rel_y>-?\d+)"
    r"(?:\s+\+(?P<abs_x>-?\d+)\+(?P<abs_y>-?\d+))?"
)


@dataclass(slots=True)
class WindowInfo:
    window_id: str
    title: str
    class_name: str
    x: int
    y: int
    width: int
    height: int

    @property
    def geometry(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


def x11_env(window: WindowConfig) -> dict[str, str]:
    env = dict(os.environ)
    env["DISPLAY"] = window.display
    if window.xauthority:
        env["XAUTHORITY"] = window.xauthority
    return env


def _run(command: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
    return result.stdout.strip()


def parse_windows(output: str, class_name: str | None = None) -> list[WindowInfo]:
    matches: list[WindowInfo] = []
    for line in output.splitlines():
        raw = WINDOW_RE.match(line)
        if not raw:
            continue
        current_class_name = raw.group("class1") or raw.group("class2")
        title = raw.group("title")
        if class_name and current_class_name != class_name:
            continue
        matches.append(
            WindowInfo(
                window_id=raw.group(1),
                title=title,
                class_name=current_class_name,
                x=int(raw.group("abs_x") or raw.group("rel_x")),
                y=int(raw.group("abs_y") or raw.group("rel_y")),
                width=int(raw.group("width")),
                height=int(raw.group("height")),
            )
        )
    return matches


def parse_wechat_windows(output: str, class_name: str) -> list[WindowInfo]:
    return parse_windows(output, class_name=class_name)


def list_windows(window: WindowConfig, class_name: str | None = None) -> list[WindowInfo]:
    env = x11_env(window)
    output = _run(["xwininfo", "-root", "-tree"], env)
    matches = parse_windows(output, class_name)
    return sorted(matches, key=lambda item: item.width * item.height, reverse=True)


def list_wechat_windows(window: WindowConfig) -> list[WindowInfo]:
    return list_windows(window, class_name=window.class_name)


def _dedupe_by_title(windows: Iterable[WindowInfo]) -> list[WindowInfo]:
    deduped: dict[str, WindowInfo] = {}
    for window in sorted(windows, key=lambda item: item.width * item.height, reverse=True):
        deduped.setdefault(window.title, window)
    return sorted(deduped.values(), key=lambda item: (item.title.lower(), -item.width * item.height))


def discover_wechat_window(window: WindowConfig) -> WindowInfo | None:
    title_re = re.compile(window.title_regex)
    matches = [item for item in list_wechat_windows(window) if item.title and title_re.search(item.title)]
    if not matches:
        return None
    return sorted(matches, key=lambda item: item.width * item.height, reverse=True)[0]


def discover_standalone_windows(window: WindowConfig, whitelist: list[str]) -> list[WindowInfo]:
    whitelist_set = {item.strip() for item in whitelist if item.strip()}
    main_title_re = re.compile(window.main_title_regex)
    matches = [
        item
        for item in list_wechat_windows(window)
        if item.title
        and not main_title_re.search(item.title)
        and (not whitelist_set or item.title in whitelist_set)
    ]
    return _dedupe_by_title(matches)


def activate_window(window_id: str, window: WindowConfig) -> None:
    env = x11_env(window)
    subprocess.run(["xdotool", "windowactivate", "--sync", window_id], check=True, env=env)


def click(x: int, y: int, window: WindowConfig, button: int = 1) -> None:
    env = x11_env(window)
    subprocess.run(
        ["xdotool", "mousemove", "--sync", str(x), str(y), "click", str(button)],
        check=True,
        env=env,
    )


def right_click(x: int, y: int, window: WindowConfig) -> None:
    click(x, y, window, button=3)


def key(keyspec: str, window: WindowConfig) -> None:
    env = x11_env(window)
    subprocess.run(["xdotool", "key", "--clearmodifiers", keyspec], check=True, env=env)


def paste_text(text: str, window: WindowConfig) -> None:
    env = x11_env(window)
    clipboard_command = ["xsel", "--clipboard", "--input"]
    if shutil.which("xsel") is None:
        if shutil.which("xclip") is None:
            raise RuntimeError("clipboard_tool_not_found")
        clipboard_command = ["xclip", "-selection", "clipboard"]
    subprocess.run(clipboard_command, check=True, text=True, input=text, env=env)
    subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=True, env=env)


def paste_and_send(text: str, window: WindowConfig) -> None:
    paste_text(text, window)
    key("Return", window)


def active_window_id(window: WindowConfig) -> str | None:
    env = x11_env(window)
    try:
        return _run(["xdotool", "getactivewindow"], env)
    except subprocess.CalledProcessError:
        return None


def scroll_page(x: int, y: int, direction: str, window: WindowConfig, clicks: int = 8) -> None:
    button = 4 if direction == "up" else 5
    for _ in range(max(1, clicks)):
        click(x, y, window, button=button)


def derive_default_rois(info: WindowInfo) -> dict[str, Roi]:
    chat_width = max(220, int(info.width * 0.28))
    input_height = max(150, int(info.height * 0.18))
    header_height = max(70, int(info.height * 0.1))
    return {
        "chat_list": Roi(
            x=info.x,
            y=info.y + header_height,
            width=chat_width,
            height=max(200, info.height - header_height),
        ),
        "conversation": Roi(
            x=info.x + chat_width,
            y=info.y + header_height,
            width=max(300, info.width - chat_width),
            height=max(250, info.height - header_height - input_height),
        ),
        "input": Roi(
            x=info.x + chat_width,
            y=info.y + info.height - input_height,
            width=max(300, info.width - chat_width),
            height=input_height,
        ),
    }


def derive_standalone_rois(info: WindowInfo) -> dict[str, Roi]:
    header_height = max(70, int(info.height * 0.12))
    input_height = max(150, int(info.height * 0.22))
    conversation_height = max(220, info.height - header_height - input_height)
    return {
        "header": Roi(
            x=info.x,
            y=info.y,
            width=info.width,
            height=header_height,
        ),
        "conversation": Roi(
            x=info.x,
            y=info.y + header_height,
            width=info.width,
            height=conversation_height,
        ),
        "input": Roi(
            x=info.x,
            y=info.y + info.height - input_height,
            width=info.width,
            height=input_height,
        ),
    }


class UserInputMonitor:
    def __init__(self, window: WindowConfig) -> None:
        self.window = window
        self.last_user_event_monotonic = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._xtest_ids = self._discover_xtest_ids()

    def _discover_xtest_ids(self) -> set[str]:
        env = x11_env(self.window)
        try:
            output = _run(["xinput", "list"], env)
        except subprocess.CalledProcessError:
            return set()
        ids = set()
        for line in output.splitlines():
            if "XTEST" in line:
                match = re.search(r"id=(\d+)", line)
                if match:
                    ids.add(match.group(1))
        return ids

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def ms_since_user_input(self) -> float:
        if self.last_user_event_monotonic == 0:
            return float("inf")
        return max(0.0, (time.monotonic() - self.last_user_event_monotonic) * 1000.0)

    def _run(self) -> None:
        env = x11_env(self.window)
        process = subprocess.Popen(
            ["xinput", "test-xi2", "--root"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        assert process.stdout is not None
        current_device: str | None = None
        try:
            for line in process.stdout:
                if self._stop.is_set():
                    break
                line = line.strip()
                if line.startswith("device:"):
                    match = re.search(r"device:\s+\d+\s+\((\d+)\)", line)
                    current_device = match.group(1) if match else None
                if line.startswith("EVENT type") and current_device and current_device not in self._xtest_ids:
                    self.last_user_event_monotonic = time.monotonic()
        finally:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
