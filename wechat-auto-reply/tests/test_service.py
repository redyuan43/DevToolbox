from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wechat_auto_reply.config import (
    AppConfig,
    ExperimentalConfig,
    GuardConfig,
    GuardContextConfig,
    GuardWhitelistConfig,
    HistoryConfig,
    OllamaConfig,
    SafetyConfig,
    WindowConfig,
)
from wechat_auto_reply.service import AutoReplyService
from wechat_auto_reply.state import StateStore
from wechat_auto_reply.vision import ConversationObservation, MessageItem, WindowObservation
from wechat_auto_reply.x11 import WindowInfo


class StandaloneServiceTests(unittest.TestCase):
    def _build_service(self, tmp: str) -> tuple[AutoReplyService, Path]:
        state_dir = Path(tmp) / "state"
        config = AppConfig(
            window=WindowConfig(monitor_mode="standalone", focus_allowed=False),
            guard=GuardConfig(
                whitelist=GuardWhitelistConfig(private_chats=["Ivan"]),
                context=GuardContextConfig(strategy="truncated_actionable_one_page"),
            ),
            experimental=ExperimentalConfig(history=HistoryConfig(enabled=True, max_pages=1)),
            ollama=OllamaConfig(base_url="http://127.0.0.1:11434", timeout_s=1),
            safety=SafetyConfig(dry_run=True),
            state_dir=state_dir,
            config_dir=Path(tmp) / "config",
        )
        store = StateStore(config.state_dir, config.runtime_state_path, config.audit_log_path)
        service = AutoReplyService(config, store)
        return service, state_dir

    def test_first_seen_window_only_initializes_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = self._build_service(tmp)
            capture = Path(tmp) / "capture.png"
            capture.write_bytes(b"first")
            window = WindowInfo("0x1", "Ivan", "wechat", 10, 20, 598, 640)
            observation = ConversationObservation("Ivan", "你好", "inbound", 0.95)

            with (
                patch("wechat_auto_reply.service.discover_standalone_windows", return_value=[window]),
                patch("wechat_auto_reply.service.list_wechat_windows", return_value=[window]),
                patch("wechat_auto_reply.service.active_window_id", return_value=None),
                patch("wechat_auto_reply.service.capture_window", return_value=capture),
                patch("wechat_auto_reply.service.analyze_standalone_window", return_value=observation) as analyze_mock,
                patch.object(service, "calibrate"),
            ):
                result = service.run_once()

            self.assertEqual(result.action, "observed")
            self.assertIsNotNone(service.store.get_window_observation("Ivan").get("baseline_message_hash"))
            self.assertEqual(analyze_mock.call_count, 1)

    def test_unchanged_screenshot_skips_second_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = self._build_service(tmp)
            capture = Path(tmp) / "capture.png"
            capture.write_bytes(b"same")
            window = WindowInfo("0x1", "Ivan", "wechat", 10, 20, 598, 640)
            observation = ConversationObservation("Ivan", "你好", "inbound", 0.95)

            with (
                patch("wechat_auto_reply.service.discover_standalone_windows", return_value=[window]),
                patch("wechat_auto_reply.service.list_wechat_windows", return_value=[window]),
                patch("wechat_auto_reply.service.active_window_id", return_value=None),
                patch("wechat_auto_reply.service.capture_window", return_value=capture),
                patch("wechat_auto_reply.service.analyze_standalone_window", return_value=observation) as analyze_mock,
                patch.object(service, "calibrate"),
            ):
                first = service.run_once()
                second = service.run_once()

            self.assertEqual(first.action, "observed")
            self.assertEqual(second.detail, "unchanged_screenshot:Ivan")
            self.assertEqual(analyze_mock.call_count, 1)

    def test_draft_present_skips_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = self._build_service(tmp)
            first_capture = Path(tmp) / "capture1.png"
            second_capture = Path(tmp) / "capture2.png"
            first_capture.write_bytes(b"first")
            second_capture.write_bytes(b"second")
            window = WindowInfo("0x1", "Ivan", "wechat", 10, 20, 598, 640)
            baseline = ConversationObservation("Ivan", "旧消息", "inbound", 0.95)
            draft = ConversationObservation("Ivan", "新消息", "inbound", 0.95, input_has_text=True)

            with (
                patch("wechat_auto_reply.service.discover_standalone_windows", return_value=[window]),
                patch("wechat_auto_reply.service.list_wechat_windows", return_value=[window]),
                patch("wechat_auto_reply.service.active_window_id", return_value=None),
                patch("wechat_auto_reply.service.capture_window", side_effect=[first_capture, second_capture]),
                patch("wechat_auto_reply.service.analyze_standalone_window", side_effect=[baseline, draft]),
                patch("wechat_auto_reply.service.decide_reply") as decide_reply_mock,
                patch.object(service, "calibrate"),
            ):
                service.run_once()
                result = service.run_once()

            self.assertEqual(result.detail, "draft_present:Ivan")
            self.assertEqual(decide_reply_mock.call_count, 0)

    def test_outbound_item_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = self._build_service(tmp)
            capture = Path(tmp) / "capture.png"
            capture.write_bytes(b"first")
            window = WindowInfo("0x1", "Ivan", "wechat", 10, 20, 598, 640)
            outbound_observation = WindowObservation(
                chat_name="Ivan",
                input_has_text=False,
                send_button_enabled=False,
                items=[
                    MessageItem(
                        kind="text",
                        direction="outbound",
                        text_or_filename="我刚发过的消息",
                        confidence=0.95,
                        bbox={"x": 0.5, "y": 0.5, "width": 0.2, "height": 0.1},
                    )
                ],
            )

            with (
                patch("wechat_auto_reply.service.discover_standalone_windows", return_value=[window]),
                patch("wechat_auto_reply.service.list_wechat_windows", return_value=[window]),
                patch("wechat_auto_reply.service.active_window_id", return_value=None),
                patch("wechat_auto_reply.service.capture_window", return_value=capture),
                patch("wechat_auto_reply.service.analyze_standalone_window", return_value=outbound_observation),
                patch.object(service, "calibrate"),
            ):
                first = service.run_once()
                second = service.run_once()

            self.assertEqual(first.action, "observed")
            self.assertEqual(second.detail, "unchanged_screenshot:Ivan")
            self.assertTrue(service.store.runtime.outbound_text_hashes.get("Ivan"))

    def test_history_does_not_scroll_for_truncated_outbound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = self._build_service(tmp)
            capture = Path(tmp) / "capture.png"
            capture.write_bytes(b"first")
            window = WindowInfo("0x1", "Ivan", "wechat", 10, 20, 598, 640)
            observation = WindowObservation(
                chat_name="Ivan",
                input_has_text=False,
                send_button_enabled=False,
                items=[
                    MessageItem(
                        kind="text",
                        direction="outbound",
                        text_or_filename="一条很长的我方消息",
                        confidence=0.95,
                        bbox={"x": 0.2, "y": 0.5, "width": 0.5, "height": 0.2},
                        truncated=True,
                        from_self=True,
                    )
                ],
            )

            with (
                patch("wechat_auto_reply.service.discover_standalone_windows", return_value=[window]),
                patch("wechat_auto_reply.service.list_wechat_windows", return_value=[window]),
                patch("wechat_auto_reply.service.active_window_id", return_value=None),
                patch("wechat_auto_reply.service.capture_window", return_value=capture),
                patch("wechat_auto_reply.service.analyze_standalone_window", return_value=observation),
                patch("wechat_auto_reply.service.scroll_page") as scroll_mock,
                patch.object(service, "calibrate"),
            ):
                service.run_once()
                service.run_once()

            self.assertEqual(scroll_mock.call_count, 0)


if __name__ == "__main__":
    unittest.main()
