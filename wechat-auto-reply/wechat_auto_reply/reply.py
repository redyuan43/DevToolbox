from __future__ import annotations

import re
from dataclasses import dataclass

from .config import AppConfig
from .ollama import OllamaClient
from .vision import ConversationObservation


LINK_RE = re.compile(r"https?://|www\.", re.IGNORECASE)


@dataclass(slots=True)
class ReplyDecision:
    should_send: bool
    reply_text: str
    reason: str
    risk_flags: list[str]


def build_reply_prompt(
    config: AppConfig,
    chat_name: str,
    turns: list[dict[str, str]],
    inbound_text: str,
) -> str:
    turns_text = "\n".join(f"{item['role']}: {item['text']}" for item in turns[-6:])
    contact_prompt = config.reply.per_contact_prompts.get(chat_name, "")
    return (
        f"{config.reply.system_prompt}\n"
        f"联系人额外约束: {contact_prompt or '无'}\n"
        f"最近上下文:\n{turns_text or '(无)'}\n"
        f"对方刚发来的最新消息:\n{inbound_text}\n"
        "请直接生成一条可以发送的微信回复。\n"
        "只在最后一行输出最终结果，并且必须使用 `FINAL_REPLY:` 前缀。\n"
        "不要解释，不要输出思考过程，不要加引号。"
    )


def decide_reply(
    client: OllamaClient,
    config: AppConfig,
    observation: ConversationObservation,
    turns: list[dict[str, str]],
) -> ReplyDecision:
    if observation.direction != "inbound":
        return ReplyDecision(False, "", "latest_message_not_inbound", ["direction"])
    if observation.confidence < config.safety.require_confidence:
        return ReplyDecision(False, "", "low_confidence", ["confidence"])
    if not observation.latest_inbound_text:
        return ReplyDecision(False, "", "empty_message", ["empty"])
    prompt = build_reply_prompt(config, observation.chat_name, turns, observation.latest_inbound_text)
    reply_text = client.generate(
        model=config.ollama.reply_model,
        prompt=prompt,
        temperature=0.3,
    ).strip()
    if "FINAL_REPLY:" in reply_text:
        reply_text = reply_text.rsplit("FINAL_REPLY:", 1)[-1].strip()
    return enforce_guardrails(config, reply_text)


def enforce_guardrails(config: AppConfig, reply_text: str) -> ReplyDecision:
    flags: list[str] = []
    if not reply_text:
        flags.append("empty")
    if len(reply_text) > config.reply.max_chars:
        flags.append("too_long")
    if config.safety.disallow_links and LINK_RE.search(reply_text):
        flags.append("link")
    lowered = reply_text.lower()
    for keyword in config.reply.blacklist_keywords:
        if keyword.lower() in lowered:
            flags.append(f"blocked:{keyword}")
    if flags:
        return ReplyDecision(False, reply_text, "guardrail_blocked", flags)
    return ReplyDecision(True, reply_text, "ok", [])
