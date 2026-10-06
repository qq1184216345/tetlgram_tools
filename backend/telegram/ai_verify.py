from __future__ import annotations

import json
import re
import ssl
from typing import Any
from urllib import error, request
from urllib.request import ProxyHandler, build_opener, HTTPSHandler

from backend.config import settings

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.I)
_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json_payload(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    text = _THINK_RE.sub("", text).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_RE.search(text)
        if not match:
            raise
        return json.loads(match.group(0))


def _should_bypass_proxy(api_url: str) -> bool:
    """国内 MiniMax 节点直连更稳；走本地 Clash 代理易 SSL 异常。"""
    host = (api_url or "").lower()
    return "minimaxi.com" in host or "minimax.io" in host


async def ask_ai_for_verification(
    prompt: str,
    button_labels: list[str] | None = None,
) -> dict[str, Any]:
    """
    调用 OpenAI 兼容中转站，解析复杂加群验证。
    返回: {"action": "reply"|"click"|"none", "text": str, "button": str}
    """
    api_url = (getattr(settings, "ai_api_url", "") or "").strip()
    api_key = (getattr(settings, "ai_api_key", "") or "").strip()
    model = (getattr(settings, "ai_model", "") or "gpt-4o-mini").strip()

    if not api_url or not api_key:
        return {"action": "none", "text": "", "button": "", "error": "未配置 AI 中转站"}

    system = (
        "你是 Telegram 加群验证助手。根据验证消息内容，决定如何通过验证。"
        "只输出 JSON，不要其他文字。格式："
        '{"action":"reply|click|none","text":"若需回复则填答案","button":"若需点击则填按钮原文"}'
    )
    user_parts = [f"验证消息:\n{prompt}"]
    if button_labels:
        user_parts.append("可选按钮:\n" + "\n".join(f"- {b}" for b in button_labels))
    user_content = "\n\n".join(user_parts)

    endpoint = api_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/chat/completions"

    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    }
    # MiniMax-M3 默认带思考链，关闭后更易得到纯 JSON
    if "minimax" in model.lower() or "minimax" in api_url.lower():
        payload["thinking"] = {"type": "disabled"}

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        ctx = ssl.create_default_context()
        handlers: list[Any] = [HTTPSHandler(context=ctx)]
        if _should_bypass_proxy(api_url):
            handlers.insert(0, ProxyHandler({}))
        opener = build_opener(*handlers)
        with opener.open(req, timeout=45) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = (
            raw.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        parsed = _extract_json_payload(content)
        action = str(parsed.get("action", "none")).lower()
        return {
            "action": action if action in ("reply", "click", "none") else "none",
            "text": str(parsed.get("text", "") or ""),
            "button": str(parsed.get("button", "") or ""),
            "error": "",
        }
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"action": "none", "text": "", "button": "", "error": f"HTTP {exc.code}: {detail[:200]}"}
    except Exception as exc:
        return {"action": "none", "text": "", "button": "", "error": str(exc)}
