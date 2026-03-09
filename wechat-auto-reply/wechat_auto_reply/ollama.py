from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import requests


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: int = 180,
        *,
        api_format: str = "ollama",
        api_key: str | None = None,
        disable_thinking: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.api_format = api_format
        self.api_key = api_key
        self.disable_thinking = disable_thinking

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        images: list[Path] | None = None,
        temperature: float | None = None,
    ) -> str:
        if self.api_format == "openai":
            return self._generate_openai(
                model=model,
                prompt=prompt,
                images=images,
                temperature=temperature,
            )
        return self._generate_ollama(
            model=model,
            prompt=prompt,
            images=images,
            temperature=temperature,
        )

    def _generate_ollama(
        self,
        *,
        model: str,
        prompt: str,
        images: list[Path] | None = None,
        temperature: float | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if images:
            payload["images"] = [
                base64.b64encode(path.read_bytes()).decode("ascii") for path in images
            ]
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        if "response" not in data:
            raise OllamaError(f"Unexpected Ollama response: {data}")
        return str(data["response"]).strip()

    def _generate_openai(
        self,
        *,
        model: str,
        prompt: str,
        images: list[Path] | None = None,
        temperature: float | None = None,
    ) -> str:
        content: list[dict[str, Any]] | str
        if images:
            content = [{"type": "text", "text": prompt}]
            for path in images:
                mime = "image/png"
                suffix = path.suffix.lower()
                if suffix in {".jpg", ".jpeg"}:
                    mime = "image/jpeg"
                elif suffix == ".webp":
                    mime = "image/webp"
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{encoded}"},
                    }
                )
        else:
            content = prompt

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if self.disable_thinking:
            # Qwen documents use chat_template_kwargs.enable_thinking=false. LM Studio's
            # OpenAI bridge currently logs these fields but still renders <think>, so we
            # send the known variants and keep a separate output cleanup fallback.
            payload["chat_template_kwargs"] = {"enable_thinking": False}
            payload["enableThinking"] = False
            payload["reasoning"] = False

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        try:
            content_data = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OllamaError(f"Unexpected OpenAI-compatible response: {data}") from exc
        text = _coerce_content_to_text(content_data).strip()
        if self.disable_thinking:
            text = strip_reasoning_artifacts(text)
        return text


def _coerce_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def strip_reasoning_artifacts(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped

    without_tags = re.sub(
        r"<think>.*?</think>\s*",
        "",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    if without_tags and without_tags != stripped:
        stripped = without_tags

    marker_match = None
    for pattern in (
        r"(?:^|\n)\s*FINAL_REPLY:\s*",
        r"(?:^|\n)\s*FINAL_ANSWER:\s*",
        r"(?:^|\n)\s*Final Reply:\s*",
        r"(?:^|\n)\s*Final Answer:\s*",
        r"(?:^|\n)\s*最终回复[:：]\s*",
        r"(?:^|\n)\s*最终答案[:：]\s*",
    ):
        match = None
        for candidate in re.finditer(pattern, stripped, flags=re.IGNORECASE):
            match = candidate
        if match is not None:
            marker_match = match
            break
    if marker_match is not None:
        return stripped[marker_match.end() :].strip()

    return stripped


def extract_json_fragment(text: str) -> str:
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = fenced + re.findall(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue
    raise OllamaError(f"Model did not return valid JSON: {text}")


def parse_json_response(text: str) -> Any:
    return json.loads(extract_json_fragment(text))
