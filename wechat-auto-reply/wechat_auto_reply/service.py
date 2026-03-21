from __future__ import annotations

import hashlib
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig
from .ollama import OllamaClient
from .reply import decide_reply
from .screenshot import capture_roi, capture_window, file_sha256
from .state import Calibration, StateStore
from .vision import (
    MessageItem,
    WindowObservation,
    analyze_chat_list,
    analyze_conversation,
    analyze_standalone_window,
    click_point_for_candidate,
    locate_context_action,
    pick_candidate,
    verify_reply_visible,
)
from .x11 import (
    UserInputMonitor,
    WindowInfo,
    activate_window,
    active_window_id,
    click,
    derive_default_rois,
    derive_standalone_rois,
    discover_standalone_windows,
    discover_wechat_window,
    key,
    list_windows,
    list_wechat_windows,
    paste_and_send,
    paste_text,
    right_click,
    scroll_page,
    x11_env,
)


DOWNLOAD_LABEL = "下载"
FILE_CHOOSER_TITLE_HINTS = ("Open", "打开", "Select File", "Select Files", "File Upload")
FILE_CHOOSER_CLASS_HINTS = ("GtkFileChooserDialog", "org.gnome.Nautilus", "Nautilus")


@dataclass(slots=True)
class CycleResult:
    action: str
    detail: str


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _text_fingerprint(chat_name: str, text: str) -> str:
    normalized = f"{chat_name.strip().lower()}::{_normalize_text(text)}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _file_fingerprint(chat_name: str, file_name: str) -> str:
    normalized = f"{chat_name.strip().lower()}::{file_name.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _sanitize_chat_title(chat_name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]+', "_", chat_name).strip()
    return sanitized or "unknown_chat"


