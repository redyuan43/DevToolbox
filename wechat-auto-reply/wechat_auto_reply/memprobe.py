from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator


CHAT_USERNAME_RE = re.compile(rb"(?:[0-9]{6,}@chatroom|wxid_[0-9A-Za-z_]+|gh_[0-9A-Za-z_]+)")
CHAT_USERNAME_TEXT_RE = re.compile(r"(?:[0-9]{6,}@chatroom|wxid_[0-9A-Za-z_]+|gh_[0-9A-Za-z_]+)")
TEXT_RE = re.compile(r"[A-Za-z0-9_@:/.\-\u4e00-\u9fff\[\]（）()：，。！？、'\"“”‘’%+#&= ]{4,}")
FILENAME_RE = re.compile(r".+\.(?:zip|7z|rar|txt|md|pdf|doc|docx|xls|xlsx|ppt|pptx|png|jpe?g|gif|bmp|webp|mp3|wav|m4a|mp4|mov)$", re.IGNORECASE)
SYSTEM_MESSAGE_RE = re.compile(r"撤回了一条消息|加入了群聊|拍了拍|sysmsg|revokemsg", re.IGNORECASE)
IMAGE_MESSAGE_RE = re.compile(r"\[图片\]|\bimage\b|\bphoto\b", re.IGNORECASE)
TECHNICAL_TOKEN_RE = re.compile(
    r"(?:mmkv|message_fts|sqlite|sqlcipher|Content-Length|db_storage|session\.db|message_0\.db|"
    r"coroutine|QString|QByteArray|Noto Sans|/home/|/org/freedesktop|wxworker|http://|https://|"
    r"resourceid/|visible=0|long_polling|cgi-bin/|update\.data|conf\.avail|conf\.d/|"
    r"monospace|sans-serif|Persian_|AR PL |font|title=|square|serif|fantasy|activity|path d=|"
    r"xml version|appmsg|cdnthumb|aeskey|_timestamp|appattach|msgsource|/url|/type|/title|CDATA)",
    re.IGNORECASE,
)


def _iter_regions(pid: int) -> Iterator[tuple[int, int]]:
    maps_path = Path(f"/proc/{pid}/maps")
    for raw in maps_path.read_text(encoding="utf-8").splitlines():
        parts = raw.split(maxsplit=5)
        if len(parts) < 2:
            continue
        addr_range, perms = parts[0], parts[1]
        if "r" not in perms or "w" not in perms:
            continue
        start, end = [int(value, 16) for value in addr_range.split("-")]
        size = end - start
        if size <= 0 or size > 64 * 1024 * 1024:
            continue
        yield start, end


def _read_region(mem_path: Path, start: int, end: int) -> bytes:
    with mem_path.open("rb", buffering=0) as handle:
        handle.seek(start)
        return handle.read(end - start)


def extract_context_strings(chunk: bytes, limit: int = 20) -> list[str]:
    text = chunk.decode("utf-8", "ignore")
    seen: set[str] = set()
    results: list[str] = []
    for match in TEXT_RE.finditer(text):
        candidate = re.sub(r"\s+", " ", match.group(0)).strip(" \x00")
        if len(candidate) < 4 or len(candidate) > 220:
            continue
        if candidate in seen:
            continue
        if candidate.startswith("/etc/"):
            continue
        if "Noto Sans" in candidate or "conf.avail" in candidate or "conf.d/" in candidate:
            continue
        if candidate.startswith("http") and len(candidate) > 160:
            continue
        if not any(
            char.isdigit()
            or char.isalpha()
            or "\u4e00" <= char <= "\u9fff"
            or char in "[]（）()：，。！？、'\"“”‘’%+#&=@:/.-_ "
            for char in candidate
        ):
            continue
        seen.add(candidate)
        results.append(candidate)
        if len(results) >= limit:
            break
    return results


