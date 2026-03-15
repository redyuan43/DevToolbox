from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig, Roi
from .ollama import OllamaClient, parse_json_response


@dataclass(slots=True)
class ChatCandidate:
    chat_name: str
    unread: bool
    is_private: bool
    confidence: float
    click_y_ratio: float


@dataclass(slots=True)
class MessageItem:
    kind: str
    direction: str
    text_or_filename: str
    confidence: float
    bbox: dict[str, float]
    downloadable: bool = False
    truncated: bool = False
    from_self: bool | None = None

    @property
    def item_hash(self) -> str:
        bbox_key = ",".join(
            f"{key}:{self.bbox.get(key, 0.0):.3f}"
            for key in ("x", "y", "width", "height")
        )
        normalized = (
            f"{self.kind.strip().lower()}::{self.direction.strip().lower()}::"
            f"{self.text_or_filename.strip()}::{bbox_key}"
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @property
    def center_ratio(self) -> tuple[float, float]:
        x = self.bbox.get("x", 0.5) + self.bbox.get("width", 0.0) / 2.0
        y = self.bbox.get("y", 0.5) + self.bbox.get("height", 0.0) / 2.0
        return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "direction": self.direction,
            "text_or_filename": self.text_or_filename,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "downloadable": self.downloadable,
            "truncated": self.truncated,
            "from_self": self.from_self,
            "item_hash": self.item_hash,
        }


