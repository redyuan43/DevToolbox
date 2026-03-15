from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig
from .state import StateStore
from .x11 import WindowInfo, activate_window, discover_standalone_windows


def _now_ms() -> int:
    return int(time.time() * 1000)


def _shell_words(value: str) -> str:
    return value.replace("'", "''")


def _json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_window_title(value: str) -> str:
    return re.sub(r"\(\d+\)$", "", value.strip())


def _truncate_text(value: str, limit: int = 80) -> str:
    compact = _normalize_text(value)
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)] + "…"


CHAT_USERNAME_VALUE_RE = re.compile(r"^(?:[0-9]{6,}@chatroom|wxid_[0-9A-Za-z_]+(?:_[0-9a-fA-F]{4,})?|gh_[0-9A-Za-z_]+)$")
FILENAME_LIKE_RE = re.compile(
    r".+\.(?:zip|7z|rar|txt|md|pdf|doc|docx|xls|xlsx|ppt|pptx|png|jpe?g|gif|bmp|webp|mp3|wav|m4a|mp4|mov)$",
    re.IGNORECASE,
)


def _candidate_fingerprint(kind: str, sender_id: str, sender_name: str, text: str) -> str:
    normalized = "::".join(
        [
            kind.strip().lower(),
            sender_id.strip().lower(),
            sender_name.strip().lower(),
            _normalize_text(text).lower(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _derive_self_username(account_dir: Path) -> str | None:
    name = account_dir.name.strip()
    if not name.startswith("wxid_"):
        return None
    if re.fullmatch(r"wxid_[0-9A-Za-z]+_[0-9a-fA-F]{4,}", name):
        return name.rsplit("_", 1)[0]
    return name


def _normalize_message_candidates(
    resolution: dict[str, Any],
    *,
    sender_id: str,
    sender_name: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in list(resolution.get("message_candidates") or [])[:50]:
        kind = str(raw.get("kind", "unknown")).strip() or "unknown"
        text = _normalize_text(str(raw.get("text", "")).strip())
        if not text:
            continue
        count = int(raw.get("count", 0) or 0)
        normalized.append(
            {
                "kind": kind,
                "text": text,
                "count": count,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "fingerprint": _candidate_fingerprint(kind, sender_id, sender_name, text),
            }
        )
    return normalized


def _pick_latest_candidate(
    previous_fingerprints: set[str],
    current_candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    new_candidates = [item for item in current_candidates if item["fingerprint"] not in previous_fingerprints]
    if not new_candidates:
        return None

    def sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
        kind = str(item.get("kind", "unknown"))
        priority = {"text": 3, "file": 2, "image": 2}.get(kind, 1)
        return (
            priority,
            int(item.get("count", 0)),
            len(str(item.get("text", ""))),
            str(item.get("text", "")),
        )

    return sorted(new_candidates, key=sort_key, reverse=True)[0]


@dataclass(slots=True)
class SqlcipherParams:
    db_path: str
    key_hex: str | None
    pragmas: dict[str, str]


class SqlcipherError(RuntimeError):
    pass


class MemoryProbeError(RuntimeError):
    pass


class SqlcipherRunner:
    def __init__(self, sqlcipher_bin: str) -> None:
        self.sqlcipher_bin = sqlcipher_bin

    def query(self, db_path: str, params: SqlcipherParams, sql: str) -> list[list[str]]:
        script_lines = [
            ".headers off",
            ".mode tabs",
            ".nullvalue NULL",
        ]
        if params.key_hex:
            script_lines.append(f"PRAGMA key = \"x'{params.key_hex}'\";")
        for pragma, value in params.pragmas.items():
            script_lines.append(f"PRAGMA {pragma} = {value};")
        script_lines.append(sql.rstrip(";") + ";")
        script = "\n".join(script_lines) + "\n"
        result = subprocess.run(
            [self.sqlcipher_bin, "-readonly", db_path],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise SqlcipherError(result.stderr.strip() or result.stdout.strip() or "sqlcipher_query_failed")
        rows: list[list[str]] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            rows.append(line.split("\t"))
        return rows

    def scalar(self, db_path: str, params: SqlcipherParams, sql: str) -> str | None:
        rows = self.query(db_path, params, sql)
        if not rows:
            return None
        return rows[0][0] if rows[0] else None

    def json_rows(self, db_path: str, params: SqlcipherParams, sql: str) -> list[dict[str, Any]]:
        rows = self.query(db_path, params, sql)
        payloads: list[dict[str, Any]] = []
        for row in rows:
            if not row:
                continue
            raw = str(row[0]).strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                payloads.append(parsed)
        return payloads


def active_account_dir(download_root: Path) -> Path | None:
    try:
        output = subprocess.run(
            ["pgrep", "-x", "wechat"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None

    pids = [line.strip() for line in output.splitlines() if line.strip()]
    path_re = re.compile(rf"({re.escape(str(download_root))}/[^/\s]+/db_storage/)")
    for pid in pids:
        result = subprocess.run(
            ["lsof", "-p", pid],
            text=True,
            capture_output=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            raw = path_re.search(line)
            if not raw:
                continue
            return Path(raw.group(1)).parent
    return None


def main_wechat_pid() -> int | None:
    result = subprocess.run(
        ["pgrep", "-a", "-x", "wechat"],
        text=True,
        capture_output=True,
        check=False,
    )
    for raw in result.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split(maxsplit=1)
        if not parts:
            continue
        pid = int(parts[0])
        command = parts[1] if len(parts) > 1 else ""
        if command == "/usr/bin/wechat" or command.endswith("/usr/bin/wechat") or command == "wechat":
            return pid
    return None


def run_memory_probe(
    chat_title: str,
    pid: int,
    use_sudo: bool,
    timeout_s: int,
    self_username: str | None = None,
) -> dict[str, Any]:
    script_path = Path(__file__).with_name("memprobe.py")
    command = [
        sys.executable,
        str(script_path),
        "--pid",
        str(pid),
        "--chat-title",
        chat_title,
    ]
    if self_username:
        command.extend(["--self-username", self_username])
    if use_sudo and os.geteuid() != 0:
        command = ["sudo", "-n", *command]
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=max(1, timeout_s),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MemoryProbeError("memory_probe_timeout") from exc
    if result.returncode != 0:
        raise MemoryProbeError(result.stderr.strip() or result.stdout.strip() or "memory_probe_failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MemoryProbeError("memory_probe_invalid_json") from exc
    return payload


def parse_hook_log(path: Path) -> dict[str, SqlcipherParams]:
    per_db: dict[str, SqlcipherParams] = {}
    if not path.exists():
        return per_db
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        db_path = str(payload.get("db_path", "")).strip()
        if not db_path:
            continue
        current = per_db.setdefault(db_path, SqlcipherParams(db_path=db_path, key_hex=None, pragmas={}))
        event = str(payload.get("event", ""))
        if event in {"sqlite3_key", "sqlite3_key_v2"}:
            key_hex = str(payload.get("key_hex", "")).strip()
            if key_hex:
                current.key_hex = key_hex
        if event in {"sqlite3_exec", "sqlite3_prepare_v2"}:
            sql = str(payload.get("sql", "")).strip()
            match = re.match(r"PRAGMA\s+([a-zA-Z0-9_]+)\s*=\s*(.+)", sql, flags=re.IGNORECASE)
            if not match:
                continue
            pragma = match.group(1).strip().lower()
            value = match.group(2).strip().rstrip(";")
            if pragma == "key":
                value = value.strip('"')
                if value.startswith("x'") and value.endswith("'"):
                    current.key_hex = value[2:-1]
            elif pragma.startswith("cipher_"):
                current.pragmas[pragma] = value
    return per_db


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_columns(
    runner: SqlcipherRunner,
    db_path: str,
    params: SqlcipherParams,
    table: str,
) -> list[dict[str, str]]:
    rows = runner.query(db_path, params, f"PRAGMA table_info({_quote_ident(table)})")
    columns: list[dict[str, str]] = []
    for row in rows:
        if len(row) < 2:
            continue
        columns.append(
            {
                "cid": str(row[0]) if len(row) > 0 else "",
                "name": str(row[1]) if len(row) > 1 else "",
                "type": str(row[2]) if len(row) > 2 else "",
                "notnull": str(row[3]) if len(row) > 3 else "",
                "default": str(row[4]) if len(row) > 4 else "",
                "pk": str(row[5]) if len(row) > 5 else "",
            }
        )
    return columns


def _column_score(name: str, *, exact: tuple[str, ...], contains: tuple[str, ...]) -> int:
    lowered = name.strip().lower()
    best = 0
    for index, target in enumerate(exact):
        if lowered == target.lower():
            best = max(best, 100 - index)
    for index, token in enumerate(contains):
        if token.lower() in lowered:
            best = max(best, 40 - index)
    return best


def _best_column(name_list: list[str], *, exact: tuple[str, ...], contains: tuple[str, ...]) -> str | None:
    scored = [
        (_column_score(name, exact=exact, contains=contains), name)
        for name in name_list
    ]
    scored = [item for item in scored if item[0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][1]


def _extract_username_value(values: list[str], preferred_username: str | None = None) -> str | None:
    normalized = [
        str(value).strip()
        for value in values
        if str(value).strip() and str(value).strip() != "NULL"
    ]
    if preferred_username and preferred_username in normalized:
        return preferred_username
    for value in normalized:
        if CHAT_USERNAME_VALUE_RE.fullmatch(value) and value.endswith("@chatroom"):
            return value
    for value in normalized:
        if CHAT_USERNAME_VALUE_RE.fullmatch(value):
            return value
    return None


def _json_expr_for_column(column: dict[str, str]) -> str:
    name = str(column.get("name", "")).strip()
    ident = _quote_ident(name)
    decl_type = str(column.get("type", "")).strip().lower()
    if "blob" in decl_type:
        value_expr = f"hex({ident})"
    else:
        value_expr = f"CAST({ident} AS TEXT)"
    return f"'{name}', CASE WHEN {ident} IS NULL THEN NULL ELSE {value_expr} END"


def _clean_db_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text == "NULL":
        return ""
    return _normalize_text(text.replace("\x00", " "))


def _xml_tag_text(payload: str, tag: str) -> str | None:
    for pattern in [
        rf"<{tag}><!\[CDATA\[(.*?)\]\]></{tag}>",
        rf"<{tag}>(.*?)</{tag}>",
    ]:
        match = re.search(pattern, payload, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _normalize_text(match.group(1))
    return None


def _message_row_identity(mapping: dict[str, Any], row: dict[str, Any]) -> str:
    order_column = str(mapping.get("message_order_column", "")).strip()
    order_value = _clean_db_value(row.get(order_column))
    rowid = _clean_db_value(row.get("rowid"))
    if order_value:
        return f"{order_value}:{rowid}"
    return rowid


def _partition_new_message_rows(
    mapping: dict[str, Any],
    rows: list[dict[str, Any]],
    last_seen_identity: str | None,
) -> tuple[str | None, list[dict[str, Any]]]:
    if not rows:
        return last_seen_identity, []
    newest_identity = _message_row_identity(mapping, rows[0])
    if not last_seen_identity:
        return newest_identity, []
    new_rows: list[dict[str, Any]] = []
    for row in rows:
        identity = _message_row_identity(mapping, row)
        if identity == last_seen_identity:
            break
        new_rows.append(row)
    return newest_identity, list(reversed(new_rows))


def _parse_message_row(
    mapping: dict[str, Any],
    row: dict[str, Any],
    *,
    self_username: str | None,
    target_chat_username: str | None,
) -> dict[str, Any]:
    content_column = str(mapping.get("message_content_column", "")).strip()
    sender_column = str(mapping.get("message_sender_column", "")).strip()
    sender_name_column = str(mapping.get("message_sender_name_column", "")).strip()
    direction_column = str(mapping.get("message_direction_column", "")).strip()
    type_column = str(mapping.get("message_type_column", "")).strip()

    raw_content_value = "" if row.get(content_column) is None else str(row.get(content_column))
    raw_content = raw_content_value.replace("\x00", "").strip()
    sender_id = _clean_db_value(row.get(sender_column))
    sender_name = _clean_db_value(row.get(sender_name_column))
    direction_raw = _clean_db_value(row.get(direction_column))
    type_raw = _clean_db_value(row.get(type_column))

    inline_sender = None
    inline_match = re.match(r"^((?:wxid_[0-9A-Za-z_]+|gh_[0-9A-Za-z_]+|[0-9]{6,}@chatroom)):\n(.+)$", raw_content, flags=re.DOTALL)
    if inline_match:
        inline_sender = inline_match.group(1)
        raw_content = inline_match.group(2).strip()
    if not sender_id and inline_sender:
        sender_id = inline_sender

    extracted_text = _normalize_text(raw_content)
    kind = "unknown"
    if raw_content.startswith("<") and "appmsg" in raw_content.lower():
        extracted_text = (
            _xml_tag_text(raw_content, "title")
            or _xml_tag_text(raw_content, "des")
            or _xml_tag_text(raw_content, "url")
            or ""
        )
        app_type = _xml_tag_text(raw_content, "type") or ""
        if FILENAME_LIKE_RE.fullmatch(extracted_text) or app_type in {"6", "74"}:
            kind = "file"
        else:
            kind = "text" if extracted_text else "unknown"
    elif raw_content.startswith("<") and "img" in raw_content.lower():
        kind = "image"
        extracted_text = "[图片]"
    elif FILENAME_LIKE_RE.fullmatch(raw_content):
        kind = "file"
    elif type_raw in {"3", "47"}:
        kind = "image"
        if not extracted_text:
            extracted_text = "[图片]"
    elif raw_content:
        kind = "text"

    if not extracted_text:
        for key, value in row.items():
            if key in {"rowid", content_column, sender_column, sender_name_column, direction_column, type_column}:
                continue
            candidate = _clean_db_value(value)
            if not candidate or candidate == target_chat_username or CHAT_USERNAME_VALUE_RE.fullmatch(candidate):
                continue
            if FILENAME_LIKE_RE.fullmatch(candidate):
                extracted_text = candidate
                kind = "file"
                break
            if not extracted_text and len(candidate) <= 200:
                extracted_text = candidate

    direction = "unknown"
    lowered_direction = direction_raw.lower()
    if lowered_direction in {"1", "true", "yes"}:
        direction = "outbound"
    elif lowered_direction in {"0", "false", "no"}:
        direction = "inbound"
    elif sender_id and self_username and sender_id.startswith(self_username):
        direction = "outbound"
    elif sender_id and target_chat_username and sender_id != target_chat_username:
        direction = "inbound"

    if direction == "outbound" and not sender_id and self_username:
        sender_id = self_username
    if not sender_name and sender_id:
        sender_name = sender_id

    order_column = str(mapping.get("message_order_column", "")).strip()
    return {
        "rowid": _clean_db_value(row.get("rowid")),
        "order_value": _clean_db_value(row.get(order_column)),
        "message_identity": _message_row_identity(mapping, row),
        "message_type": kind,
        "message_type_raw": type_raw,
        "message_direction": direction,
        "message_direction_raw": direction_raw,
        "text": extracted_text,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "raw_content": raw_content,
    }


def fetch_target_message_rows(
    runner: SqlcipherRunner,
    message_db: str,
    params: SqlcipherParams,
    mapping: dict[str, Any],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    table = str(mapping["message_table"])
    match_column = str(mapping["message_match_column"])
    order_column = str(mapping["message_order_column"])
    match_value = _shell_words(str(mapping["match_value"]))
    columns_meta = list(mapping.get("message_columns_meta") or [])
    if not columns_meta:
        columns_meta = [{"name": name, "type": ""} for name in list(mapping.get("message_columns") or [])]

    json_pairs = ["'rowid', CAST(rowid AS TEXT)"]
    seen = {"rowid"}
    for column in columns_meta:
        name = str(column.get("name", "")).strip()
        if not name or name in seen:
            continue
        json_pairs.append(_json_expr_for_column(column))
        seen.add(name)
    sql = (
        f"SELECT json_object({', '.join(json_pairs)}) FROM {_quote_ident(table)} "
        f"WHERE CAST({_quote_ident(match_column)} AS TEXT) = '{match_value}' "
        f"ORDER BY {_quote_ident(order_column)} DESC, rowid DESC LIMIT {max(1, int(limit))}"
    )
    return runner.json_rows(message_db, params, sql)


def find_target_chat_mapping(
    runner: SqlcipherRunner,
    session_db: str,
    message_db: str,
    session_params: SqlcipherParams,
    message_params: SqlcipherParams,
    target_chat_title: str,
    preferred_target_username: str | None = None,
) -> dict[str, Any]:
    tables = [row[0] for row in runner.query(session_db, session_params, "SELECT name FROM sqlite_master WHERE type='table'")]
    session_candidates: list[dict[str, Any]] = []
    search_terms = [target_chat_title]
    if preferred_target_username and preferred_target_username not in search_terms:
        search_terms.insert(0, preferred_target_username)

    for table in tables:
        columns_meta = table_columns(runner, session_db, session_params, table)
        if not columns_meta:
            continue
        col_names = [column["name"] for column in columns_meta if column.get("name")]
        for term in search_terms:
            escaped_term = _shell_words(term)
            for col_name in col_names:
                sql = (
                    f"SELECT rowid, * FROM {_quote_ident(table)} "
                    f"WHERE instr(CAST({_quote_ident(col_name)} AS TEXT), '{escaped_term}') > 0 LIMIT 8"
                )
                rows = runner.query(session_db, session_params, sql)
                if not rows:
                    continue
                for row in rows:
                    target_username = _extract_username_value(row, preferred_target_username)
                    score = _column_score(
                        col_name,
                        exact=("strtalker", "talker", "username", "chatname", "name", "nickname", "remark"),
                        contains=("talker", "user", "name", "nick", "remark", "title", "chat"),
                    )
                    if term == preferred_target_username:
                        score += 120
                    elif term == target_chat_title:
                        score += 100
                    if target_username:
                        score += 30
                        if target_username.endswith("@chatroom"):
                            score += 10
                    session_candidates.append(
                        {
                            "score": score,
                            "session_table": table,
                            "matched_column": col_name,
                            "columns": ["rowid", *col_names],
                            "columns_meta": columns_meta,
                            "row": row,
                            "target_chat_username": target_username,
                        }
                    )
    if not session_candidates:
        raise SqlcipherError("target_chat_not_found")

    session_match = sorted(session_candidates, key=lambda item: (-int(item["score"]), item["session_table"], item["matched_column"]))[0]
    target_chat_username = str(session_match.get("target_chat_username") or "").strip() or preferred_target_username
    message_tables = [row[0] for row in runner.query(message_db, message_params, "SELECT name FROM sqlite_master WHERE type='table'")]
    candidate_values: list[str] = []
    if target_chat_username:
        candidate_values.append(target_chat_username)
    for value in session_match["row"]:
        text = str(value).strip()
        if not text or text == "NULL" or text == target_chat_title or len(text) < 4:
            continue
        if CHAT_USERNAME_VALUE_RE.fullmatch(text) and text not in candidate_values:
            candidate_values.append(text)

    preferred_order = ["CreateTime", "create_time", "msgSvrId", "msg_seq", "local_id"]
    chosen: dict[str, Any] | None = None
    for candidate in candidate_values:
        escaped = _shell_words(candidate)
        for table in message_tables:
            columns_meta = table_columns(runner, message_db, message_params, table)
            if not columns_meta:
                continue
            col_names = [column["name"] for column in columns_meta if column.get("name")]
            for col_name in col_names:
                sql = (
                    f"SELECT rowid, * FROM {_quote_ident(table)} "
                    f"WHERE CAST({_quote_ident(col_name)} AS TEXT) = '{escaped}' LIMIT 2"
                )
                rows = runner.query(message_db, message_params, sql)
                if not rows:
                    continue
                order_column = next((item for item in preferred_order if item in col_names), "rowid")
                score = _column_score(
                    col_name,
                    exact=("strtalker", "talker", "username", "sessionid", "conversationid"),
                    contains=("talker", "session", "chat", "conversation", "user"),
                )
                if candidate == target_chat_username:
                    score += 120
                chosen = {
                    "score": score,
                    "session_table": session_match["session_table"],
                    "session_match_column": session_match["matched_column"],
                    "message_table": table,
                    "message_match_column": col_name,
                    "message_order_column": order_column,
                    "message_columns": ["rowid", *col_names],
                    "message_columns_meta": columns_meta,
                    "match_value": candidate,
                    "target_chat_username": target_chat_username or candidate,
                    "message_content_column": _best_column(
                        col_names,
                        exact=("content", "strcontent", "message", "text", "compresscontent", "title"),
                        contains=("content", "text", "message", "title", "desc", "body"),
                    ),
                    "message_sender_column": _best_column(
                        col_names,
                        exact=("sender", "senderid", "senderuserid", "fromusername", "fromuser"),
                        contains=("sender", "fromuser", "username", "usr"),
                    ),
                    "message_sender_name_column": _best_column(
                        col_names,
                        exact=("sendername", "displayname", "nickname", "fromnickname"),
                        contains=("name", "nick"),
                    ),
                    "message_direction_column": _best_column(
                        col_names,
                        exact=("issender", "des", "direction", "issend"),
                        contains=("sender", "direction", "send"),
                    ),
                    "message_type_column": _best_column(
                        col_names,
                        exact=("type", "msgtype", "messagetype", "subtype"),
                        contains=("type",),
                    ),
                }
                break
            if chosen:
                break
        if chosen:
            break
    if not chosen:
        raise SqlcipherError("target_message_table_not_found")
    return chosen


def detect_new_target_rows(
    runner: SqlcipherRunner,
    message_db: str,
    params: SqlcipherParams,
    mapping: dict[str, Any],
    last_seen: str | None,
) -> tuple[str | None, list[dict[str, str]]]:
    table = mapping["message_table"]
    match_column = mapping["message_match_column"]
    order_column = mapping["message_order_column"]
    match_value = _shell_words(mapping["match_value"])
    rows = runner.query(
        message_db,
        params,
        f"SELECT {_quote_ident(order_column)}, rowid FROM {_quote_ident(table)} "
        f"WHERE CAST({_quote_ident(match_column)} AS TEXT) = '{match_value}' "
        f"ORDER BY {_quote_ident(order_column)} DESC LIMIT 20",
    )
    if not rows:
        return last_seen, []
    newest = rows[0][0]
    if last_seen is None:
        return newest, []
    new_rows = [
        {"order_value": row[0], "rowid": row[1] if len(row) > 1 else ""}
        for row in rows
        if row[0] > last_seen
    ]
    return newest, list(reversed(new_rows))


def db_snapshot_paths(account_dir: Path) -> list[Path]:
    bases = [
        account_dir / "db_storage" / "message" / "message_0.db",
        account_dir / "db_storage" / "session" / "session.db",
    ]
    paths: list[Path] = []
    for base in bases:
        paths.append(base)
        paths.append(Path(str(base) + "-wal"))
        paths.append(Path(str(base) + "-shm"))
    return paths


def snapshot_paths(paths: list[Path]) -> dict[str, dict[str, int]]:
    snapshot: dict[str, dict[str, int]] = {}
    for path in paths:
        if not path.exists():
            continue
        stat = path.stat()
        snapshot[str(path)] = {
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
    return snapshot


def changed_snapshot_paths(
    previous: dict[str, dict[str, int]] | None,
    current: dict[str, dict[str, int]],
) -> list[str]:
    previous = previous or {}
    changed: list[str] = []
    for path, values in current.items():
        if previous.get(path) != values:
            changed.append(path)
    for path in previous:
        if path not in current:
            changed.append(path)
    return sorted(changed)


class InotifyWatcher:
    IN_MODIFY = 0x00000002
    IN_CLOSE_WRITE = 0x00000008
    IN_MOVED_TO = 0x00000080
    IN_CREATE = 0x00000100
    IN_NONBLOCK = 0x800

    def __init__(self, paths: list[Path]) -> None:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        self._init = libc.inotify_init1
        self._init.argtypes = [ctypes.c_int]
        self._init.restype = ctypes.c_int
        self._add = libc.inotify_add_watch
        self._add.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self._add.restype = ctypes.c_int
        self.fd = self._init(self.IN_NONBLOCK)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1_failed")
        self.paths = [path for path in paths if path.exists()]
        self.mask = self.IN_MODIFY | self.IN_CLOSE_WRITE | self.IN_MOVED_TO | self.IN_CREATE
        self.watches: dict[int, Path] = {}
        for path in self.paths:
            wd = self._add(self.fd, os.fsencode(str(path)), self.mask)
            if wd >= 0:
                self.watches[wd] = path

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def wait(self, timeout_ms: int) -> list[dict[str, str]]:
        import select

        ready, _, _ = select.select([self.fd], [], [], max(0.0, timeout_ms / 1000.0))
        if not ready:
            return []
        data = os.read(self.fd, 4096)
        events: list[dict[str, str]] = []
        offset = 0
        while offset + 16 <= len(data):
            wd = int.from_bytes(data[offset:offset + 4], "little", signed=True)
            mask = int.from_bytes(data[offset + 4:offset + 8], "little")
            name_len = int.from_bytes(data[offset + 12:offset + 16], "little")
            name_bytes = data[offset + 16:offset + 16 + name_len]
            name = name_bytes.split(b"\x00", 1)[0].decode("utf-8", "ignore")
            base = self.watches.get(wd)
            if base and name:
                events.append({"path": str(base / name), "mask": str(mask)})
            offset += 16 + name_len
        return events


class DbDetectService:
    def __init__(self, config: AppConfig, store: StateStore) -> None:
        self.config = config
        self.store = store
        self.runner = SqlcipherRunner(config.db_parse.sqlcipher_bin)

    def status(self) -> dict[str, Any]:
        return dict(self.store.runtime.db_detector_state)

    def _console_print(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [db-detect] {message}", flush=True)

    def _format_run_once_summary(self, payload: dict[str, Any]) -> str:
        reason = str(payload.get("last_wake_reason", "")).strip() or "unknown"
        popup = str(payload.get("popup_decision", "")).strip() or "popup_no_action"
        chat = str(payload.get("target_chat_title", "")).strip() or "unknown"
        latest_type = str(payload.get("latest_message_type", "unknown")).strip() or "unknown"
        latest_text = _truncate_text(str(payload.get("latest_text", "")).strip())
        sender_name = str(payload.get("latest_sender_name", "")).strip()
        sender_id = str(payload.get("latest_sender_id", "")).strip()
        sender = sender_name or sender_id

        if reason in {"target_chat_db_activity", "db_changed_target_unchanged"} and popup == "popup_activated":
            detail = chat
            if sender:
                detail += f" | from={sender}"
            if latest_text:
                detail += f" | {_truncate_text(latest_text)}"
            return f"检测到会话写入并已弹窗: {detail}"

        if reason in {"target_chat_message_candidate", "target_chat_new_message"}:
            detail = f"{chat} | {latest_type}"
            if sender:
                detail += f" | from={sender}"
            if latest_text:
                detail += f" | {latest_text}"
            if popup == "popup_activated":
                return f"检测到新消息并已弹窗: {detail}"
            if popup == "popup_window_missing":
                return f"检测到新消息，但目标窗口未打开: {detail}"
            if popup == "popup_cooldown_skip":
                return f"检测到新消息，但处于弹窗冷却期: {detail}"
            if popup == "popup_skipped_unknown":
                return f"检测到消息，但候选不完整，已跳过: {detail}"
            return f"检测到新消息: {detail} | {popup}"

        if reason == "target_chat_db_activity":
            return f"目标群数据库有活动: {chat}"
        if reason == "memory_changed_without_db_change":
            return f"检测到目标群上下文变化: {chat}"
        if reason == "db_changed_target_unchanged":
            return f"数据库有写入，但未确认到目标群新消息: {chat}"
        if reason == "baseline_initialized":
            return f"已建立基线: {chat}"
        if reason == "no_change":
            return f"无新变化: {chat}"
        return f"{chat}: {reason} | {popup}"

    def run_once(self) -> dict[str, Any]:
        account_dir = self._resolve_account_dir()
        hook_params = parse_hook_log(Path(self.config.db_parse.hook_log_path))
        session_db = str(account_dir / "db_storage" / "session" / "session.db")
        message_db = str(account_dir / "db_storage" / "message" / "message_0.db")
        session_params = hook_params.get(session_db)
        message_params = hook_params.get(message_db)
        resolver_mode = self.config.db_parse.resolver_mode.strip().lower() or "auto"

        if resolver_mode == "sqlcipher":
            if not session_params or not message_params:
                raise SqlcipherError("db_open_failed:missing_hook_params")
            return self._run_sqlcipher_mode(account_dir, session_db, message_db, session_params, message_params)

        if resolver_mode == "auto" and session_params and message_params:
            return self._run_sqlcipher_mode(account_dir, session_db, message_db, session_params, message_params)

        return self._run_memory_mode(account_dir)

    def run_daemon(self) -> None:
        account_dir = self._resolve_account_dir()
        watch_paths = [
            account_dir / "db_storage" / "session",
        ]
        watcher = InotifyWatcher(watch_paths)
        self.store.runtime.db_detector_state = {
            "driver_mode": "db_detect",
            "watch_paths": [str(path) for path in watch_paths if path.exists()],
            "updated_at_ms": _now_ms(),
        }
        self.store.save()
        self.store.append_audit(
            {
                "scope": "db",
                "event": "db_trigger_bound",
                "watch_paths": [str(path) for path in watch_paths if path.exists()],
            }
        )
        self._console_print(
            "开始监听: " + ", ".join(str(path) for path in watch_paths if path.exists())
        )
        debounce_s = max(0.05, self.config.db_parse.debounce_ms / 1000.0)
        try:
            while True:
                events = watcher.wait(timeout_ms=1000)
                if not events:
                    continue
                events = [
                    item
                    for item in events
                    if Path(str(item.get("path", ""))).name in {"session.db", "session.db-wal"}
                ]
                if not events:
                    continue
                time.sleep(debounce_s)
                event_paths = sorted({str(item.get("path", "")).strip() for item in events if str(item.get("path", "")).strip()})
                self.store.append_audit(
                    {
                        "scope": "db",
                        "event": "db_trigger_event",
                        "events": events[:20],
                    }
                )
                if event_paths:
                    self._console_print("触发: " + ", ".join(event_paths[:3]))
                try:
                    payload = self.run_once()
                    self._console_print(self._format_run_once_summary(payload))
                except (SqlcipherError, MemoryProbeError) as exc:
                    self.store.runtime.db_detector_state = {
                        **self.store.runtime.db_detector_state,
                        "last_wake_reason": "detector_error",
                        "last_error": str(exc),
                        "updated_at_ms": _now_ms(),
                    }
                    self.store.runtime.last_status = {
                        "action": "db_detect",
                        "detail": "detector_error",
                        "updated_at_ms": _now_ms(),
                    }
                    self.store.save()
                    self.store.append_audit(
                        {
                            "scope": "db",
                            "event": "detector_error",
                            "error": str(exc),
                        }
                    )
                    self._console_print(f"错误: {exc}")
        finally:
            watcher.close()

    def _run_sqlcipher_mode(
        self,
        account_dir: Path,
        session_db: str,
        message_db: str,
        session_params: SqlcipherParams,
        message_params: SqlcipherParams,
    ) -> dict[str, Any]:
        mapping_path = self.config.state_dir / "db_schema_cache.json"
        mapping = self._load_json(mapping_path)
        previous_state = dict(self.store.runtime.db_detector_state)
        preferred_username = self._preferred_target_chat_username(previous_state)
        if not mapping or str(mapping.get("target_chat_title", "")).strip() != self.config.db_parse.target_chat_title:
            mapping = find_target_chat_mapping(
                self.runner,
                session_db,
                message_db,
                session_params,
                message_params,
                self.config.db_parse.target_chat_title,
                preferred_target_username=preferred_username,
            )
            mapping["target_chat_title"] = self.config.db_parse.target_chat_title
            mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

        rows = fetch_target_message_rows(
            self.runner,
            message_db,
            message_params,
            mapping,
            limit=20,
        )
        parsed_rows = [
            _parse_message_row(
                mapping,
                row,
                self_username=_derive_self_username(account_dir),
                target_chat_username=str(mapping.get("target_chat_username", "")).strip() or None,
            )
            for row in rows
        ]
        last_seen_identity = str(previous_state.get("last_seen_message_identity", "")).strip() or None
        newest_identity, new_rows = _partition_new_message_rows(mapping, rows, last_seen_identity)
        parsed_new_rows = [
            _parse_message_row(
                mapping,
                row,
                self_username=_derive_self_username(account_dir),
                target_chat_username=str(mapping.get("target_chat_username", "")).strip() or None,
            )
            for row in new_rows
        ]
        latest_row = parsed_rows[0] if parsed_rows else None
        target_window = self._find_target_window()
        payload = {
            "driver_mode": "db_detect_sqlcipher",
            "resolver_mode": "sqlcipher",
            "account_dir": str(account_dir),
            "target_chat_title": self.config.db_parse.target_chat_title,
            "target_chat_username": str(mapping.get("target_chat_username", "")).strip() or None,
            "session_db": session_db,
            "message_db": message_db,
            "mapping": mapping,
            "last_seen_message_identity": newest_identity or last_seen_identity,
            "last_seen_order_value": latest_row["order_value"] if latest_row else str(previous_state.get("last_seen_order_value", "")).strip(),
            "updated_at_ms": _now_ms(),
        }
        if target_window:
            payload["window_id"] = target_window.window_id
            payload["window_title"] = target_window.title
        else:
            payload["window_id"] = None
            payload["window_title"] = None
        if latest_row:
            payload.update(
                {
                    "latest_message_type": latest_row["message_type"],
                    "latest_message_direction": latest_row["message_direction"],
                    "latest_text": latest_row["text"],
                    "latest_sender_id": latest_row["sender_id"],
                    "latest_sender_name": latest_row["sender_name"],
                    "latest_message_identity": latest_row["message_identity"],
                    "latest_message_type_raw": latest_row["message_type_raw"],
                    "latest_message_direction_raw": latest_row["message_direction_raw"],
                }
            )
        else:
            payload.update(
                {
                    "latest_message_type": "unknown",
                    "latest_message_direction": "unknown",
                    "latest_text": "",
                    "latest_sender_id": "",
                    "latest_sender_name": "",
                    "latest_message_identity": last_seen_identity,
                    "latest_message_type_raw": "",
                    "latest_message_direction_raw": "",
                }
            )

        if last_seen_identity is None and newest_identity:
            payload["last_wake_reason"] = "baseline_initialized"
            payload["new_rows"] = []
        elif parsed_new_rows:
            payload["last_wake_reason"] = "target_chat_new_message"
            payload["new_rows"] = parsed_new_rows
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "target_chat_new_message",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "account_dir": str(account_dir),
                    "message_table": mapping["message_table"],
                    "message_match_column": mapping["message_match_column"],
                    "message_order_column": mapping["message_order_column"],
                    "new_rows": parsed_new_rows,
                }
            )
        else:
            payload["last_wake_reason"] = "no_new_target_rows"

        popup_decision, popup_at_ms = self._popup_action(
            previous_state,
            target_window,
            base_reason=str(payload["last_wake_reason"]),
            has_new_message=bool(parsed_new_rows),
            latest_type=str(payload["latest_message_type"]),
            latest_text=str(payload["latest_text"]),
            latest_sender_id=str(payload["latest_sender_id"]),
            latest_sender_name=str(payload["latest_sender_name"]),
        )
        payload["popup_decision"] = popup_decision
        payload["last_popup_at_ms"] = popup_at_ms
        self.store.runtime.db_detector_state = payload
        self.store.runtime.last_status = {
            "action": "db_detect",
            "detail": f"{payload['last_wake_reason']}:{popup_decision}",
            "updated_at_ms": payload["updated_at_ms"],
        }
        self.store.save()
        return payload

    def _preferred_target_chat_username(self, previous_state: dict[str, Any]) -> str | None:
        candidate = str(previous_state.get("target_chat_username", "")).strip()
        if candidate:
            return candidate
        cached = self._load_json(self.config.state_dir / "db_target_cache.json")
        if not cached:
            return None
        candidate = str(cached.get("target_chat_username", "")).strip()
        return candidate or None

    def _find_target_window(self) -> WindowInfo | None:
        target_title = _normalize_window_title(self.config.db_parse.target_chat_title)
        candidates = discover_standalone_windows(self.config.window, [])
        matches = [
            item
            for item in candidates
            if _normalize_window_title(item.title) == target_title
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda item: item.width * item.height, reverse=True)[0]

    def _should_popup_on_db_activity(
        self,
        *,
        base_reason: str,
        latest_sender_id: str,
        latest_sender_name: str,
    ) -> bool:
        if base_reason not in {"target_chat_db_activity", "db_changed_target_unchanged"}:
            return False
        return bool(latest_sender_id or latest_sender_name)

    def _popup_action(
        self,
        previous_state: dict[str, Any],
        window: WindowInfo | None,
        *,
        base_reason: str,
        has_new_message: bool,
        latest_type: str,
        latest_text: str,
        latest_sender_id: str,
        latest_sender_name: str,
    ) -> tuple[str, int | None]:
        last_popup_at_ms = int(previous_state.get("last_popup_at_ms", 0) or 0)
        if not self.config.db_parse.popup_enabled or not self.config.window.focus_allowed:
            return "popup_disabled", last_popup_at_ms or None

        if not window:
            if (
                self.config.db_parse.popup_existing_window_only
                and base_reason in {"target_chat_db_activity", "memory_changed_without_db_change", "target_chat_message_candidate"}
            ):
                self.store.append_audit(
                    {
                        "scope": "db",
                        "event": "popup_window_missing",
                        "target_chat_title": self.config.db_parse.target_chat_title,
                    }
                )
                return "popup_window_missing", last_popup_at_ms or None
            return "popup_no_action", last_popup_at_ms or None

        window_id = str(window.window_id).strip()
        if not window_id:
            return "popup_no_action", last_popup_at_ms or None

        allow_db_activity_popup = self._should_popup_on_db_activity(
            base_reason=base_reason,
            latest_sender_id=latest_sender_id,
            latest_sender_name=latest_sender_name,
        )
        if not has_new_message and not allow_db_activity_popup:
            return "popup_no_new_message", last_popup_at_ms or None

        if not latest_text and latest_type == "unknown":
            if not allow_db_activity_popup:
                self.store.append_audit(
                    {
                        "scope": "db",
                        "event": "popup_skipped_unknown",
                        "target_chat_title": self.config.db_parse.target_chat_title,
                        "message_type": latest_type,
                        "latest_text": latest_text,
                        "latest_sender_id": latest_sender_id,
                        "latest_sender_name": latest_sender_name,
                        "window_id": window_id,
                    }
                )
                return "popup_skipped_unknown", last_popup_at_ms or None

        if latest_type in {"file", "image"}:
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "non_text_detected",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "message_type": latest_type,
                    "latest_text": latest_text,
                    "latest_sender_id": latest_sender_id,
                    "latest_sender_name": latest_sender_name,
                    "window_id": window_id,
                }
            )

        now_ms = _now_ms()
        if last_popup_at_ms and now_ms - last_popup_at_ms < self.config.db_parse.popup_cooldown_ms:
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "popup_cooldown_skip",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "window_id": window_id,
                    "message_type": latest_type,
                    "latest_text": latest_text,
                    "latest_sender_id": latest_sender_id,
                    "latest_sender_name": latest_sender_name,
                }
            )
            return "popup_cooldown_skip", last_popup_at_ms

        try:
            activate_window(window_id, self.config.window)
        except Exception as exc:
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "popup_failed",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "window_id": window_id,
                    "error": str(exc),
                }
            )
            return "popup_failed", last_popup_at_ms or None

        self.store.append_audit(
            {
                "scope": "db",
                "event": "popup_activated",
                "target_chat_title": self.config.db_parse.target_chat_title,
                "window_id": window_id,
                "message_type": latest_type,
                "latest_text": latest_text,
                "latest_sender_id": latest_sender_id,
                "latest_sender_name": latest_sender_name,
                "activation_mode": "candidate" if has_new_message else "db_activity",
            }
        )
        return "popup_activated", now_ms

    def _run_memory_mode(self, account_dir: Path) -> dict[str, Any]:
        pid = main_wechat_pid()
        if pid is None:
            raise MemoryProbeError("wechat_pid_not_found")
        self_username = _derive_self_username(account_dir)

        target_cache_path = self.config.state_dir / "db_target_cache.json"
        resolution_error: str | None = None
        try:
            resolution = run_memory_probe(
                self.config.db_parse.target_chat_title,
                pid,
                use_sudo=self.config.db_parse.memory_probe_use_sudo,
                timeout_s=self.config.db_parse.memory_probe_timeout_s,
                self_username=self_username,
            )
            target_cache_path.write_text(json.dumps(resolution, ensure_ascii=False, indent=2), encoding="utf-8")
        except MemoryProbeError as exc:
            cached = self._load_json(target_cache_path)
            if not cached:
                raise
            resolution = cached
            resolution_error = str(exc)

        previous_state = dict(self.store.runtime.db_detector_state)
        previous_snapshot = previous_state.get("db_snapshot")
        previous_db_hash = str(previous_state.get("db_snapshot_hash", "")).strip() or None
        previous_context_hash = str(previous_state.get("target_context_hash", "")).strip() or None
        previous_username = str(previous_state.get("target_chat_username", "")).strip() or None
        previous_fingerprints = {
            str(item).strip()
            for item in list(previous_state.get("message_candidate_fingerprints") or [])
            if str(item).strip()
        }

        current_snapshot = snapshot_paths(db_snapshot_paths(account_dir))
        current_db_hash = _json_hash(current_snapshot)
        context_hash = str(resolution.get("context_hash", "")).strip() or None
        context_strings = list(resolution.get("context_strings") or [])[:12]
        username = str(resolution.get("target_chat_username", "")).strip() or None
        changed_paths = changed_snapshot_paths(previous_snapshot if isinstance(previous_snapshot, dict) else None, current_snapshot)
        latest_sender_id = str(resolution.get("active_sender_id", "")).strip()
        latest_sender_name = str(resolution.get("active_sender_name", "")).strip()
        current_candidates = _normalize_message_candidates(
            resolution,
            sender_id=latest_sender_id,
            sender_name=latest_sender_name,
        )
        latest_candidate = _pick_latest_candidate(previous_fingerprints, current_candidates)
        latest_message_fingerprint = latest_candidate["fingerprint"] if latest_candidate else None

        if previous_username != username and username:
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "target_chat_resolved",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "target_chat_username": username,
                    "wechat_pid": pid,
                }
            )

        if previous_db_hash is None or previous_context_hash is None:
            reason = "baseline_initialized"
        elif current_db_hash != previous_db_hash and context_hash != previous_context_hash:
            reason = "target_chat_db_activity"
        elif current_db_hash != previous_db_hash:
            reason = "db_changed_target_unchanged"
        elif context_hash != previous_context_hash:
            reason = "memory_changed_without_db_change"
        else:
            reason = "no_change"

        has_new_message = latest_candidate is not None and reason != "no_change"
        if latest_message_fingerprint and not previous_fingerprints and reason != "no_change":
            reason = "baseline_initialized"
        elif has_new_message:
            reason = "target_chat_message_candidate"

        target_window = self._find_target_window()

        payload = {
            "driver_mode": "db_detect_memory",
            "resolver_mode": "memory",
            "account_dir": str(account_dir),
            "watch_paths": [
                str(account_dir / "db_storage" / "session"),
            ],
            "target_chat_title": self.config.db_parse.target_chat_title,
            "target_chat_username": username,
            "self_username": self_username,
            "wechat_pid": pid,
            "candidate_usernames": list(resolution.get("candidate_usernames") or [])[:5],
            "sender_candidates": list(resolution.get("sender_candidates") or [])[:5],
            "sender_name_candidates": dict(resolution.get("sender_name_candidates") or {}),
            "message_candidates": current_candidates[:20],
            "target_context_strings": context_strings,
            "target_context_hash": context_hash,
            "db_snapshot": current_snapshot,
            "db_snapshot_hash": current_db_hash,
            "changed_paths": changed_paths,
            "last_wake_reason": reason,
            "updated_at_ms": _now_ms(),
            "last_message_fingerprint": latest_message_fingerprint,
            "message_candidate_fingerprints": [item["fingerprint"] for item in current_candidates[:50]],
            "latest_sender_id": latest_sender_id,
            "latest_sender_name": latest_sender_name,
        }
        if target_window:
            payload.update(
                {
                    "window_id": target_window.window_id,
                    "window_title": target_window.title,
                }
            )
        else:
            payload.update(
                {
                    "window_id": None,
                    "window_title": None,
                }
            )
        if latest_candidate:
            payload.update(
                {
                    "latest_message_type": latest_candidate.get("kind", "unknown"),
                    "latest_message_direction": "unknown",
                    "latest_text": latest_candidate.get("text", ""),
                    "latest_message_confidence": 1.0,
                }
            )
        else:
            payload.update(
                {
                    "latest_message_type": "unknown",
                    "latest_message_direction": "unknown",
                    "latest_text": "",
                    "latest_message_confidence": 0.0,
                }
            )
        if resolution_error:
            payload["memory_probe_error"] = resolution_error

        if reason == "target_chat_message_candidate":
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "target_chat_message_candidate",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "target_chat_username": username,
                    "message_type": payload["latest_message_type"],
                    "latest_text": payload["latest_text"],
                    "latest_sender_id": latest_sender_id,
                    "latest_sender_name": latest_sender_name,
                    "window_id": payload["window_id"],
                }
            )
        elif reason == "target_chat_db_activity":
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "target_chat_db_activity",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "target_chat_username": username,
                    "changed_paths": changed_paths,
                    "latest_sender_id": latest_sender_id,
                    "latest_sender_name": latest_sender_name,
                    "target_context_strings": context_strings,
                }
            )
        elif reason == "memory_changed_without_db_change":
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "target_chat_memory_changed",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "target_chat_username": username,
                    "latest_sender_id": latest_sender_id,
                    "latest_sender_name": latest_sender_name,
                    "target_context_strings": context_strings,
                }
            )
        elif reason == "db_changed_target_unchanged":
            self.store.append_audit(
                {
                    "scope": "db",
                    "event": "db_changed_target_unchanged",
                    "target_chat_title": self.config.db_parse.target_chat_title,
                    "target_chat_username": username,
                    "changed_paths": changed_paths,
                    "latest_sender_id": latest_sender_id,
                    "latest_sender_name": latest_sender_name,
                }
            )

        popup_decision, popup_at_ms = self._popup_action(
            previous_state,
            target_window,
            base_reason=reason,
            has_new_message=has_new_message and reason != "baseline_initialized",
            latest_type=str(payload["latest_message_type"]),
            latest_text=str(payload["latest_text"]),
            latest_sender_id=latest_sender_id,
            latest_sender_name=latest_sender_name,
        )
        payload["popup_decision"] = popup_decision
        payload["last_popup_at_ms"] = popup_at_ms

        self.store.runtime.db_detector_state = payload
        self.store.runtime.last_status = {
            "action": "db_detect",
            "detail": f"{reason}:{popup_decision}",
            "updated_at_ms": payload["updated_at_ms"],
        }
        self.store.save()
        return payload

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _resolve_account_dir(self) -> Path:
        configured = self.config.db_parse.account_dir.strip()
        if configured and configured != "auto":
            path = Path(configured).expanduser().resolve()
            if path.exists():
                return path
        account = active_account_dir(Path(self.config.downloads.root_dir).expanduser())
        if account:
            return account
        root = Path(self.config.downloads.root_dir).expanduser()
        candidates = sorted(
            [path for path in root.iterdir() if path.is_dir() and path.name.startswith("wxid_")],
            key=lambda item: item.name,
        )
        if not candidates:
            raise SqlcipherError("account_dir_not_found")
        return candidates[0]