class AutoReplyService:
    def __init__(self, config: AppConfig, store: StateStore) -> None:
        self.config = config
        self.store = store
        self.client = OllamaClient(
            config.ollama.base_url,
            timeout_s=config.ollama.timeout_s,
            api_format=config.ollama.api_format,
            api_key=config.ollama.api_key,
            disable_thinking=config.ollama.disable_thinking,
        )
        self.monitor = UserInputMonitor(config.window)
        self._suspend_until_ms = 0

    def _audit(self, scope: str, payload: dict[str, Any]) -> None:
        self.store.append_audit({"scope": scope, **payload})

    def _audit_guard(self, payload: dict[str, Any]) -> None:
        self._audit("guard", payload)

    def _audit_tools(self, payload: dict[str, Any]) -> None:
        self._audit("tools", payload)

    def _audit_experimental(self, payload: dict[str, Any]) -> None:
        self._audit("experimental", payload)

    def calibrate(self) -> Calibration:
        window = self._pick_calibration_window()
        if not window:
            raise RuntimeError("WeChat window not found")
        calibration_key = (
            self.config.window.calibration_key
            or (
                f"{self.config.window.monitor_mode}:{window.title}:"
                f"{window.width}x{window.height}:{self.config.window.display}"
            )
        )
        rois = (
            derive_standalone_rois(window)
            if self.config.window.monitor_mode == "standalone"
            else derive_default_rois(window)
        )
        calibration = Calibration(
            monitor_mode=self.config.window.monitor_mode,
            calibration_key=calibration_key,
            window_id=window.window_id,
            window_title=window.title,
            geometry=window.geometry,
            rois=rois,
            updated_at_ms=int(time.time() * 1000),
        )
        self.store.save_calibration(self.config.calibration_path, calibration)
        self._audit_guard(
            {
                "event": "calibration_saved",
                "monitor_mode": calibration.monitor_mode,
                "window_id": calibration.window_id,
                "window_title": calibration.window_title,
                "geometry": calibration.geometry,
            }
        )
        return calibration

    def load_or_calibrate(self) -> Calibration:
        calibration = self.store.load_calibration(self.config.calibration_path)
        if calibration and calibration.monitor_mode == self.config.window.monitor_mode:
            return calibration
        return self.calibrate()

    def send_text(self, chat_name: str, text: str) -> dict[str, Any]:
        message = text.strip()
        if not message:
            raise ValueError("Text message must not be empty")
        window = self._find_chat_window(chat_name)
        if not window:
            raise RuntimeError(f"Standalone chat window not found: {chat_name}")

        env = x11_env(self.config.window)
        self._audit_tools(
            {
                "event": "text_send_started",
                "chat_name": chat_name,
                "window_id": window.window_id,
                "text": message,
            }
        )

        rois = derive_standalone_rois(window)
        input_roi = rois["input"]
        activate_window(window.window_id, self.config.window)
        click(input_roi.x + input_roi.width // 2, input_roi.y + input_roi.height // 2, self.config.window)
        paste_and_send(message, self.config.window)
        time.sleep(0.8)

        verify_capture = capture_window(window.window_id, env)
        visible, verify_confidence = verify_reply_visible(
            self.client,
            self.config,
            verify_capture,
            message,
        )
        if not visible:
            self._audit_tools(
                {
                    "event": "text_send_failed",
                    "chat_name": chat_name,
                    "text": message,
                    "verify_confidence": verify_confidence,
                }
            )
            self.store.save()
            raise RuntimeError("text_send_verify_failed")

        self.store.remember_outbound_text(chat_name, _text_fingerprint(chat_name, message))
        self._audit_tools(
            {
                "event": "text_send_completed",
                "chat_name": chat_name,
                "text": message,
                "verify_confidence": verify_confidence,
            }
        )
        self.store.save()
        return {
            "chat_name": chat_name,
            "text": message,
            "verify_confidence": verify_confidence,
        }

    def send_file(self, chat_name: str, file_path: Path) -> dict[str, Any]:
        if not self.config.tools.send_file.enabled:
            raise RuntimeError("send_file_tool_disabled")
        path = file_path.expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        allowed = {item.lower().lstrip(".") for item in self.config.attachments.explicit_send_extensions}
        suffix = path.suffix.lower().lstrip(".")
        if suffix not in allowed:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        window = self._find_chat_window(chat_name)
        if not window:
            raise RuntimeError(f"Standalone chat window not found: {chat_name}")
        self._audit_tools(
            {
                "event": "file_send_started",
                "chat_name": chat_name,
                "path": str(path),
                "window_id": window.window_id,
            }
        )

        try:
            self._send_file_via_controls(window, path)
        except Exception:
            self._audit_tools(
                {
                    "event": "file_send_failed",
                    "chat_name": chat_name,
                    "path": str(path),
                }
            )
            self.store.save()
            raise

        fingerprint = _file_fingerprint(chat_name, path.name)
        self.store.remember_outbound_file(chat_name, fingerprint)
        self.store.append_recent_sent_file(chat_name, str(path), fingerprint)
        self._audit_tools(
            {
                "event": "file_send_completed",
                "chat_name": chat_name,
                "path": str(path),
            }
        )
        self.store.save()
        return {
            "chat_name": chat_name,
            "path": str(path),
        }

    def run_once(self) -> CycleResult:
        now_ms = int(time.time() * 1000)
        if self.config.pause_flag_path.exists():
            return CycleResult("paused", "global_pause_flag")
        if now_ms < self._suspend_until_ms:
            return CycleResult("paused", "temporary_suspend")

        env = x11_env(self.config.window)
        mode = self.config.window.monitor_mode
        if mode == "standalone":
            return self._run_once_standalone(now_ms, env)
        if mode == "main":
            return self._run_once_main(now_ms, env)
        if mode == "hybrid":
            standalone_result = self._run_once_standalone(now_ms, env)
            if standalone_result.action not in {"idle", "observed"}:
                return standalone_result
            main_result = self._run_once_main(now_ms, env)
            return self._prefer_result(standalone_result, main_result)
        raise RuntimeError(f"Unsupported monitor_mode: {mode}")

    def run_daemon(self) -> None:
        self.monitor.start()
        try:
            while True:
                result = self.run_once()
                self.store.runtime.last_status = {
                    "action": result.action,
                    "detail": result.detail,
                    "updated_at_ms": int(time.time() * 1000),
                }
                self.store.save()
                time.sleep(self.config.poll.interval_ms / 1000.0)
        finally:
            self.monitor.stop()

    def status(self) -> dict[str, object]:
        calibration = self.store.load_calibration(self.config.calibration_path)
        calibrated = (
            calibration is not None
            and calibration.monitor_mode == self.config.window.monitor_mode
        )
        current_windows = self._current_window_snapshot()
        return {
            "monitor_mode": self.config.window.monitor_mode,
            "paused": self.config.pause_flag_path.exists(),
            "guard_scope": {
                "private_chats": self.config.guard.whitelist.private_chats,
                "group_chats": self.config.guard.whitelist.group_chats,
                "legacy_titles": self.config.guard.whitelist.legacy_titles,
                "context_strategy": self.config.guard.context.strategy,
                "auto_download_inbound": self.config.guard.files.auto_download_inbound,
                "experimental_history_enabled": self.config.experimental.history.enabled,
            },
            "calibrated": calibrated,
            "calibration_key": calibration.calibration_key if calibrated else None,
            "calibration_mode": calibration.monitor_mode if calibration else None,
            "last_status": self.store.runtime.last_status,
            "seen_messages": len(self.store.runtime.seen_messages),
            "paused_chats": self.store.runtime.paused_chats,
            "current_windows": current_windows,
            "window_observations": self.store.runtime.window_observations,
            "last_message_items": self.store.runtime.last_message_items,
            "recent_downloads": self.store.runtime.recent_downloads,
            "recent_sent_files": self.store.runtime.recent_sent_files,
        }

    def _pick_calibration_window(self) -> WindowInfo | None:
        if self.config.window.monitor_mode == "standalone":
            windows = discover_standalone_windows(self.config.window, self.config.whitelist)
            if windows:
                return windows[0]
            all_windows = list_wechat_windows(self.config.window)
            standalone = [
                item
                for item in all_windows
                if item.title and item.title not in {"Weixin", "微信"}
            ]
            return standalone[0] if standalone else None
        return discover_wechat_window(self.config.window)

    def _current_window_snapshot(self) -> list[dict[str, Any]]:
        if self.config.window.monitor_mode == "standalone":
            windows = discover_standalone_windows(self.config.window, self.config.whitelist)
        elif self.config.window.monitor_mode == "hybrid":
            windows = list_wechat_windows(self.config.window)
        else:
            window = discover_wechat_window(self.config.window)
            windows = [window] if window else []
        return [
            {
                "window_id": item.window_id,
                "title": item.title,
                "geometry": item.geometry,
            }
            for item in windows
            if item
        ]

    def _prefer_result(self, left: CycleResult, right: CycleResult) -> CycleResult:
        priority = {
            "sent": 7,
            "downloaded": 6,
            "dry_run": 5,
            "paused": 4,
            "skipped": 3,
            "observed": 2,
            "idle": 1,
        }
        left_priority = priority.get(left.action, 0)
        right_priority = priority.get(right.action, 0)
        if right_priority > left_priority:
            return right
        if right_priority == left_priority and right.detail != left.detail:
            return right
        return left

    def _user_active_in_any_wechat_window(self) -> bool:
        active_window = active_window_id(self.config.window)
        if not active_window:
            return False
        if self.monitor.ms_since_user_input() >= self.config.conflict.user_idle_ms:
            return False
        return any(item.window_id == active_window for item in list_wechat_windows(self.config.window))

    def _run_once_main(self, now_ms: int, env: dict[str, str]) -> CycleResult:
        calibration = self.load_or_calibrate()
        window = discover_wechat_window(self.config.window)
        if not window:
            self._audit_guard({"event": "window_missing"})
            return CycleResult("idle", "window_missing")

        if active_window_id(self.config.window) == window.window_id:
            if self.monitor.ms_since_user_input() < self.config.conflict.user_idle_ms:
                self._suspend_until_ms = now_ms + self.config.conflict.wechat_pause_ms
                return CycleResult("paused", "user_active_in_wechat")

        chat_list_capture = capture_roi(self.config.window.display, calibration.rois["chat_list"], env)
        candidates = analyze_chat_list(self.client, self.config, chat_list_capture)
        candidate = pick_candidate(candidates, self.config)
        if not candidate:
            self._audit_guard({"event": "no_candidate"})
            return CycleResult("idle", "no_candidate")
        if self.store.chat_paused(candidate.chat_name):
            return CycleResult("paused", f"chat_paused:{candidate.chat_name}")

        if self.config.window.focus_allowed:
            activate_window(window.window_id, self.config.window)
        x, y = click_point_for_candidate(calibration.rois["chat_list"], candidate)
        click(x, y, self.config.window)
        time.sleep(0.35)

        if active_window_id(self.config.window) == window.window_id:
            if self.monitor.ms_since_user_input() < self.config.conflict.user_idle_ms:
                self._suspend_until_ms = now_ms + self.config.conflict.wechat_pause_ms
                self.store.pause_chat_until(
                    candidate.chat_name,
                    now_ms + self.config.conflict.send_conflict_cooldown_ms,
                )
                return CycleResult("paused", f"focus_conflict:{candidate.chat_name}")

        conversation_capture = capture_roi(self.config.window.display, calibration.rois["conversation"], env)
        observation = analyze_conversation(self.client, self.config, conversation_capture, candidate.chat_name)
        if self.store.has_seen(observation.message_hash):
            return CycleResult("idle", "already_seen")

        turns = self.store.get_recent_turns(candidate.chat_name)
        decision = decide_reply(self.client, self.config, observation, turns)
        self._audit_guard(
            {
                "event": "decision",
                "chat_name": candidate.chat_name,
                "message_hash": observation.message_hash,
                "observation": {
                    "direction": observation.direction,
                    "confidence": observation.confidence,
                    "text": observation.latest_inbound_text,
                },
                "decision": {
                    "should_send": decision.should_send,
                    "reason": decision.reason,
                    "risk_flags": decision.risk_flags,
                },
            }
        )
        if not decision.should_send:
            self.store.mark_seen(observation.message_hash)
            self.store.add_turn(candidate.chat_name, "inbound", observation.latest_inbound_text)
            self.store.save()
            return CycleResult("skipped", decision.reason)

        if self.config.safety.dry_run:
            self._audit_guard(
                {
                    "event": "dry_run_reply",
                    "chat_name": candidate.chat_name,
                    "message_hash": observation.message_hash,
                    "reply_text": decision.reply_text,
                }
            )
            self.store.runtime.last_status = {
                "last_chat": candidate.chat_name,
                "last_message_hash": observation.message_hash,
                "last_reply": decision.reply_text,
                "updated_at_ms": int(time.time() * 1000),
                "dry_run": True,
            }
            self.store.save()
            return CycleResult("dry_run", candidate.chat_name)

        input_roi = calibration.rois["input"]
        click(input_roi.x + input_roi.width // 2, input_roi.y + input_roi.height // 2, self.config.window)
        paste_and_send(decision.reply_text, self.config.window)
        time.sleep(0.8)

        verify_capture = capture_roi(self.config.window.display, calibration.rois["conversation"], env)
        reply_visible, verify_confidence = verify_reply_visible(
            self.client,
            self.config,
            verify_capture,
            decision.reply_text,
        )
        if not reply_visible or verify_confidence < self.config.safety.require_confidence:
            self.store.pause_chat_until(
                candidate.chat_name,
                now_ms + self.config.conflict.send_conflict_cooldown_ms,
            )
            self._audit_guard(
                {
                    "event": "send_verify_failed",
                    "chat_name": candidate.chat_name,
                    "message_hash": observation.message_hash,
                    "verify_confidence": verify_confidence,
                }
            )
            self.store.save()
            return CycleResult("paused", "send_verify_failed")

        self.store.mark_seen(observation.message_hash)
        self.store.add_turn(candidate.chat_name, "inbound", observation.latest_inbound_text)
        self.store.add_turn(candidate.chat_name, "outbound", decision.reply_text)
        self.store.runtime.last_status = {
            "last_chat": candidate.chat_name,
            "last_message_hash": observation.message_hash,
            "last_reply": decision.reply_text,
            "updated_at_ms": int(time.time() * 1000),
        }
        self._audit_guard(
            {
                "event": "reply_sent",
                "chat_name": candidate.chat_name,
                "message_hash": observation.message_hash,
                "reply_text": decision.reply_text,
            }
        )
        self.store.save()
        return CycleResult("sent", candidate.chat_name)

    def _run_once_standalone(self, now_ms: int, env: dict[str, str]) -> CycleResult:
        calibration = self.store.load_calibration(self.config.calibration_path)
        if not calibration or calibration.monitor_mode != self.config.window.monitor_mode:
            try:
                self.calibrate()
            except RuntimeError:
                pass
        windows = discover_standalone_windows(self.config.window, self.config.whitelist)
        if not windows:
            self._audit_guard({"event": "standalone_window_missing"})
            return CycleResult("idle", "window_missing")
        if self._user_active_in_any_wechat_window():
            self._suspend_until_ms = now_ms + self.config.conflict.wechat_pause_ms
            return CycleResult("paused", "user_active_in_wechat")

        result = CycleResult("idle", "no_window_changes")
        for window in windows:
            try:
                current = self._process_standalone_window(window, now_ms, env)
            except Exception as exc:  # pragma: no cover - defensive live guard
                self._audit_guard(
                    {
                        "event": "window_process_failed",
                        "chat_name": window.title,
                        "window_id": window.window_id,
                        "error": str(exc),
                    }
                )
                self.store.save()
                current = CycleResult("idle", f"window_process_failed:{window.title}")
            result = self._prefer_result(result, current)
        return result

    def _process_standalone_window(self, window: WindowInfo, now_ms: int, env: dict[str, str]) -> CycleResult:
        chat_name = window.title
        if self.config.is_group_chat(chat_name) and self.config.safety.disallow_groups:
            return CycleResult("skipped", f"group_guard_disabled:{chat_name}")
        if self.store.chat_paused(chat_name):
            return CycleResult("paused", f"chat_paused:{chat_name}")

        screenshot = capture_window(window.window_id, env)
        screenshot_hash = file_sha256(screenshot)
        cached = self.store.get_window_observation(chat_name)
        if (
            cached.get("screenshot_hash") == screenshot_hash
            and cached.get("window_id") == window.window_id
        ):
            return CycleResult("idle", f"unchanged_screenshot:{chat_name}")

        observation, items, pages_scrolled = self._collect_history(window, env, screenshot, screenshot_hash)
        latest_visible = self._latest_visible_item(items)
        self.store.update_window_observation(
            chat_name,
            {
                "window_id": window.window_id,
                "window_title": window.title,
                "screenshot_hash": screenshot_hash,
                "message_hash": latest_visible.item_hash if latest_visible else None,
                "updated_at_ms": now_ms,
                "pages_scrolled": pages_scrolled,
            },
        )
        self.store.set_last_message_items(
            chat_name,
            [item.to_mapping() for item in items[-10:]],
        )
        self._audit_guard(
            {
                "event": "window_observation",
                "chat_name": chat_name,
                "window_id": window.window_id,
                "screenshot_hash": screenshot_hash,
                "pages_scrolled": pages_scrolled,
                "input_has_text": observation.input_has_text,
                "send_button_enabled": observation.send_button_enabled,
                "items": [item.to_mapping() for item in items[-6:]],
            }
        )

        self._record_outbound_items(chat_name, items)

        if observation.input_has_text:
            self._audit_guard(
                {
                    "event": "draft_present",
                    "chat_name": chat_name,
                    "input_has_text": observation.input_has_text,
                    "send_button_enabled": observation.send_button_enabled,
                }
            )
            self.store.save()
            return CycleResult("skipped", f"draft_present:{chat_name}")

        if not latest_visible:
            self.store.save()
            return CycleResult("idle", f"no_items:{chat_name}")

        if not cached.get("baseline_message_hash"):
            self.store.update_window_observation(
                chat_name,
                {"baseline_message_hash": latest_visible.item_hash},
            )
            self._audit_guard(
                {
                    "event": "baseline_initialized",
                    "chat_name": chat_name,
                    "message_hash": latest_visible.item_hash,
                }
            )
            self.store.save()
            return CycleResult("observed", f"baseline_initialized:{chat_name}")

        if cached.get("baseline_message_hash") == latest_visible.item_hash:
            self.store.save()
            return CycleResult("idle", f"no_message_change:{chat_name}")

        item = self._select_latest_actionable_item(chat_name, items)
        if not item:
            self.store.update_window_observation(
                chat_name,
                {"baseline_message_hash": latest_visible.item_hash},
            )
            self.store.save()
            return CycleResult("skipped", f"no_actionable_item:{chat_name}")

        if item.kind == "file":
            if not self.config.guard.files.auto_download_inbound:
                self.store.mark_seen(item.item_hash)
                self.store.update_window_observation(
                    chat_name,
                    {"baseline_message_hash": latest_visible.item_hash},
                )
                self._audit_guard(
                    {
                        "event": "file_auto_download_skipped",
                        "chat_name": chat_name,
                        "message_hash": item.item_hash,
                    }
                )
                self.store.save()
                return CycleResult("skipped", f"file_auto_download_disabled:{chat_name}")
            saved_path = self._download_file_item(window, chat_name, item, env)
            self.store.update_window_observation(
                chat_name,
                {"baseline_message_hash": latest_visible.item_hash},
            )
            self.store.mark_seen(item.item_hash)
            self.store.save()
            if not saved_path:
                return CycleResult("paused", f"download_failed:{chat_name}")
            return CycleResult("downloaded", chat_name)

        observation_for_reply = self._conversation_observation_from_item(chat_name, item, observation)
        turns = self.store.get_recent_turns(chat_name)
        decision = decide_reply(self.client, self.config, observation_for_reply, turns)
        self._audit_guard(
            {
                "event": "decision",
                "chat_name": chat_name,
                "message_hash": item.item_hash,
                "observation": {
                    "direction": item.direction,
                    "confidence": item.confidence,
                    "text": item.text_or_filename,
                    "pages_scrolled": pages_scrolled,
                },
                "decision": {
                    "should_send": decision.should_send,
                    "reason": decision.reason,
                    "risk_flags": decision.risk_flags,
                },
            }
        )
        if not decision.should_send:
            self.store.mark_seen(item.item_hash)
            if item.text_or_filename:
                self.store.add_turn(chat_name, "inbound", item.text_or_filename)
            self.store.update_window_observation(
                chat_name,
                {"baseline_message_hash": latest_visible.item_hash},
            )
            self.store.save()
            return CycleResult("skipped", f"{decision.reason}:{chat_name}")

        if self.config.safety.dry_run:
            self.store.mark_seen(item.item_hash)
            self.store.add_turn(chat_name, "inbound", item.text_or_filename)
            self.store.update_window_observation(
                chat_name,
                {"baseline_message_hash": latest_visible.item_hash},
            )
            self._audit_guard(
                {
                    "event": "dry_run_reply",
                    "chat_name": chat_name,
                    "message_hash": item.item_hash,
                    "reply_text": decision.reply_text,
                }
            )
            self.store.runtime.last_status = {
                "last_chat": chat_name,
                "last_message_hash": item.item_hash,
                "last_reply": decision.reply_text,
                "updated_at_ms": now_ms,
                "dry_run": True,
            }
            self.store.save()
            return CycleResult("dry_run", chat_name)

        if not self.config.window.focus_allowed:
            return CycleResult("skipped", f"focus_disabled:{chat_name}")

        rois = derive_standalone_rois(window)
        activate_window(window.window_id, self.config.window)
        input_roi = rois["input"]
        click(input_roi.x + input_roi.width // 2, input_roi.y + input_roi.height // 2, self.config.window)
        paste_and_send(decision.reply_text, self.config.window)
        time.sleep(0.8)

        verify_capture = capture_window(window.window_id, env)
        reply_visible, verify_confidence = verify_reply_visible(
            self.client,
            self.config,
            verify_capture,
            decision.reply_text,
        )
        if not reply_visible:
            self.store.pause_chat_until(
                chat_name,
                now_ms + self.config.conflict.send_conflict_cooldown_ms,
            )
            self._audit_guard(
                {
                    "event": "send_verify_failed",
                    "chat_name": chat_name,
                    "message_hash": item.item_hash,
                    "verify_confidence": verify_confidence,
                }
            )
            self.store.save()
            return CycleResult("paused", f"send_verify_failed:{chat_name}")

        self.store.mark_seen(item.item_hash)
        self.store.add_turn(chat_name, "inbound", item.text_or_filename)
        self.store.add_turn(chat_name, "outbound", decision.reply_text)
        self.store.remember_outbound_text(chat_name, _text_fingerprint(chat_name, decision.reply_text))
        self.store.update_window_observation(
            chat_name,
            {"baseline_message_hash": latest_visible.item_hash},
        )
        self.store.runtime.last_status = {
            "last_chat": chat_name,
            "last_message_hash": item.item_hash,
            "last_reply": decision.reply_text,
            "updated_at_ms": now_ms,
        }
        self._audit_guard(
            {
                "event": "reply_sent",
                "chat_name": chat_name,
                "message_hash": item.item_hash,
                "reply_text": decision.reply_text,
            }
        )
        self.store.save()
        return CycleResult("sent", chat_name)

    def _collect_history(
        self,
        window: WindowInfo,
        env: dict[str, str],
        screenshot: Path,
        screenshot_hash: str,
    ) -> tuple[WindowObservation, list[MessageItem], int]:
        observation = self._coerce_window_observation(
            window.title,
            analyze_standalone_window(self.client, self.config, screenshot, window.title),
        )
        merged_items = list(observation.items)
        pages_scrolled = 0
        cached = self.store.get_window_observation(window.title)
        if not cached.get("baseline_message_hash"):
            return observation, merged_items, pages_scrolled
        if not self.config.experimental.history.enabled:
            return observation, merged_items, pages_scrolled
        if not self._needs_history(window.title, merged_items):
            return observation, merged_items, pages_scrolled

        rois = derive_standalone_rois(window)
        conversation = rois["conversation"]
        center_x = conversation.x + conversation.width // 2
        center_y = conversation.y + conversation.height // 2
        if self.config.window.focus_allowed:
            activate_window(window.window_id, self.config.window)

        while (
            pages_scrolled < self.config.experimental.history.max_pages
            and self._needs_history(window.title, merged_items)
        ):
            scroll_page(center_x, center_y, "up", self.config.window)
            time.sleep(0.15)
            older_capture = capture_window(window.window_id, env)
            older_hash = file_sha256(older_capture)
            older_observation = self._coerce_window_observation(
                window.title,
                analyze_standalone_window(self.client, self.config, older_capture, window.title),
            )
            older_items = older_observation.items
            merged_items = self._merge_items(older_items, merged_items)
            pages_scrolled += 1
            self._audit_experimental(
                {
                    "event": "scroll_page_captured",
                    "chat_name": window.title,
                    "page_index": pages_scrolled,
                    "screenshot_hash": older_hash,
                    "item_count": len(older_items),
                }
            )
            if older_hash == screenshot_hash:
                break

        for _ in range(pages_scrolled):
            scroll_page(center_x, center_y, "down", self.config.window)
            time.sleep(0.08)

        return observation, merged_items, pages_scrolled

    def _coerce_window_observation(self, chat_name: str, raw: Any) -> WindowObservation:
        if isinstance(raw, WindowObservation):
            return raw
        latest_text = str(getattr(raw, "latest_inbound_text", "")).strip()
        direction = str(getattr(raw, "direction", "unknown")).strip()
        confidence = float(getattr(raw, "confidence", 0.0))
        item = MessageItem(
            kind="text",
            direction=direction,
            text_or_filename=latest_text,
            confidence=confidence,
            bbox={"x": 0.2, "y": 0.2, "width": 0.6, "height": 0.2},
            downloadable=False,
            truncated=False,
            from_self=(direction == "outbound"),
        )
        return WindowObservation(
            chat_name=chat_name,
            input_has_text=bool(getattr(raw, "input_has_text", False)),
            send_button_enabled=bool(getattr(raw, "send_button_enabled", False)),
            items=[item] if latest_text else [],
        )

    def _needs_history(self, chat_name: str, items: list[MessageItem]) -> bool:
        if self.config.guard.context.strategy != "truncated_actionable_one_page":
            return False
        latest_actionable = self._select_latest_actionable_item(chat_name, items)
        return bool(latest_actionable and latest_actionable.truncated)

    def _merge_items(self, older: list[MessageItem], newer: list[MessageItem]) -> list[MessageItem]:
        merged: list[MessageItem] = []
        seen: set[str] = set()
        for item in older + newer:
            if item.item_hash in seen:
                continue
            seen.add(item.item_hash)
            merged.append(item)
        return merged

    def _latest_visible_item(self, items: list[MessageItem]) -> MessageItem | None:
        for item in reversed(items):
            if item.kind != "system":
                return item
        return None

    def _record_outbound_items(self, chat_name: str, items: list[MessageItem]) -> None:
        for item in items:
            if item.direction != "outbound":
                continue
            if item.kind == "text" and item.text_or_filename:
                fingerprint = _text_fingerprint(chat_name, item.text_or_filename)
                if not self.store.outbound_text_seen(chat_name, fingerprint):
                    self.store.remember_outbound_text(chat_name, fingerprint)
                    self.store.add_turn(chat_name, "outbound", item.text_or_filename)
            if item.kind == "file" and item.text_or_filename:
                fingerprint = _file_fingerprint(chat_name, item.text_or_filename)
                if not self.store.outbound_file_seen(chat_name, fingerprint):
                    self.store.remember_outbound_file(chat_name, fingerprint)
            self._audit_guard(
                {
                    "event": "outbound_ignored",
                    "chat_name": chat_name,
                    "item_hash": item.item_hash,
                    "kind": item.kind,
                    "text_or_filename": item.text_or_filename,
                }
            )

    def _select_latest_actionable_item(self, chat_name: str, items: list[MessageItem]) -> MessageItem | None:
        latest_visible = self._latest_visible_item(items)
        if not latest_visible:
            return None
        if latest_visible.direction != "inbound":
            return None
        if latest_visible.from_self is True:
            return None

        item = latest_visible
        if item.kind == "file":
            if self.store.download_seen(chat_name, item.item_hash):
                return None
            if item.text_or_filename and self.store.outbound_file_seen(
                chat_name,
                _file_fingerprint(chat_name, item.text_or_filename),
            ):
                return None
            return item
        if item.kind == "text":
            if self.store.has_seen(item.item_hash):
                return None
            if item.text_or_filename and self.store.outbound_text_seen(
                chat_name,
                _text_fingerprint(chat_name, item.text_or_filename),
            ):
                return None
            return item
        return None

    def _conversation_observation_from_item(
        self,
        chat_name: str,
        item: MessageItem,
        observation: WindowObservation,
    ):
        from .vision import ConversationObservation

        return ConversationObservation(
            chat_name=chat_name,
            latest_inbound_text=item.text_or_filename,
            direction=item.direction,
            confidence=item.confidence,
            input_has_text=observation.input_has_text,
            send_button_enabled=observation.send_button_enabled,
            items=[item],
        )

    def _download_file_item(
        self,
        window: WindowInfo,
        chat_name: str,
        item: MessageItem,
        env: dict[str, str],
    ) -> Path | None:
        root = Path(self.config.downloads.root_dir).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        before = self._snapshot_download_tree(root)
        click_x, click_y = self._item_click_point(window, item)

        activate_window(window.window_id, self.config.window)
        click(click_x, click_y, self.config.window)
        time.sleep(0.15)
        right_click(click_x, click_y, self.config.window)
        time.sleep(0.25)

        menu_capture = capture_window(window.window_id, env)
        found, x_ratio, y_ratio, confidence = locate_context_action(
            self.client,
            self.config,
            menu_capture,
            DOWNLOAD_LABEL,
        )
        if not found or confidence < 0.4:
            key("Escape", self.config.window)
            self._audit_guard(
                {
                    "event": "file_download_failed",
                    "chat_name": chat_name,
                    "item_hash": item.item_hash,
                    "reason": "download_menu_not_found",
                }
            )
            return None

        menu_x, menu_y = self._ratio_to_abs(window, x_ratio, y_ratio)
        click(menu_x, menu_y, self.config.window)
        self._audit_guard(
            {
                "event": "file_download_started",
                "chat_name": chat_name,
                "item_hash": item.item_hash,
                "file_name": item.text_or_filename,
            }
        )

        downloaded = self._wait_for_download(root, before)
        if not downloaded:
            self._audit_guard(
                {
                    "event": "file_download_failed",
                    "chat_name": chat_name,
                    "item_hash": item.item_hash,
                    "reason": "download_timeout",
                }
            )
            return None

        final_path = self._organize_download(chat_name, downloaded)
        self.store.remember_download(chat_name, item.item_hash, str(final_path))
        self._audit_guard(
            {
                "event": "file_download_completed",
                "chat_name": chat_name,
                "item_hash": item.item_hash,
                "source_path": str(downloaded),
                "saved_path": str(final_path),
            }
        )
        return final_path

    def _snapshot_download_tree(self, root: Path) -> dict[str, int]:
        snapshot: dict[str, int] = {}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                snapshot[str(path)] = path.stat().st_mtime_ns
            except FileNotFoundError:
                continue
        return snapshot

    def _wait_for_download(self, root: Path, before: dict[str, int]) -> Path | None:
        deadline = time.time() + self.config.downloads.poll_timeout_s
        ignored_suffixes = {".tmp", ".part", ".download"}
        while time.time() < deadline:
            candidates: list[tuple[int, Path]] = []
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() in ignored_suffixes:
                    continue
                try:
                    stat = path.stat()
                except FileNotFoundError:
                    continue
                previous = before.get(str(path))
                if previous is None or stat.st_mtime_ns > previous:
                    candidates.append((stat.st_mtime_ns, path))
            if candidates:
                candidates.sort(key=lambda item: item[0], reverse=True)
                return candidates[0][1]
            time.sleep(self.config.downloads.poll_interval_ms / 1000.0)
        return None

    def _organize_download(self, chat_name: str, source_path: Path) -> Path:
        root = Path(self.config.downloads.root_dir).expanduser()
        if self.config.downloads.organize_by_chat_title:
            target_dir = root / _sanitize_chat_title(chat_name)
        else:
            target_dir = root
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / source_path.name
        if target_path.resolve() == source_path.resolve():
            return target_path
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            target_path = target_dir / f"{stem}-{timestamp}{suffix}"
        shutil.copy2(source_path, target_path)
        return target_path

    def _find_chat_window(self, chat_name: str) -> WindowInfo | None:
        windows = [
            item
            for item in list_wechat_windows(self.config.window)
            if item.title and item.title not in {"Weixin", "微信"}
        ]
        for window in windows:
            if window.title == chat_name:
                return window
        return None

    def _ratio_to_abs(self, window: WindowInfo, x_ratio: float, y_ratio: float) -> tuple[int, int]:
        x = window.x + int(max(0.0, min(1.0, x_ratio)) * window.width)
        y = window.y + int(max(0.0, min(1.0, y_ratio)) * window.height)
        return x, y

    def _item_click_point(self, window: WindowInfo, item: MessageItem) -> tuple[int, int]:
        x_ratio, y_ratio = item.center_ratio
        return self._ratio_to_abs(window, x_ratio, y_ratio)

    def _fallback_attachment_point(self, window: WindowInfo) -> tuple[float, float]:
        rois = derive_standalone_rois(window)
        input_roi = rois["input"]
        x_ratio = ((input_roi.x - window.x) + max(80, int(input_roi.width * 0.18))) / window.width
        y_ratio = ((input_roi.y - window.y) + max(24, int(input_roi.height * 0.24))) / window.height
        return x_ratio, y_ratio

    def _send_file_via_controls(self, chat_window: WindowInfo, file_path: Path) -> None:
        folder_x, folder_y = self._toolbar_file_button_point(chat_window)
        activate_window(chat_window.window_id, self.config.window)
        click(folder_x, folder_y, self.config.window)
        time.sleep(self.config.attachments.chooser_open_delay_ms / 1000.0)

        chooser = self._wait_for_window_title(FILE_CHOOSER_TITLE_HINTS, timeout_s=3.0)
        if not chooser:
            key("ctrl+o", self.config.window)
            time.sleep(0.4)
            chooser = self._wait_for_window_title(FILE_CHOOSER_TITLE_HINTS, timeout_s=2.0)
        if not chooser:
            raise RuntimeError("file_chooser_not_found")

        activate_window(chooser.window_id, self.config.window)
        time.sleep(0.1)
        key("alt+n", self.config.window)
        time.sleep(0.05)
        key("ctrl+a", self.config.window)
        time.sleep(0.05)
        key("BackSpace", self.config.window)
        time.sleep(0.05)
        paste_text(str(file_path), self.config.window)
        time.sleep(0.1)
        key("alt+o", self.config.window)
        time.sleep(0.3)
        activate_window(chat_window.window_id, self.config.window)
        time.sleep(0.1)
        key("Return", self.config.window)
        time.sleep(self.config.attachments.post_send_delay_ms / 1000.0)

    def _toolbar_file_button_point(self, window: WindowInfo) -> tuple[int, int]:
        input_roi = derive_standalone_rois(window)["input"]
        x = input_roi.x + max(104, int(input_roi.width * 0.18))
        y = input_roi.y + max(10, int(input_roi.height * 0.06))
        return x, y

    def _title_matches(self, title: str, expected: str) -> bool:
        normalized_title = re.sub(r"\s+", " ", (title or "").strip()).lower()
        normalized_expected = re.sub(r"\s+", " ", (expected or "").strip()).lower()
        if not normalized_title or not normalized_expected:
            return False
        if normalized_title == normalized_expected:
            return True
        if normalized_expected in {"open", "打开"}:
            return any(
                alias in normalized_title
                for alias in ("open", "打开", "select file", "select files", "file upload")
            )
        return normalized_expected in normalized_title

    def _looks_like_file_chooser_title(self, title: str) -> bool:
        normalized_title = re.sub(r"\s+", " ", (title or "").strip()).lower()
        return any(alias in normalized_title for alias in ("open", "打开", "select file", "select files", "file upload"))

    def _find_window_by_title(self, title: str | tuple[str, ...]) -> WindowInfo | None:
        candidates = (title,) if isinstance(title, str) else title
        for class_name in (*FILE_CHOOSER_CLASS_HINTS, None):
            for window in list_windows(self.config.window, class_name=class_name):
                if any(self._title_matches(window.title, item) for item in candidates):
                    return window
                if self._looks_like_file_chooser_title(window.title):
                    return window
        return None

    def _wait_for_window_title(self, title: str | tuple[str, ...], timeout_s: float) -> WindowInfo | None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            chooser = self._find_window_by_title(title)
            if chooser:
                return chooser
            time.sleep(0.1)
        return None
