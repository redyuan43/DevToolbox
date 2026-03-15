from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wechat_auto_reply.config import AppConfig
from wechat_auto_reply.dbdetect import (
    DbDetectService,
    SqlcipherParams,
    _parse_message_row,
    _partition_new_message_rows,
    active_account_dir,
    changed_snapshot_paths,
    detect_new_target_rows,
    parse_hook_log,
)
from wechat_auto_reply.state import StateStore


class DbDetectTests(unittest.TestCase):
    def test_format_run_once_summary_for_inbound_popup(self) -> None:
        service = DbDetectService(AppConfig(), StateStore(Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()) / "runtime.json", Path(tempfile.mkdtemp()) / "audit.jsonl"))
        summary = service._format_run_once_summary(
            {
                "target_chat_title": "新技术讨论",
                "last_wake_reason": "target_chat_message_candidate",
                "popup_decision": "popup_activated",
                "latest_message_type": "text",
                "latest_message_direction": "inbound",
                "latest_text": "利好良好",
            }
        )
        self.assertIn("检测到新消息并已弹窗", summary)
        self.assertIn("利好良好", summary)

    def test_format_run_once_summary_for_self_message(self) -> None:
        service = DbDetectService(AppConfig(), StateStore(Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()) / "runtime.json", Path(tempfile.mkdtemp()) / "audit.jsonl"))
        summary = service._format_run_once_summary(
            {
                "target_chat_title": "新技术讨论",
                "last_wake_reason": "target_chat_message_candidate",
                "popup_decision": "popup_activated",
                "latest_message_type": "text",
                "latest_text": "自己发的新消息",
                "latest_sender_name": "test2",
            }
        )
        self.assertIn("from=test2", summary)

    def test_parse_hook_log_collects_key_and_cipher_pragmas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "db_hook.jsonl"
            path.write_text(
                '{"event":"sqlite3_key_v2","db_path":"/tmp/message_0.db","sql":"","key_hex":"aabb"}\n'
                '{"event":"sqlite3_exec","db_path":"/tmp/message_0.db","sql":"PRAGMA cipher_page_size = 4096;","key_hex":""}\n',
                encoding="utf-8",
            )
            parsed = parse_hook_log(path)
            self.assertIn("/tmp/message_0.db", parsed)
            self.assertEqual(parsed["/tmp/message_0.db"].key_hex, "aabb")
            self.assertEqual(parsed["/tmp/message_0.db"].pragmas["cipher_page_size"], "4096")

    def test_detect_new_target_rows_uses_high_water_mark(self) -> None:
        class FakeRunner:
            def query(self, db_path: str, params: SqlcipherParams, sql: str) -> list[list[str]]:
                return [["300", "3"], ["200", "2"], ["100", "1"]]

        newest, rows = detect_new_target_rows(
            FakeRunner(),
            "/tmp/message_0.db",
            SqlcipherParams("/tmp/message_0.db", "aabb", {}),
            {
                "message_table": "msg",
                "message_match_column": "talker",
                "message_order_column": "CreateTime",
                "match_value": "room123",
            },
            last_seen="150",
        )
        self.assertEqual(newest, "300")
        self.assertEqual([row["order_value"] for row in rows], ["200", "300"])

    def test_partition_new_message_rows_uses_message_identity(self) -> None:
        mapping = {"message_order_column": "CreateTime"}
        newest, rows = _partition_new_message_rows(
            mapping,
            [
                {"rowid": "3", "CreateTime": "300"},
                {"rowid": "2", "CreateTime": "200"},
                {"rowid": "1", "CreateTime": "100"},
            ],
            "100:1",
        )
        self.assertEqual(newest, "300:3")
        self.assertEqual(rows, [{"rowid": "2", "CreateTime": "200"}, {"rowid": "3", "CreateTime": "300"}])

    def test_parse_message_row_extracts_group_sender_and_text(self) -> None:
        parsed = _parse_message_row(
            {
                "message_order_column": "CreateTime",
                "message_content_column": "Content",
                "message_sender_column": "SenderUserName",
                "message_sender_name_column": "SenderName",
                "message_direction_column": "IsSender",
                "message_type_column": "Type",
            },
            {
                "rowid": "9",
                "CreateTime": "123456",
                "Content": "wxid_testabc:\n利好良好",
                "SenderUserName": "",
                "SenderName": "test2",
                "IsSender": "0",
                "Type": "1",
            },
            self_username="wxid_self",
            target_chat_username="49791584143@chatroom",
        )
        self.assertEqual(parsed["sender_id"], "wxid_testabc")
        self.assertEqual(parsed["sender_name"], "test2")
        self.assertEqual(parsed["message_direction"], "inbound")
        self.assertEqual(parsed["message_type"], "text")
        self.assertEqual(parsed["text"], "利好良好")

    def test_changed_snapshot_paths_detects_delta(self) -> None:
        previous = {
            "/tmp/a": {"size": 1, "mtime_ns": 1},
            "/tmp/b": {"size": 1, "mtime_ns": 1},
        }
        current = {
            "/tmp/a": {"size": 2, "mtime_ns": 1},
            "/tmp/c": {"size": 1, "mtime_ns": 1},
        }
        self.assertEqual(
            changed_snapshot_paths(previous, current),
            ["/tmp/a", "/tmp/b", "/tmp/c"],
        )

    def test_active_account_dir_returns_wxid_directory(self) -> None:
        import subprocess
        import wechat_auto_reply.dbdetect as dbdetect

        class FakeCompleted:
            def __init__(self, stdout: str) -> None:
                self.stdout = stdout

        original_run = subprocess.run

        def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
            if args[:3] == ["pgrep", "-x", "wechat"]:
                return FakeCompleted("123\n")
            if args[:2] == ["lsof", "-p"]:
                return FakeCompleted(
                    "wechat 123 user 123u REG 0,0 0 0 "
                    "/home/dgx/Documents/xwechat_files/wxid_s7tvaxolmw3719_ffb0/db_storage/message/message_0.db\n"
                )
            raise AssertionError(args)

        subprocess.run = fake_run
        try:
            resolved = active_account_dir(Path("/home/dgx/Documents/xwechat_files"))
        finally:
            subprocess.run = original_run
        self.assertEqual(
            resolved,
            Path("/home/dgx/Documents/xwechat_files/wxid_s7tvaxolmw3719_ffb0"),
        )

    def test_run_once_memory_mode_uses_db_and_context_change(self) -> None:
        import wechat_auto_reply.dbdetect as dbdetect

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account_dir = root / "wxid_test"
            message_dir = account_dir / "db_storage" / "message"
            session_dir = account_dir / "db_storage" / "session"
            message_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            (message_dir / "message_0.db").write_text("a", encoding="utf-8")
            (session_dir / "session.db").write_text("a", encoding="utf-8")

            config = AppConfig()
            config.state_dir = root / "state"
            config.state_dir.mkdir(parents=True, exist_ok=True)
            config.db_parse.enabled = True
            config.db_parse.account_dir = str(account_dir)
            config.db_parse.resolver_mode = "memory"
            config.db_parse.memory_probe_use_sudo = False
            config.db_parse.popup_cooldown_ms = 0

            store = StateStore(config.state_dir, config.runtime_state_path, config.audit_log_path)
            service = DbDetectService(config, store)

            original_main_pid = dbdetect.main_wechat_pid
            original_run_memory_probe = dbdetect.run_memory_probe
            probe_payloads = iter(
                [
                    {
                        "target_chat_username": "49791584143@chatroom",
                        "context_hash": "hash-1",
                        "context_strings": ["第一次"],
                        "candidate_usernames": [{"username": "49791584143@chatroom", "count": 1, "min_distance": 1}],
                    },
                    {
                        "target_chat_username": "49791584143@chatroom",
                        "context_hash": "hash-2",
                        "context_strings": ["第二次"],
                        "candidate_usernames": [{"username": "49791584143@chatroom", "count": 1, "min_distance": 1}],
                    },
                ]
            )
            dbdetect.main_wechat_pid = lambda: 123456
            dbdetect.run_memory_probe = lambda *args, **kwargs: next(probe_payloads)
            service._find_target_window = lambda: None  # type: ignore[method-assign]
            try:
                first = service.run_once()
                self.assertEqual(first["last_wake_reason"], "baseline_initialized")
                self.assertEqual(first["target_chat_username"], "49791584143@chatroom")

                (message_dir / "message_0.db").write_text("aa", encoding="utf-8")
                second = service.run_once()
                self.assertEqual(second["last_wake_reason"], "target_chat_db_activity")
                self.assertIn(str(message_dir / "message_0.db"), second["changed_paths"])
            finally:
                dbdetect.main_wechat_pid = original_main_pid
                dbdetect.run_memory_probe = original_run_memory_probe

    def test_run_once_memory_mode_marks_window_missing_for_new_message(self) -> None:
        import wechat_auto_reply.dbdetect as dbdetect

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account_dir = root / "wxid_test"
            message_dir = account_dir / "db_storage" / "message"
            session_dir = account_dir / "db_storage" / "session"
            message_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            (message_dir / "message_0.db").write_text("a", encoding="utf-8")
            (session_dir / "session.db").write_text("a", encoding="utf-8")

            config = AppConfig()
            config.state_dir = root / "state"
            config.state_dir.mkdir(parents=True, exist_ok=True)
            config.db_parse.enabled = True
            config.db_parse.account_dir = str(account_dir)
            config.db_parse.resolver_mode = "memory"
            config.db_parse.memory_probe_use_sudo = False
            config.db_parse.popup_cooldown_ms = 0

            store = StateStore(config.state_dir, config.runtime_state_path, config.audit_log_path)
            service = DbDetectService(config, store)

            original_main_pid = dbdetect.main_wechat_pid
            original_run_memory_probe = dbdetect.run_memory_probe
            dbdetect.main_wechat_pid = lambda: 123456
            probe_payloads = iter(
                [
                    {
                        "target_chat_username": "49791584143@chatroom",
                        "context_hash": "hash-1",
                        "context_strings": ["上下文"],
                        "candidate_usernames": [{"username": "49791584143@chatroom", "count": 1, "min_distance": 1}],
                        "active_sender_id": "wxid_a",
                        "active_sender_name": "test2",
                        "message_candidates": [{"kind": "text", "text": "旧消息", "count": 2}],
                    },
                    {
                        "target_chat_username": "49791584143@chatroom",
                        "context_hash": "hash-2",
                        "context_strings": ["上下文", "新消息"],
                        "candidate_usernames": [{"username": "49791584143@chatroom", "count": 1, "min_distance": 1}],
                        "active_sender_id": "wxid_a",
                        "active_sender_name": "test2",
                        "message_candidates": [
                            {"kind": "text", "text": "旧消息", "count": 2},
                            {"kind": "text", "text": "自己发的新消息", "count": 3},
                        ],
                    },
                ]
            )
            dbdetect.run_memory_probe = lambda *args, **kwargs: next(probe_payloads)
            service._find_target_window = lambda: None  # type: ignore[method-assign]
            try:
                first = service.run_once()
                self.assertEqual(first["last_wake_reason"], "baseline_initialized")

                (message_dir / "message_0.db").write_text("aa", encoding="utf-8")
                second = service.run_once()
                self.assertEqual(second["last_wake_reason"], "target_chat_message_candidate")
                self.assertEqual(second["popup_decision"], "popup_window_missing")
                self.assertEqual(second["latest_text"], "自己发的新消息")
                self.assertEqual(second["latest_sender_name"], "test2")
            finally:
                dbdetect.main_wechat_pid = original_main_pid
                dbdetect.run_memory_probe = original_run_memory_probe

    def test_run_once_memory_mode_activates_popup_for_new_inbound_message(self) -> None:
        import wechat_auto_reply.dbdetect as dbdetect

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account_dir = root / "wxid_test"
            message_dir = account_dir / "db_storage" / "message"
            session_dir = account_dir / "db_storage" / "session"
            message_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            (message_dir / "message_0.db").write_text("a", encoding="utf-8")
            (session_dir / "session.db").write_text("a", encoding="utf-8")

            config = AppConfig()
            config.state_dir = root / "state"
            config.state_dir.mkdir(parents=True, exist_ok=True)
            config.db_parse.enabled = True
            config.db_parse.account_dir = str(account_dir)
            config.db_parse.resolver_mode = "memory"
            config.db_parse.memory_probe_use_sudo = False
            config.db_parse.popup_cooldown_ms = 0

            store = StateStore(config.state_dir, config.runtime_state_path, config.audit_log_path)
            service = DbDetectService(config, store)

            original_main_pid = dbdetect.main_wechat_pid
            original_run_memory_probe = dbdetect.run_memory_probe
            original_activate_window = dbdetect.activate_window
            activated: list[str] = []
            dbdetect.main_wechat_pid = lambda: 123456
            probe_payloads = iter(
                [
                    {
                        "target_chat_username": "49791584143@chatroom",
                        "context_hash": "hash-1",
                        "context_strings": ["上下文"],
                        "candidate_usernames": [{"username": "49791584143@chatroom", "count": 1, "min_distance": 1}],
                        "active_sender_id": "wxid_a",
                        "active_sender_name": "test2",
                        "message_candidates": [{"kind": "text", "text": "旧消息", "count": 2}],
                    },
                    {
                        "target_chat_username": "49791584143@chatroom",
                        "context_hash": "hash-2",
                        "context_strings": ["上下文", "新消息"],
                        "candidate_usernames": [{"username": "49791584143@chatroom", "count": 1, "min_distance": 1}],
                        "active_sender_id": "wxid_a",
                        "active_sender_name": "test2",
                        "message_candidates": [
                            {"kind": "text", "text": "旧消息", "count": 2},
                            {"kind": "text", "text": "别人发的新消息", "count": 4},
                        ],
                    },
                ]
            )
            dbdetect.run_memory_probe = lambda *args, **kwargs: next(probe_payloads)
            dbdetect.activate_window = lambda window_id, window_cfg: activated.append(window_id)
            service._find_target_window = lambda: type("Window", (), {"window_id": "0x9", "title": "新技术讨论", "width": 800, "height": 600})()  # type: ignore[method-assign]
            try:
                first = service.run_once()
                self.assertEqual(first["last_wake_reason"], "baseline_initialized")

                (message_dir / "message_0.db").write_text("aa", encoding="utf-8")
                second = service.run_once()
                self.assertEqual(second["last_wake_reason"], "target_chat_message_candidate")
                self.assertEqual(second["popup_decision"], "popup_activated")
                self.assertEqual(second["latest_sender_name"], "test2")
                self.assertEqual(activated, ["0x9"])
            finally:
                dbdetect.main_wechat_pid = original_main_pid
                dbdetect.run_memory_probe = original_run_memory_probe
                dbdetect.activate_window = original_activate_window

    def test_run_once_memory_mode_activates_popup_on_db_activity_with_sender(self) -> None:
        import wechat_auto_reply.dbdetect as dbdetect

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account_dir = root / "wxid_test"
            message_dir = account_dir / "db_storage" / "message"
            session_dir = account_dir / "db_storage" / "session"
            message_dir.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            (message_dir / "message_0.db").write_text("a", encoding="utf-8")
            (session_dir / "session.db").write_text("a", encoding="utf-8")

            config = AppConfig()
            config.state_dir = root / "state"
            config.state_dir.mkdir(parents=True, exist_ok=True)
            config.db_parse.enabled = True
            config.db_parse.account_dir = str(account_dir)
            config.db_parse.resolver_mode = "memory"
            config.db_parse.memory_probe_use_sudo = False
            config.db_parse.popup_cooldown_ms = 0

            store = StateStore(config.state_dir, config.runtime_state_path, config.audit_log_path)
            service = DbDetectService(config, store)

            original_main_pid = dbdetect.main_wechat_pid
            original_run_memory_probe = dbdetect.run_memory_probe
            original_activate_window = dbdetect.activate_window
            activated: list[str] = []
            dbdetect.main_wechat_pid = lambda: 123456
            probe_payloads = iter(
                [
                    {
                        "target_chat_username": "49791584143@chatroom",
                        "context_hash": "hash-1",
                        "context_strings": ["上下文"],
                        "candidate_usernames": [{"username": "49791584143@chatroom", "count": 1, "min_distance": 1}],
                        "active_sender_id": "wxid_a",
                        "active_sender_name": "test2",
                        "message_candidates": [{"kind": "text", "text": "旧消息", "count": 2}],
                    },
                    {
                        "target_chat_username": "49791584143@chatroom",
                        "context_hash": "hash-1",
                        "context_strings": ["上下文"],
                        "candidate_usernames": [{"username": "49791584143@chatroom", "count": 1, "min_distance": 1}],
                        "active_sender_id": "wxid_a",
                        "active_sender_name": "test2",
                        "message_candidates": [{"kind": "text", "text": "旧消息", "count": 2}],
                    },
                ]
            )
            dbdetect.run_memory_probe = lambda *args, **kwargs: next(probe_payloads)
            dbdetect.activate_window = lambda window_id, window_cfg: activated.append(window_id)
            service._find_target_window = lambda: type("Window", (), {"window_id": "0x9", "title": "新技术讨论", "width": 800, "height": 600})()  # type: ignore[method-assign]
            try:
                first = service.run_once()
                self.assertEqual(first["last_wake_reason"], "baseline_initialized")

                (session_dir / "session.db").write_text("aa", encoding="utf-8")
                second = service.run_once()
                self.assertEqual(second["last_wake_reason"], "db_changed_target_unchanged")
                self.assertEqual(second["popup_decision"], "popup_activated")
                self.assertEqual(second["latest_sender_name"], "test2")
                self.assertEqual(activated, ["0x9"])
            finally:
                dbdetect.main_wechat_pid = original_main_pid
                dbdetect.run_memory_probe = original_run_memory_probe
                dbdetect.activate_window = original_activate_window


if __name__ == "__main__":
    unittest.main()
