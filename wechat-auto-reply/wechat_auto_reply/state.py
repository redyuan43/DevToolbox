from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Roi


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(slots=True)
class Calibration:
    monitor_mode: str
    calibration_key: str
    window_id: str
    window_title: str
    geometry: dict[str, int]
    rois: dict[str, Roi]
    updated_at_ms: int

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Calibration":
        return cls(
            monitor_mode=str(data.get("monitor_mode", "main")),
            calibration_key=str(data["calibration_key"]),
            window_id=str(data["window_id"]),
            window_title=str(data["window_title"]),
            geometry={k: int(v) for k, v in data["geometry"].items()},
            rois={k: Roi.from_mapping(v) for k, v in data["rois"].items()},
            updated_at_ms=int(data["updated_at_ms"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "monitor_mode": self.monitor_mode,
            "calibration_key": self.calibration_key,
            "window_id": self.window_id,
            "window_title": self.window_title,
            "geometry": self.geometry,
            "rois": {k: v.to_mapping() for k, v in self.rois.items()},
            "updated_at_ms": self.updated_at_ms,
        }


@dataclass(slots=True)
class RuntimeState:
    seen_messages: dict[str, int] = field(default_factory=dict)
    paused_chats: dict[str, int] = field(default_factory=dict)
    recent_turns: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    window_observations: dict[str, dict[str, Any]] = field(default_factory=dict)
    outbound_text_hashes: dict[str, dict[str, int]] = field(default_factory=dict)
    outbound_file_fingerprints: dict[str, dict[str, int]] = field(default_factory=dict)
    downloaded_file_events: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    last_message_items: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    recent_downloads: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    recent_sent_files: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    db_detector_state: dict[str, Any] = field(default_factory=dict)
    last_status: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RuntimeState":
        return cls(
            seen_messages={str(k): int(v) for k, v in data.get("seen_messages", {}).items()},
            paused_chats={str(k): int(v) for k, v in data.get("paused_chats", {}).items()},
            recent_turns={
                str(k): list(v)
                for k, v in data.get("recent_turns", {}).items()
            },
            window_observations={
                str(k): dict(v)
                for k, v in data.get("window_observations", {}).items()
            },
            outbound_text_hashes={
                str(k): {str(key): int(value) for key, value in dict(v).items()}
                for k, v in data.get("outbound_text_hashes", {}).items()
            },
            outbound_file_fingerprints={
                str(k): {str(key): int(value) for key, value in dict(v).items()}
                for k, v in data.get("outbound_file_fingerprints", {}).items()
            },
            downloaded_file_events={
                str(k): {str(key): dict(value) for key, value in dict(v).items()}
                for k, v in data.get("downloaded_file_events", {}).items()
            },
            last_message_items={
                str(k): list(v)
                for k, v in data.get("last_message_items", {}).items()
            },
            recent_downloads={
                str(k): list(v)
                for k, v in data.get("recent_downloads", {}).items()
            },
            recent_sent_files={
                str(k): list(v)
                for k, v in data.get("recent_sent_files", {}).items()
            },
            db_detector_state=dict(data.get("db_detector_state", {})),
            last_status=dict(data.get("last_status", {})),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "seen_messages": self.seen_messages,
            "paused_chats": self.paused_chats,
            "recent_turns": self.recent_turns,
            "window_observations": self.window_observations,
            "outbound_text_hashes": self.outbound_text_hashes,
            "outbound_file_fingerprints": self.outbound_file_fingerprints,
            "downloaded_file_events": self.downloaded_file_events,
            "last_message_items": self.last_message_items,
            "recent_downloads": self.recent_downloads,
            "recent_sent_files": self.recent_sent_files,
            "db_detector_state": self.db_detector_state,
            "last_status": self.last_status,
        }


class StateStore:
    def __init__(self, state_dir: Path, runtime_state_path: Path, audit_log_path: Path) -> None:
        self.state_dir = state_dir
        self.runtime_state_path = runtime_state_path
        self.audit_log_path = audit_log_path
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.runtime = self._load_runtime()

    def _load_runtime(self) -> RuntimeState:
        if not self.runtime_state_path.exists():
            return RuntimeState()
        data = json.loads(self.runtime_state_path.read_text(encoding="utf-8"))
        return RuntimeState.from_mapping(data)

    def save(self) -> None:
        self.runtime_state_path.write_text(
            json.dumps(self.runtime.to_mapping(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_calibration(self, path: Path, calibration: Calibration) -> None:
        path.write_text(
            json.dumps(calibration.to_mapping(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_calibration(self, path: Path) -> Calibration | None:
        if not path.exists():
            return None
        return Calibration.from_mapping(json.loads(path.read_text(encoding="utf-8")))

    def append_audit(self, payload: dict[str, Any]) -> None:
        payload = {"ts_ms": _now_ms(), **payload}
        with self.audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def mark_seen(self, message_hash: str) -> None:
        self.runtime.seen_messages[message_hash] = _now_ms()
        self._trim_seen()

    def has_seen(self, message_hash: str) -> bool:
        return message_hash in self.runtime.seen_messages

    def _trim_seen(self) -> None:
        if len(self.runtime.seen_messages) <= 2000:
            return
        items = sorted(self.runtime.seen_messages.items(), key=lambda item: item[1], reverse=True)
        self.runtime.seen_messages = dict(items[:2000])

    def pause_chat_until(self, chat_name: str, until_ms: int) -> None:
        self.runtime.paused_chats[chat_name] = until_ms

    def chat_paused(self, chat_name: str) -> bool:
        until_ms = self.runtime.paused_chats.get(chat_name)
        if until_ms is None:
            return False
        if until_ms <= _now_ms():
            self.runtime.paused_chats.pop(chat_name, None)
            return False
        return True

    def add_turn(self, chat_name: str, role: str, text: str) -> None:
        turns = self.runtime.recent_turns.setdefault(chat_name, [])
        turns.append({"role": role, "text": text})
        self.runtime.recent_turns[chat_name] = turns[-6:]

    def get_recent_turns(self, chat_name: str) -> list[dict[str, str]]:
        return list(self.runtime.recent_turns.get(chat_name, []))

    def get_window_observation(self, chat_name: str) -> dict[str, Any]:
        return dict(self.runtime.window_observations.get(chat_name, {}))

    def update_window_observation(self, chat_name: str, updates: dict[str, Any]) -> None:
        current = dict(self.runtime.window_observations.get(chat_name, {}))
        current.update(updates)
        self.runtime.window_observations[chat_name] = current

    def remember_outbound_text(self, chat_name: str, fingerprint: str) -> None:
        bucket = self.runtime.outbound_text_hashes.setdefault(chat_name, {})
        bucket[fingerprint] = _now_ms()
        self.runtime.outbound_text_hashes[chat_name] = self._trim_bucket(bucket)

    def outbound_text_seen(self, chat_name: str, fingerprint: str) -> bool:
        return fingerprint in self.runtime.outbound_text_hashes.get(chat_name, {})

    def remember_outbound_file(self, chat_name: str, fingerprint: str) -> None:
        bucket = self.runtime.outbound_file_fingerprints.setdefault(chat_name, {})
        bucket[fingerprint] = _now_ms()
        self.runtime.outbound_file_fingerprints[chat_name] = self._trim_bucket(bucket)

    def outbound_file_seen(self, chat_name: str, fingerprint: str) -> bool:
        return fingerprint in self.runtime.outbound_file_fingerprints.get(chat_name, {})

    def remember_download(self, chat_name: str, item_hash: str, saved_path: str) -> None:
        bucket = self.runtime.downloaded_file_events.setdefault(chat_name, {})
        bucket[item_hash] = {
            "saved_path": saved_path,
            "ts_ms": _now_ms(),
        }
        recent = self.runtime.recent_downloads.setdefault(chat_name, [])
        recent.append({"saved_path": saved_path, "item_hash": item_hash, "ts_ms": _now_ms()})
        self.runtime.downloaded_file_events[chat_name] = self._trim_mapping_bucket(bucket)
        self.runtime.recent_downloads[chat_name] = recent[-10:]

    def download_seen(self, chat_name: str, item_hash: str) -> bool:
        return item_hash in self.runtime.downloaded_file_events.get(chat_name, {})

    def set_last_message_items(self, chat_name: str, items: list[dict[str, Any]]) -> None:
        self.runtime.last_message_items[chat_name] = items[:20]

    def append_recent_sent_file(self, chat_name: str, path: str, fingerprint: str) -> None:
        recent = self.runtime.recent_sent_files.setdefault(chat_name, [])
        recent.append({"path": path, "fingerprint": fingerprint, "ts_ms": _now_ms()})
        self.runtime.recent_sent_files[chat_name] = recent[-10:]

    def _trim_bucket(self, bucket: dict[str, int], limit: int = 200) -> dict[str, int]:
        if len(bucket) <= limit:
            return dict(bucket)
        items = sorted(bucket.items(), key=lambda item: item[1], reverse=True)
        return dict(items[:limit])

    def _trim_mapping_bucket(
        self,
        bucket: dict[str, dict[str, Any]],
        limit: int = 200,
    ) -> dict[str, dict[str, Any]]:
        if len(bucket) <= limit:
            return dict(bucket)
        items = sorted(
            bucket.items(),
            key=lambda item: int(item[1].get("ts_ms", 0)),
            reverse=True,
        )
        return dict(items[:limit])