@dataclass(slots=True)
class ConversationObservation:
    chat_name: str
    latest_inbound_text: str
    direction: str
    confidence: float
    input_has_text: bool = False
    send_button_enabled: bool = False
    items: list[MessageItem] | None = None

    @property
    def message_hash(self) -> str:
        normalized = (
            f"{self.chat_name.strip().lower()}::{self.direction.strip().lower()}::"
            f"{self.latest_inbound_text.strip()}"
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class WindowObservation:
    chat_name: str
    input_has_text: bool
    send_button_enabled: bool
    items: list[MessageItem]

    @property
    def latest_item(self) -> MessageItem | None:
        for item in reversed(self.items):
            if item.kind != "system":
                return item
        return None


def _chat_list_prompt(whitelist: list[str]) -> str:
    return (
        "You are reading a WeChat chat list screenshot.\n"
        "Return JSON only.\n"
        "Schema: {\"items\":[{\"chat_name\":\"...\",\"unread\":true,"
        "\"is_private\":true,\"confidence\":0.0,\"click_y_ratio\":0.0}]}\n"
        "Only include visible rows with a readable chat name.\n"
        "click_y_ratio must be between 0 and 1 and indicate the vertical center of the row inside the screenshot.\n"
        f"Known whitelist contacts: {whitelist}.\n"
        "If a row looks like a group, set is_private=false."
    )


def _conversation_prompt() -> str:
    return (
        "You are reading a WeChat conversation screenshot.\n"
        "Return JSON only.\n"
        "Schema: {\"latest_inbound_text\":\"...\",\"direction\":\"inbound|outbound|unknown\",\"confidence\":0.0}\n"
        "Extract only the latest visible inbound message from the other person.\n"
        "If the latest visible message is from self or unclear, use direction=unknown."
    )


def _standalone_window_prompt(chat_name: str) -> str:
    return (
        "You are reading a standalone WeChat chat window screenshot.\n"
        "Return JSON only.\n"
        "Schema: {\"input_has_text\":false,\"send_button_enabled\":false,"
        "\"items\":[{\"kind\":\"text|file|image|system\",\"direction\":\"inbound|outbound|unknown\","
        "\"text_or_filename\":\"...\",\"confidence\":0.0,"
        "\"bbox\":{\"x\":0.0,\"y\":0.0,\"width\":0.0,\"height\":0.0},"
        "\"downloadable\":false,\"truncated\":false,\"from_self\":false}]}\n"
        f"The chat title is {chat_name!r}.\n"
        "Only read the visible conversation transcript area between the title bar and the input toolbar.\n"
        "Ignore side chrome, menus, title bar text, terminal windows behind it, and the bottom tool icons.\n"
        "Use kind=text for normal chat bubbles, kind=file for visible file cards/documents, kind=image for visible image/photo thumbnails, kind=system for timestamps or notices.\n"
        "Use direction=outbound for self messages and direction=inbound for other-party messages.\n"
        "Do not rely only on left/right position in group chats. Prefer bubble color and sender presentation: green or tinted self bubbles are outbound even if they are not on the far right; white/gray bubbles from other people are inbound.\n"
        "If a message or file card is partially cut off or obviously continues off screen, set truncated=true.\n"
        "bbox values are normalized ratios between 0 and 1 relative to the full screenshot.\n"
        "Return items in top-to-bottom visible order."
    )


def _verify_prompt(target_text: str, target_kind: str) -> str:
    return (
        "You are verifying whether a just-sent item is visible in a WeChat conversation screenshot.\n"
        "Return JSON only.\n"
        f"Schema: {{\"visible\": true, \"confidence\": 0.0}}.\n"
        f"The target kind is {target_kind!r}.\n"
        f"The target text or filename to look for is: {target_text!r}."
    )


def _locate_attachment_prompt() -> str:
    return (
        "You are locating the file attachment button inside a standalone WeChat chat window screenshot.\n"
        "Return JSON only.\n"
        "Schema: {\"found\":true,\"x_ratio\":0.0,\"y_ratio\":0.0,\"confidence\":0.0}.\n"
        "Find the folder/file attachment icon in the bottom toolbar above the input box."
    )


def _locate_context_action_prompt(action_label: str) -> str:
    return (
        "You are locating a context-menu action inside a WeChat screenshot after a right click.\n"
        "Return JSON only.\n"
        "Schema: {\"found\":true,\"x_ratio\":0.0,\"y_ratio\":0.0,\"confidence\":0.0}.\n"
        f"Find the visible menu item whose label best matches {action_label!r}."
    )


def _normalize_bbox(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
    box: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        try:
            box[key] = max(0.0, min(1.0, float(raw.get(key, 0.0))))
        except (TypeError, ValueError):
            box[key] = 0.0
    return box


def _average_rgb_for_bbox(screenshot_path: Path, bbox: dict[str, float]) -> tuple[float, float, float] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        image = Image.open(screenshot_path).convert("RGB")
    except OSError:
        return None
    left = int(max(0.0, min(1.0, bbox.get("x", 0.0))) * image.width)
    top = int(max(0.0, min(1.0, bbox.get("y", 0.0))) * image.height)
    right = int(max(0.0, min(1.0, bbox.get("x", 0.0) + bbox.get("width", 0.0))) * image.width)
    bottom = int(max(0.0, min(1.0, bbox.get("y", 0.0) + bbox.get("height", 0.0))) * image.height)
    if right - left < 4 or bottom - top < 4:
        return None
    crop = image.crop((left, top, right, bottom))
    pixels = list(crop.getdata())
    if not pixels:
        return None
    return tuple(sum(pixel[index] for pixel in pixels) / len(pixels) for index in range(3))


def _apply_color_direction_heuristics(screenshot_path: Path, items: list[MessageItem]) -> None:
    for item in items:
        if item.kind == "system":
            continue
        avg_rgb = _average_rgb_for_bbox(screenshot_path, item.bbox)
        if not avg_rgb:
            continue
        red, green, blue = avg_rgb
        if green >= red + 15.0 and green >= blue + 10.0 and green >= 150.0:
            item.direction = "outbound"
            item.from_self = True


def analyze_chat_list(
    client: OllamaClient,
    config: AppConfig,
    screenshot_path: Path,
) -> list[ChatCandidate]:
    raw = client.generate(
        model=config.ollama.vision_model,
        prompt=_chat_list_prompt(config.whitelist),
        images=[screenshot_path],
        temperature=0.1,
    )
    data = parse_json_response(raw)
    items = data.get("items", []) if isinstance(data, dict) else []
    candidates: list[ChatCandidate] = []
    for item in items:
        try:
            candidates.append(
                ChatCandidate(
                    chat_name=str(item["chat_name"]).strip(),
                    unread=bool(item["unread"]),
                    is_private=bool(item["is_private"]),
                    confidence=float(item["confidence"]),
                    click_y_ratio=float(item["click_y_ratio"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return candidates


def analyze_conversation(
    client: OllamaClient,
    config: AppConfig,
    screenshot_path: Path,
    chat_name: str,
) -> ConversationObservation:
    raw = client.generate(
        model=config.ollama.vision_model,
        prompt=_conversation_prompt(),
        images=[screenshot_path],
        temperature=0.1,
    )
    data = parse_json_response(raw)
    return ConversationObservation(
        chat_name=chat_name,
        latest_inbound_text=str(data.get("latest_inbound_text", "")).strip(),
        direction=str(data.get("direction", "unknown")).strip(),
        confidence=float(data.get("confidence", 0.0)),
    )


def analyze_standalone_window(
    client: OllamaClient,
    config: AppConfig,
    screenshot_path: Path,
    chat_name: str,
) -> WindowObservation:
    raw = client.generate(
        model=config.ollama.vision_model,
        prompt=_standalone_window_prompt(chat_name),
        images=[screenshot_path],
        temperature=0.0,
    )
    data = parse_json_response(raw)
    raw_items = data.get("items", []) if isinstance(data, dict) else []
    items: list[MessageItem] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            items.append(
                MessageItem(
                    kind=str(item.get("kind", "text")).strip(),
                    direction=str(item.get("direction", "unknown")).strip(),
                    text_or_filename=str(item.get("text_or_filename", "")).strip(),
                    confidence=float(item.get("confidence", 0.0)),
                    bbox=_normalize_bbox(item.get("bbox")),
                    downloadable=bool(item.get("downloadable")),
                    truncated=bool(item.get("truncated")),
                    from_self=item.get("from_self"),
                )
            )
        except (TypeError, ValueError):
            continue
    _apply_color_direction_heuristics(screenshot_path, items)
    return WindowObservation(
        chat_name=chat_name,
        input_has_text=bool(data.get("input_has_text")),
        send_button_enabled=bool(data.get("send_button_enabled")),
        items=items,
    )


def verify_visible(
    client: OllamaClient,
    config: AppConfig,
    screenshot_path: Path,
    target_text: str,
    *,
    target_kind: str = "text",
) -> tuple[bool, float]:
    raw = client.generate(
        model=config.ollama.vision_model,
        prompt=_verify_prompt(target_text, target_kind),
        images=[screenshot_path],
        temperature=0.0,
    )
    data = parse_json_response(raw)
    return bool(data.get("visible")), float(data.get("confidence", 0.0))


def verify_reply_visible(
    client: OllamaClient,
    config: AppConfig,
    screenshot_path: Path,
    reply_text: str,
) -> tuple[bool, float]:
    return verify_visible(
        client,
        config,
        screenshot_path,
        reply_text,
        target_kind="reply_text",
    )


def locate_attachment_button(
    client: OllamaClient,
    config: AppConfig,
    screenshot_path: Path,
) -> tuple[bool, float, float, float]:
    raw = client.generate(
        model=config.ollama.vision_model,
        prompt=_locate_attachment_prompt(),
        images=[screenshot_path],
        temperature=0.0,
    )
    data = parse_json_response(raw)
    return (
        bool(data.get("found")),
        float(data.get("x_ratio", 0.0)),
        float(data.get("y_ratio", 0.0)),
        float(data.get("confidence", 0.0)),
    )


def locate_context_action(
    client: OllamaClient,
    config: AppConfig,
    screenshot_path: Path,
    action_label: str,
) -> tuple[bool, float, float, float]:
    raw = client.generate(
        model=config.ollama.vision_model,
        prompt=_locate_context_action_prompt(action_label),
        images=[screenshot_path],
        temperature=0.0,
    )
    data = parse_json_response(raw)
    return (
        bool(data.get("found")),
        float(data.get("x_ratio", 0.0)),
        float(data.get("y_ratio", 0.0)),
        float(data.get("confidence", 0.0)),
    )


def pick_candidate(
    candidates: list[ChatCandidate],
    config: AppConfig,
) -> ChatCandidate | None:
    whitelist = {item.strip() for item in config.whitelist}
    filtered = [
        item
        for item in candidates
        if item.unread
        and item.chat_name in whitelist
        and item.is_private
        and item.confidence >= config.safety.require_confidence
    ]
    if not filtered:
        return None
    return sorted(filtered, key=lambda item: item.confidence, reverse=True)[0]


def click_point_for_candidate(roi: Roi, candidate: ChatCandidate) -> tuple[int, int]:
    x = roi.x + max(20, int(roi.width * 0.5))
    y = roi.y + int(max(0.05, min(0.95, candidate.click_y_ratio)) * roi.height)
    return x, y
