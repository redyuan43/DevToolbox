from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wechat_auto_reply.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_merges_reply_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "window:\n"
                "  monitor_mode: standalone\n"
                "guard:\n"
                "  whitelist:\n"
                "    private_chats:\n"
                "      - Alice\n"
                "    group_chats:\n"
                "      - 团队群\n"
                "  context:\n"
                "    strategy: current_screen\n"
                "tools:\n"
                "  send_file:\n"
                "    enabled: true\n"
                "experimental:\n"
                "  history:\n"
                "    enabled: false\n"
                "ollama:\n"
                "  api_format: openai\n"
                "  timeout_s: 45\n"
                "reply:\n"
                "  max_chars: 42\n",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.window.monitor_mode, "standalone")
            self.assertEqual(config.guard.whitelist.private_chats, ["Alice"])
            self.assertEqual(config.guard.whitelist.group_chats, ["团队群"])
            self.assertEqual(config.whitelist, ["Alice", "团队群"])
            self.assertEqual(config.guard.context.strategy, "current_screen")
            self.assertEqual(config.ollama.api_format, "openai")
            self.assertEqual(config.ollama.timeout_s, 45)
            self.assertTrue(config.ollama.disable_thinking)
            self.assertEqual(config.history.max_pages, 1)
            self.assertFalse(config.experimental.history.enabled)
            self.assertEqual(config.downloads.root_dir, "/home/dgx/Documents/xwechat_files")
            self.assertEqual(config.attachments.explicit_send_extensions, ["txt", "md"])
            self.assertEqual(config.db_parse.target_chat_title, "新技术讨论")
            self.assertEqual(config.db_parse.sqlcipher_bin, "/usr/bin/sqlcipher")
            self.assertEqual(config.db_parse.resolver_mode, "auto")
            self.assertTrue(config.db_parse.memory_probe_use_sudo)
            self.assertTrue(config.db_parse.popup_enabled)
            self.assertEqual(config.db_parse.popup_cooldown_ms, 5000)
            self.assertEqual(config.reply.max_chars, 42)
            self.assertIn("验证码", config.reply.blacklist_keywords)

    def test_legacy_top_level_fields_still_map_to_new_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "whitelist:\n"
                "  - Alice\n"
                "history:\n"
                "  max_pages: 1\n"
                "  scroll_mode: page\n"
                "  strategy: truncated_actionable\n",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.guard.whitelist.legacy_titles, ["Alice"])
            self.assertTrue(config.experimental.history.enabled)
            self.assertEqual(config.experimental.history.max_pages, 1)


if __name__ == "__main__":
    unittest.main()