def _normalize_candidate(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \x00")


def _tail_after_token(value: str, token: str) -> str | None:
    index = value.find(token)
    if index < 0:
        return None
    tail = value[index + len(token):]
    tail = re.sub(r"^[^A-Za-z0-9\u4e00-\u9fff]+", "", tail)
    if not tail:
        return None
    tail = re.split(r"(?:wxid_[0-9A-Za-z_]+|gh_[0-9A-Za-z_]+|[0-9]{6,}@chatroom)", tail, maxsplit=1)[0]
    tail = re.split(r"(?:https?://|/home/|db_storage|message_fts|session\.db|message_0\.db)", tail, maxsplit=1)[0]
    return _normalize_candidate(tail[:120]) or None


def _looks_technical(value: str) -> bool:
    if not value:
        return True
    if TECHNICAL_TOKEN_RE.search(value):
        return True
    if CHAT_USERNAME_TEXT_RE.search(value):
        return True
    if value.startswith(("wxid_", "gh_")) or "@chatroom" in value:
        return True
    if value.startswith("&"):
        return True
    if value in {"title", "type", "url", "desc", "content"}:
        return True
    if value.count("/") >= 2 and not FILENAME_RE.fullmatch(value):
        return True
    compact = value.replace(" ", "")
    if len(compact) >= 12 and re.fullmatch(r"[0-9A-Fa-f]+", compact):
        return True
    return False


def _clean_sender_name(value: str, chat_title: str, target_chat_username: str) -> str | None:
    candidate = _normalize_candidate(value)
    if not candidate or len(candidate) < 2 or len(candidate) > 40:
        return None
    if candidate == chat_title or candidate == target_chat_username:
        return None
    if _looks_technical(candidate):
        return None
    if FILENAME_RE.fullmatch(candidate) or SYSTEM_MESSAGE_RE.search(candidate):
        return None
    return candidate


def _classify_message_kind(value: str) -> str:
    if FILENAME_RE.fullmatch(value):
        return "file"
    if SYSTEM_MESSAGE_RE.search(value):
        return "system"
    if IMAGE_MESSAGE_RE.search(value):
        return "image"
    return "text"


def _clean_message_text(
    value: str,
    *,
    chat_title: str,
    target_chat_username: str,
    excluded_names: set[str],
) -> tuple[str | None, str]:
    candidate = _normalize_candidate(value)
    if not candidate or len(candidate) < 2 or len(candidate) > 120:
        return None, "unknown"
    if candidate == chat_title or candidate == target_chat_username:
        return None, "unknown"
    if candidate in excluded_names:
        return None, "unknown"
    if _looks_technical(candidate):
        return None, "unknown"
    kind = _classify_message_kind(candidate)
    if kind == "system":
        return None, kind
    return candidate, kind


def _search_hits(pid: int, needles: list[tuple[str, bytes]], max_hits: int, context_bytes: int = 4096) -> list[dict[str, Any]]:
    mem_path = Path(f"/proc/{pid}/mem")
    hits: list[dict[str, Any]] = []
    for start, end in _iter_regions(pid):
        try:
            region = _read_region(mem_path, start, end)
        except OSError:
            continue
        for encoding, needle in needles:
            search_offset = 0
            while len(hits) < max_hits:
                position = region.find(needle, search_offset)
                if position < 0:
                    break
                context_start = max(0, position - context_bytes)
                context_end = min(len(region), position + context_bytes)
                context = region[context_start:context_end]
                usernames: list[dict[str, Any]] = []
                for match in CHAT_USERNAME_RE.finditer(context):
                    username = match.group(0).decode("utf-8", "ignore")
                    distance = abs((context_start + match.start()) - position)
                    usernames.append({"username": username, "distance": distance})
                hits.append(
                    {
                        "address": hex(start + position),
                        "encoding": encoding,
                        "candidate_usernames": usernames,
                        "context_strings": extract_context_strings(context, limit=40),
                    }
                )
                search_offset = position + max(1, len(needle))
            if len(hits) >= max_hits:
                break
        if len(hits) >= max_hits:
            break
    return hits


def _ordered_sender_candidates(
    hits: list[dict[str, Any]],
    *,
    chat_title: str,
    target_chat_username: str,
    excluded_usernames: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, int]]]]:
    excluded_usernames = excluded_usernames or set()
    sender_counts: dict[str, int] = defaultdict(int)
    sender_min_distance: dict[str, int] = {}
    sender_name_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for hit in hits:
        strings = [str(item) for item in hit.get("context_strings") or []]
        for idx, raw in enumerate(strings):
            usernames = [
                username
                for username in CHAT_USERNAME_TEXT_RE.findall(raw)
                if username != target_chat_username and username not in excluded_usernames
            ]
            for username in usernames:
                sender_counts[username] += 1
                matching_distances = [
                    int(item.get("distance", 10**9))
                    for item in hit.get("candidate_usernames", [])
                    if str(item.get("username")) == username
                ]
                sender_min_distance[username] = min(
                    sender_min_distance.get(username, 10**9),
                    min(matching_distances) if matching_distances else 10**9,
                )
                inline_name = _tail_after_token(raw, username)
                cleaned_inline = _clean_sender_name(inline_name or "", chat_title, target_chat_username)
                if cleaned_inline:
                    sender_name_counts[username][cleaned_inline] += 8
                if idx + 1 < len(strings):
                    neighbor_name = _clean_sender_name(strings[idx + 1], chat_title, target_chat_username)
                    if neighbor_name:
                        sender_name_counts[username][neighbor_name] += 10

    ordered_senders = sorted(
        (
            {
                "username": username,
                "count": int(sender_counts[username]),
                "min_distance": int(sender_min_distance.get(username, 10**9)),
            }
            for username in sender_counts
        ),
        key=lambda item: (-item["count"], item["min_distance"], item["username"]),
    )
    ordered_names = {
        username: sorted(
            (
                {"name": name, "count": int(count)}
                for name, count in names.items()
            ),
            key=lambda item: (-item["count"], item["name"]),
        )
        for username, names in sender_name_counts.items()
    }
    return ordered_senders, ordered_names


