"""将彩虹助手风格的自定义标签转换为 Telegram HTML 格式。"""

from __future__ import annotations

import re

TAG_PAIRS: list[tuple[str, str, str]] = [
    ("[加粗]", "<b>", "</b>"),
    ("[斜体]", "<i>", "</i>"),
    ("[下划线]", "<u>", "</u>"),
    ("[删除线]", "<s>", "</s>"),
    ("[剧透]", "<tg-spoiler>", "</tg-spoiler>"),
    ("[引用]", "<blockquote>", "</blockquote>"),
]

LINK_PATTERN = re.compile(r"\[链接=([^\]]+)\]")
CODE_BLOCK_PATTERN = re.compile(r"\[代码块\](.*?)\[/代码块\]", re.DOTALL)
MONO_PATTERN = re.compile(r"\[等宽\](.*?)\[/等宽\]", re.DOTALL)
TRAILING_TAG_NAMES = [t[0] for t in TAG_PAIRS]


def parse_rich_text(text: str) -> tuple[str, str | None]:
    if not _has_rich_tags(text):
        return text, None

    lines = text.split("\n")
    parsed_lines = [_parse_line(line) for line in lines]
    result = "\n".join(parsed_lines)

    result = CODE_BLOCK_PATTERN.sub(r"<pre>\1</pre>", result)
    result = MONO_PATTERN.sub(r"<code>\1</code>", result)

    return result, "html"


def _parse_line(line: str) -> str:
    content = line
    wrappers: list[tuple[str, str]] = []

    link_match = LINK_PATTERN.search(content)
    if link_match:
        url = link_match.group(1)
        if not url.startswith("http"):
            url = f"https://{url}"
        content = LINK_PATTERN.sub("", content)
        wrappers.append((f'<a href="{url}">', "</a>"))

    while True:
        stripped = False
        for tag, open_tag, close_tag in TAG_PAIRS:
            if content.endswith(tag):
                content = content[: -len(tag)].rstrip()
                wrappers.insert(0, (open_tag, close_tag))
                stripped = True
                break
        if not stripped:
            break

    result = content
    for open_tag, close_tag in wrappers:
        result = f"{open_tag}{result}{close_tag}"
    return result


def _has_rich_tags(text: str) -> bool:
    markers = TRAILING_TAG_NAMES + ["[链接=", "[代码块]", "[等宽]"]
    return any(m in text for m in markers)
