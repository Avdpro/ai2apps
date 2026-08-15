"""Canonical article formatting for the managed browser."""

from __future__ import annotations

import re
from html import escape, unescape

_BLANK_LINES = re.compile(r"\n{3,}")
_TAG = re.compile(r"<[^>]+>")


def article_html_to_markdown(
    html: str,
    *,
    title: str | None = None,
    byline: str | None = None,
    published_at: str | None = None,
) -> str:
    """Convert already-sanitized reader HTML into stable, compact Markdown."""

    try:
        from markdownify import markdownify
    except ImportError as exc:  # pragma: no cover - packaging guard
        raise RuntimeError(
            "browser.read_article requires the markdownify package"
        ) from exc

    def code_language(element) -> str | None:
        code = element.find("code")
        return None if code is None else code.attrs.get("data-ai2apps-code-lang")

    body = markdownify(
        html,
        heading_style="ATX",
        bullets="-",
        strip=["script", "style", "form", "button", "input", "textarea"],
        code_language_callback=code_language,
    ).strip()
    header: list[str] = []
    if title:
        header.append(f"# {title.strip()}")
    details = " · ".join(value.strip() for value in (byline, published_at) if value)
    if details:
        header.append(f"*{details}*")
    result = "\n\n".join([*header, body] if body else header)
    return _BLANK_LINES.sub("\n\n", result).strip()


def canonical_article_html(
    body_html: str,
    *,
    title: str | None = None,
    byline: str | None = None,
    published_at: str | None = None,
    language: str | None = None,
    direction: str | None = None,
) -> str:
    """Wrap sanitized reader content in a standalone semantic article."""

    attrs = ['data-ai2apps-reader="true"']
    if language:
        attrs.append(f'lang="{escape(language, quote=True)}"')
    if direction in {"ltr", "rtl", "auto"}:
        attrs.append(f'dir="{direction}"')
    header: list[str] = []
    if title:
        header.append(f"<h1>{escape(title)}</h1>")
    if byline:
        header.append(f'<p class="byline">{escape(byline)}</p>')
    if published_at:
        value = escape(published_at, quote=True)
        header.append(f'<time datetime="{value}">{escape(published_at)}</time>')
    header_html = f"<header>{''.join(header)}</header>" if header else ""
    return f"<article {' '.join(attrs)}>{header_html}{body_html}</article>"


def plain_text_from_html(html: str) -> str:
    """Small dependency-free fallback used for HTML-only responses and tests."""

    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", html))).strip()
