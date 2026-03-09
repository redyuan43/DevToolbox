from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

from .config import Roi


def capture_roi(display: str, roi: Roi, env: dict[str, str]) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="wechat-auto-reply-"))
    output = temp_dir / "capture.png"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "x11grab",
        "-video_size",
        f"{roi.width}x{roi.height}",
        "-i",
        f"{display}+{roi.x},{roi.y}",
        "-frames:v",
        "1",
        "-update",
        "1",
        "-y",
        str(output),
    ]
    subprocess.run(command, check=True, env=env)
    return output


def capture_window(window_id: str, env: dict[str, str]) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="wechat-auto-reply-"))
    xwd_path = temp_dir / "capture.xwd"
    png_path = temp_dir / "capture.png"
    subprocess.run(
        ["xwd", "-id", window_id, "-silent", "-out", str(xwd_path)],
        check=True,
        env=env,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(xwd_path),
            "-frames:v",
            "1",
            "-update",
            "1",
            "-y",
            str(png_path),
        ],
        check=True,
        env=env,
    )
    return png_path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