def _collect_message_candidates(
    hits: list[dict[str, Any]],
    *,
    chat_title: str,
    target_chat_username: str,
    active_sender_id: str | None,
    excluded_names: set[str],
) -> list[dict[str, Any]]:
    scored: dict[tuple[str, str], int] = defaultdict(int)
    for hit in hits:
        strings = [str(item) for item in hit.get("context_strings") or []]
        for raw in strings:
            inline_tail = _tail_after_token(raw, target_chat_username)
            if inline_tail:
                text, kind = _clean_message_text(
                    inline_tail,
                    chat_title=chat_title,
                    target_chat_username=target_chat_username,
                    excluded_names=excluded_names,
                )
                if text:
                    scored[(kind, text)] += 4
            if active_sender_id:
                sender_tail = _tail_after_token(raw, active_sender_id)
                if sender_tail:
                    text, kind = _clean_message_text(
                        sender_tail,
                        chat_title=chat_title,
                        target_chat_username=target_chat_username,
                        excluded_names=excluded_names,
                    )
                    if text:
                        scored[(kind, text)] += 2
            text, kind = _clean_message_text(
                raw,
                chat_title=chat_title,
                target_chat_username=target_chat_username,
                excluded_names=excluded_names,
            )
            if text:
                scored[(kind, text)] += 1

    def score_value(kind: str, text: str, count: int) -> tuple[int, int, int, str]:
        plausibility = 0
        if kind == "file":
            plausibility += 20
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            plausibility += 12
        if any(char in "，。！？、,.!? " for char in text):
            plausibility += 8
        if re.fullmatch(r"[a-z0-9 _.-]{2,24}", text):
            plausibility += 6
        if text.startswith("&"):
            plausibility -= 12
        return (count + plausibility, count, -len(text), text)

    return [
        {
            "kind": kind,
            "text": text,
            "count": int(count),
        }
        for (kind, text), count in sorted(
            scored.items(),
            key=lambda item: score_value(item[0][0], item[0][1], item[1]),
            reverse=True,
        )
    ][:50]


def probe_recent_activity(pid: int, chat_title: str, target_chat_username: str, self_username: str | None = None) -> dict[str, Any]:
    room_hits = _search_hits(
        pid,
        [
            ("utf8", target_chat_username.encode("utf-8")),
            ("utf16le", target_chat_username.encode("utf-16le")),
        ],
        max_hits=80,
        context_bytes=4096,
    )
    sender_candidates, sender_name_candidates = _ordered_sender_candidates(
        room_hits,
        chat_title=chat_title,
        target_chat_username=target_chat_username,
        excluded_usernames={self_username} if self_username else set(),
    )
    active_sender_id = sender_candidates[0]["username"] if sender_candidates else None

    sender_hits: list[dict[str, Any]] = []
    if active_sender_id:
        sender_hits = _search_hits(
            pid,
            [
                ("utf8", active_sender_id.encode("utf-8")),
                ("utf16le", active_sender_id.encode("utf-16le")),
            ],
            max_hits=80,
            context_bytes=4096,
        )
    active_sender_name = ""
    if active_sender_id:
        active_sender_names = sender_name_candidates.get(active_sender_id) or []
        if active_sender_names:
            active_sender_name = str(active_sender_names[0]["name"])

    excluded_names = {chat_title, target_chat_username}
    excluded_names.update(str(item["username"]) for item in sender_candidates)
    if self_username:
        excluded_names.add(self_username)
    if active_sender_id:
        excluded_names.update(str(item["name"]) for item in sender_name_candidates.get(active_sender_id, []))
    message_candidates = _collect_message_candidates(
        [*room_hits, *sender_hits],
        chat_title=chat_title,
        target_chat_username=target_chat_username,
        active_sender_id=active_sender_id,
        excluded_names={item for item in excluded_names if item},
    )

    return {
        "active_sender_id": active_sender_id,
        "active_sender_name": active_sender_name,
        "sender_candidates": sender_candidates[:5],
        "sender_name_candidates": {
            username: items[:5]
            for username, items in sender_name_candidates.items()
        },
        "message_candidates": message_candidates,
        "room_hit_count": len(room_hits),
        "sender_hit_count": len(sender_hits),
    }


