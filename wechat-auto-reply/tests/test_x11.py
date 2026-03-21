from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wechat_auto_reply.config import WindowConfig
from wechat_auto_reply.x11 import discover_standalone_windows, parse_wechat_windows


SAMPLE_TREE = """
     0x6200011 "Weixin": ("wechat" "wechat") 1015x721+263+68  +263+68
     0x62002a1 "Ivan": ("wechat" "wechat") 598x640+158+136  +158+136
     0x62002a2 "Jing": ("wechat" "wechat") 598x640+200+160  +200+160
     0x62002a3 "Other": ("wechat" "wechat") 500x400+300+220  +300+220
     0x62002a4 "Open": ("wechat" "wechat") 621x415+14+49  +2716+537
"""


class X11WindowDiscoveryTests(unittest.TestCase):
    def test_parse_wechat_windows(self) -> None:
        windows = parse_wechat_windows(SAMPLE_TREE, "wechat")
        self.assertEqual([item.title for item in windows], ["Weixin", "Ivan", "Jing", "Other", "Open"])
        chooser = next(item for item in windows if item.title == "Open")
        self.assertEqual((chooser.x, chooser.y), (2716, 537))

    def test_discover_standalone_windows_filters_main_and_whitelist(self) -> None:
        config = WindowConfig(
            monitor_mode="standalone",
            class_name="wechat",
            main_title_regex=r"^(Weixin|微信)$",
        )

        def fake_list(_: WindowConfig):
            return parse_wechat_windows(SAMPLE_TREE, "wechat")

        from wechat_auto_reply import x11

        original = x11.list_wechat_windows
        x11.list_wechat_windows = fake_list
        try:
            windows = discover_standalone_windows(config, ["Ivan", "Jing"])
        finally:
            x11.list_wechat_windows = original

        self.assertEqual([item.title for item in windows], ["Ivan", "Jing"])


if __name__ == "__main__":
    unittest.main()
