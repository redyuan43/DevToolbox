from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unittest.mock import patch

from wechat_auto_reply.ollama import (
    OllamaClient,
    extract_json_fragment,
    parse_json_response,
    strip_reasoning_artifacts,
)


class OllamaParsingTests(unittest.TestCase):
    def test_extracts_json_from_fenced_block(self) -> None:
        text = 'before\n```json\n{"ok": true, "items": [1, 2]}\n```\nafter'
        self.assertEqual(
            parse_json_response(text),
            {"ok": True, "items": [1, 2]},
        )

    def test_extracts_json_array(self) -> None:
        text = 'result: [{"chat_name":"Alice","unread":true}]'
        self.assertEqual(
            extract_json_fragment(text),
            '[{"chat_name":"Alice","unread":true}]',
        )

    def test_openai_compatible_generate_returns_content_text(self) -> None:
        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "<think>ignored</think>\n{\"ok\": true}",
                            }
                        }
                    ]
                }

        client = OllamaClient(
            "http://localhost:1234/v1",
            api_format="openai",
            timeout_s=1,
            disable_thinking=True,
        )
        with patch("wechat_auto_reply.ollama.requests.post", return_value=FakeResponse()) as post_mock:
            text = client.generate(model="demo", prompt="Return JSON only", temperature=0.0)

        self.assertIn('{"ok": true}', text)
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
        self.assertFalse(payload["enableThinking"])
        self.assertFalse(payload["reasoning"])
        self.assertIn("/chat/completions", post_mock.call_args.kwargs["url"] if "url" in post_mock.call_args.kwargs else post_mock.call_args.args[0])

    def test_strip_reasoning_artifacts_prefers_final_reply_marker(self) -> None:
        text = (
            "Thinking Process:\n\n"
            "1. 分析用户意图。\n"
            "2. 生成回复。\n\n"
            "FINAL_REPLY: 好的，收到。"
        )
        self.assertEqual(strip_reasoning_artifacts(text), "好的，收到。")


if __name__ == "__main__":
    unittest.main()
