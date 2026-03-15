from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import AppConfig, default_config_path, load_config
from .dbdetect import DbDetectService
from .service import AutoReplyService
from .state import StateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wechat-auto-reply")
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="Path to config.yaml",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ["calibrate", "once", "daemon", "pause", "resume", "status", "db-detect", "db-detect-once", "db-status"]:
        subparsers.add_parser(command)
    send_text = subparsers.add_parser("send-text")
    send_text.add_argument("--chat", required=True, help="Standalone chat window title")
    send_text.add_argument("--text", required=True, help="Text to send")
    send_file = subparsers.add_parser("send-file")
    send_file.add_argument("--chat", required=True, help="Standalone chat window title")
    send_file.add_argument("--path", type=Path, required=True, help="Absolute path to txt/md file")
    return parser


def load_app(config_path: Path) -> tuple[AppConfig, StateStore]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found: {config_path}. Copy config.example.yaml to this path and edit it first."
        )
    config = load_config(config_path)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    store = StateStore(config.state_dir, config.runtime_state_path, config.audit_log_path)
    return config, store


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config, store = load_app(args.config)
    service = AutoReplyService(config, store)
    db_service = DbDetectService(config, store)

    if args.command == "calibrate":
        calibration = service.calibrate()
        print(json.dumps(calibration.to_mapping(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "once":
        service.monitor.start()
        try:
            result = service.run_once()
        finally:
            service.monitor.stop()
        print(json.dumps({"action": result.action, "detail": result.detail}, ensure_ascii=False))
        return 0

    if args.command == "daemon":
        service.run_daemon()
        return 0

    if args.command == "db-detect":
        db_service.run_daemon()
        return 0

    if args.command == "db-detect-once":
        print(json.dumps(db_service.run_once(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "pause":
        config.pause_flag_path.touch()
        print("paused")
        return 0

    if args.command == "resume":
        config.pause_flag_path.unlink(missing_ok=True)
        print("resumed")
        return 0

    if args.command == "status":
        print(json.dumps(service.status(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "db-status":
        print(json.dumps(db_service.status(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "send-file":
        result = service.send_file(args.chat, args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "send-text":
        result = service.send_text(args.chat, args.text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