def _record_candidate(
    stats: dict[str, dict[str, Any]],
    username: str,
    distance: int,
) -> None:
    current = stats.setdefault(username, {"count": 0, "min_distance": distance})
    current["count"] += 1
    current["min_distance"] = min(int(current["min_distance"]), distance)


def probe_target_chat(pid: int, chat_title: str, max_hits: int = 40, self_username: str | None = None) -> dict[str, Any]:
    title_needles = [
        ("utf8", chat_title.encode("utf-8")),
        ("utf16le", chat_title.encode("utf-16le")),
    ]
    hits = _search_hits(pid, title_needles, max_hits=max_hits, context_bytes=2048)
    if not hits:
        raise RuntimeError("target_chat_title_not_found_in_memory")

    candidate_stats: dict[str, dict[str, Any]] = {}
    for hit in hits:
        for item in hit["candidate_usernames"]:
            _record_candidate(candidate_stats, str(item["username"]), int(item["distance"]))

    ordered_candidates = sorted(
        (
            {
                "username": username,
                "count": int(stats["count"]),
                "min_distance": int(stats["min_distance"]),
            }
            for username, stats in candidate_stats.items()
        ),
        key=lambda item: (-item["count"], item["min_distance"], item["username"]),
    )
    best_username = ordered_candidates[0]["username"] if ordered_candidates else None

    best_hit: dict[str, Any] | None = None
    if best_username:
        matching_hits = [
            hit
            for hit in hits
            if any(item["username"] == best_username for item in hit["candidate_usernames"])
        ]
        if matching_hits:
            best_hit = min(
                matching_hits,
                key=lambda hit: min(
                    item["distance"]
                    for item in hit["candidate_usernames"]
                    if item["username"] == best_username
                ),
            )
    if best_hit is None:
        best_hit = hits[0]

    summary_strings = [
        item
        for item in best_hit["context_strings"]
        if item != chat_title and item != best_username
    ]
    summary_hash = hashlib.sha256(
        json.dumps(summary_strings, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    activity = probe_recent_activity(pid, chat_title, best_username, self_username=self_username) if best_username else {}
    title_sender_candidates, title_sender_name_candidates = _ordered_sender_candidates(
        hits,
        chat_title=chat_title,
        target_chat_username=best_username or "",
        excluded_usernames={self_username} if self_username else set(),
    )
    active_sender_id = str(activity.get("active_sender_id") or "").strip()
    if active_sender_id and title_sender_name_candidates.get(active_sender_id):
        preferred_names = title_sender_name_candidates[active_sender_id]
        activity["active_sender_name"] = preferred_names[0]["name"]
        merged_name_counts = {
            item["name"]: int(item["count"])
            for item in activity.get("sender_name_candidates", {}).get(active_sender_id, [])
        }
        for item in preferred_names:
            merged_name_counts[str(item["name"])] = merged_name_counts.get(str(item["name"]), 0) + int(item["count"]) + 20
        activity.setdefault("sender_name_candidates", {})[active_sender_id] = sorted(
            ({"name": name, "count": count} for name, count in merged_name_counts.items()),
            key=lambda item: (-item["count"], item["name"]),
        )

    return {
        "resolver": "memory_probe",
        "wechat_pid": pid,
        "target_chat_title": chat_title,
        "target_chat_username": best_username,
        "title_hit_count": len(hits),
        "candidate_usernames": ordered_candidates,
        "best_hit_address": best_hit["address"],
        "best_hit_encoding": best_hit["encoding"],
        "context_strings": summary_strings,
        "context_hash": summary_hash,
        "sample_hits": hits[:5],
        **activity,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wechat-memory-probe")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--chat-title", required=True)
    parser.add_argument("--max-hits", type=int, default=40)
    parser.add_argument("--self-username", default="")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            probe_target_chat(
                args.pid,
                args.chat_title,
                args.max_hits,
                self_username=args.self_username.strip() or None,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
