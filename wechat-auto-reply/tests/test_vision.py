from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw

from wechat_auto_reply.vision import MessageItem, _apply_color_direction_heuristics


class VisionTests(unittest.TestCase):
    def test_green_bubble_is_forced_to_outbound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.png"
            image = Image.new("RGB", (100, 100), (240, 240, 240))
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 10, 60, 40), fill=(180, 225, 200))
            image.save(path)

            item = MessageItem(
                kind="text",
                direction="inbound",
                text_or_filename="hello",
                confidence=0.9,
                bbox={"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.3},
                from_self=False,
            )
            _apply_color_direction_heuristics(path, [item])
            self.assertEqual(item.direction, "outbound")
            self.assertTrue(item.from_self)


if __name__ == "__main__":
    unittest.main()
