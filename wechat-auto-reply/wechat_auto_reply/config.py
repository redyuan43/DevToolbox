from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _default_display() -> str:
    return os.environ.get("DISPLAY", ":1")


def _default_xauthority() -> str | None:
    env = os.environ.get("XAUTHORITY")
    if env:
        return env
    uid = os.getuid()
    candidates = [
        Path(f"/run/user/{uid}/gdm/Xauthority"),
        Path(f"/run/user/{uid}/Xauthority"),
        Path.home() / ".Xauthority",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


@dataclass(slots=True)
class Roi:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Roi":
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            width=int(data["width"]),
            height=int(data["height"]),
        )

    def to_mapping(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(slots=True)
class WindowConfig:
    monitor_mode: str = "standalone"
    title_regex: str = r"^(Weixin|微信)$"
    main_title_regex: str = r"^(Weixin|微信)$"
    class_name: str = "wechat"
    display: str = field(default_factory=_default_display)
    xauthority: str | None = field(default_factory=_default_xauthority)
    focus_allowed: bool = True
    calibration_key: str | None = None


@dataclass(slots=True)
class PollConfig:
    interval_ms: int = 2000


@dataclass(slots=True)
class ConflictConfig:
    user_idle_ms: int = 5000
    wechat_pause_ms: int = 30000
    send_conflict_cooldown_ms: int = 60000


@dataclass(slots=True)
class OllamaConfig:
    api_format: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    api_key: str | None = None
    vision_model: str = "qwen3-vl:latest"
    reply_model: str = "glm-4.7-flash:latest"
    timeout_s: int = 90
    disable_thinking: bool = True


@dataclass(slots=True)
class HistoryConfig:
    max_pages: int = 1
    scroll_mode: str = "page"
    enabled: bool = False


@dataclass(slots=True)
class DownloadsConfig:
    root_dir: str = str(Path.home() / "Documents" / "xwechat_files")
    organize_by_chat_title: bool = True
    policy: str = "all_inbound_files"
    poll_timeout_s: int = 30
    poll_interval_ms: int = 1000


@dataclass(slots=True)
class AttachmentsConfig:
    explicit_send_extensions: list[str] = field(default_factory=lambda: ["txt", "md"])
    chooser_open_delay_ms: int = 500
    post_send_delay_ms: int = 1200


@dataclass(slots=True)
class GuardWhitelistConfig:
    private_chats: list[str] = field(default_factory=list)
    group_chats: list[str] = field(default_factory=list)
    legacy_titles: list[str] = field(default_factory=list)

    @property
    def all_titles(self) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in [*self.private_chats, *self.group_chats, *self.legacy_titles]:
            title = item.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            deduped.append(title)
        return deduped

    def is_group(self, chat_name: str) -> bool:
        return chat_name.strip() in {item.strip() for item in self.group_chats if item.strip()}

    def is_allowed(self, chat_name: str) -> bool:
        return chat_name.strip() in set(self.all_titles)


@dataclass(slots=True)
class GuardContextConfig:
    strategy: str = "current_screen"


@dataclass(slots=True)
class GuardFilesConfig:
    auto_download_inbound: bool = True
    downloads: DownloadsConfig = field(default_factory=DownloadsConfig)


@dataclass(slots=True)
class GuardConfig:
    whitelist: GuardWhitelistConfig = field(default_factory=GuardWhitelistConfig)
    context: GuardContextConfig = field(default_factory=GuardContextConfig)
    files: GuardFilesConfig = field(default_factory=GuardFilesConfig)


@dataclass(slots=True)
class ToolsSendFileConfig:
    enabled: bool = True
    attachments: AttachmentsConfig = field(default_factory=AttachmentsConfig)


@dataclass(slots=True)
class ToolsConfig:
    send_file: ToolsSendFileConfig = field(default_factory=ToolsSendFileConfig)


@dataclass(slots=True)
class ExperimentalConfig:
    history: HistoryConfig = field(default_factory=HistoryConfig)


@dataclass(slots=True)
class ReplyConfig:
    system_prompt: str = (
        "你是一个谨慎、简洁、口语化的微信代回复助手。"
        "只输出可以直接发送给对方的最终回复，不要解释。"
    )
    per_contact_prompts: dict[str, str] = field(default_factory=dict)
    max_chars: int = 120
    blacklist_keywords: list[str] = field(
        default_factory=lambda: [
            "验证码",
            "付款",
            "转账",
            "二维码",
            "登录",
            "密码",
            "链接",
            "http://",
            "https://",
        ]
    )


@dataclass(slots=True)
class SafetyConfig:
    disallow_groups: bool = True
    disallow_links: bool = True
    require_confidence: float = 0.85
    dry_run: bool = False


@dataclass(slots=True)
class DbParseConfig:
    enabled: bool = False
    target_chat_title: str = "新技术讨论"
    sqlcipher_bin: str = "/usr/bin/sqlcipher"
    hook_log_path: str = str(
        Path.home() / ".local" / "state" / "wechat-auto-reply" / "db_hook.jsonl"
    )
    hook_library_path: str = str(
        Path.home() / ".local" / "state" / "wechat-auto-reply" / "libwechat_db_hook.so"
    )
    debounce_ms: int = 500
    account_dir: str = "auto"
    resolver_mode: str = "auto"
    memory_probe_use_sudo: bool = True
    memory_probe_timeout_s: int = 15
    popup_enabled: bool = True
    popup_cooldown_ms: int = 5000
    popup_existing_window_only: bool = True
    extract_non_text_metadata_only: bool = True


@dataclass(slots=True)
class AppConfig:
    window: WindowConfig = field(default_factory=WindowConfig)
    poll: PollConfig = field(default_factory=PollConfig)
    conflict: ConflictConfig = field(default_factory=ConflictConfig)
    guard: GuardConfig = field(default_factory=GuardConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    experimental: ExperimentalConfig = field(default_factory=ExperimentalConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    reply: ReplyConfig = field(default_factory=ReplyConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    db_parse: DbParseConfig = field(default_factory=DbParseConfig)
    state_dir: Path = field(
        default_factory=lambda: Path.home() / ".local" / "state" / "wechat-auto-reply"
    )
    config_dir: Path = field(
        default_factory=lambda: Path.home() / ".config" / "wechat-auto-reply"
    )

    @property
    def audit_log_path(self) -> Path:
        return self.state_dir / "audit.jsonl"

    @property
    def runtime_state_path(self) -> Path:
        return self.state_dir / "runtime_state.json"

    @property
    def pause_flag_path(self) -> Path:
        return self.state_dir / "paused.flag"

    @property
    def calibration_path(self) -> Path:
        return self.state_dir / "calibration.json"

    @property
    def whitelist(self) -> list[str]:
        return self.guard.whitelist.all_titles

    @property
    def history(self) -> HistoryConfig:
        return self.experimental.history

    @property
    def downloads(self) -> DownloadsConfig:
        return self.guard.files.downloads

    @property
    def attachments(self) -> AttachmentsConfig:
        return self.tools.send_file.attachments

    def is_group_chat(self, chat_name: str) -> bool:
        return self.guard.whitelist.is_group(chat_name)


def _load_dataclass(cls: type[Any], data: dict[str, Any] | None) -> Any:
    data = data or {}
    kwargs: dict[str, Any] = {}
    for name in cls.__dataclass_fields__:
        if name in data:
            kwargs[name] = data[name]
    return cls(**kwargs)


def _load_guard(raw: dict[str, Any], legacy_whitelist: list[str], legacy_downloads: dict[str, Any] | None) -> GuardConfig:
    guard_raw = raw.get("guard") or {}
    whitelist_raw = dict(guard_raw.get("whitelist") or {})
    if not any(key in whitelist_raw for key in ("private_chats", "group_chats", "legacy_titles")):
        whitelist_raw["legacy_titles"] = list(legacy_whitelist or [])

    files_raw = dict(guard_raw.get("files") or {})
    downloads_raw = files_raw.get("downloads")
    if downloads_raw is None:
        downloads_raw = legacy_downloads

    return GuardConfig(
        whitelist=_load_dataclass(GuardWhitelistConfig, whitelist_raw),
        context=_load_dataclass(GuardContextConfig, guard_raw.get("context")),
        files=GuardFilesConfig(
            auto_download_inbound=bool(files_raw.get("auto_download_inbound", True)),
            downloads=_load_dataclass(DownloadsConfig, downloads_raw),
        ),
    )


def _load_tools(raw: dict[str, Any], legacy_attachments: dict[str, Any] | None) -> ToolsConfig:
    tools_raw = raw.get("tools") or {}
    send_file_raw = dict(tools_raw.get("send_file") or {})
    attachments_raw = send_file_raw.get("attachments")
    if attachments_raw is None:
        attachments_raw = legacy_attachments
    return ToolsConfig(
        send_file=ToolsSendFileConfig(
            enabled=bool(send_file_raw.get("enabled", True)),
            attachments=_load_dataclass(AttachmentsConfig, attachments_raw),
        )
    )


def _load_experimental(raw: dict[str, Any], legacy_history: dict[str, Any] | None) -> ExperimentalConfig:
    experimental_raw = raw.get("experimental") or {}
    history_raw = dict(experimental_raw.get("history") or {})
    if not history_raw and legacy_history:
        max_pages = int(legacy_history.get("max_pages", 1) or 0)
        strategy = str(legacy_history.get("strategy", "disabled"))
        history_raw = {
            "enabled": max_pages > 0 and strategy != "disabled",
            "max_pages": max(1, max_pages or 1),
            "scroll_mode": legacy_history.get("scroll_mode", "page"),
        }
    return ExperimentalConfig(
        history=_load_dataclass(HistoryConfig, history_raw),
    )


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    reply_defaults = asdict(ReplyConfig())
    legacy_whitelist = list(raw.get("whitelist", []) or [])
    legacy_history = raw.get("history")
    legacy_downloads = raw.get("downloads")
    legacy_attachments = raw.get("attachments")
    cfg = AppConfig(
        window=_load_dataclass(WindowConfig, raw.get("window")),
        poll=_load_dataclass(PollConfig, raw.get("poll")),
        conflict=_load_dataclass(ConflictConfig, raw.get("conflict")),
        guard=_load_guard(raw, legacy_whitelist, legacy_downloads),
        tools=_load_tools(raw, legacy_attachments),
        experimental=_load_experimental(raw, legacy_history),
        ollama=_load_dataclass(OllamaConfig, raw.get("ollama")),
        reply=ReplyConfig(
            **{
                **reply_defaults,
                **(raw.get("reply") or {}),
            }
        ),
        safety=_load_dataclass(SafetyConfig, raw.get("safety")),
        db_parse=_load_dataclass(DbParseConfig, raw.get("db_parse")),
        state_dir=Path(raw.get("state_dir", AppConfig().state_dir)),
        config_dir=Path(raw.get("config_dir", AppConfig().config_dir)),
    )
    return cfg


def default_config_path() -> Path:
    return Path.home() / ".config" / "wechat-auto-reply" / "config.yaml"
