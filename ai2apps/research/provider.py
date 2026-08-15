"""Provider-independent, bounded web search and page extraction."""

from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Protocol


class WebProviderError(RuntimeError):
    """A safe, user-displayable web provider failure."""


class WebProvider(Protocol):
    name: str

    def search(self, query: str, *, limit: int = 5) -> dict: ...

    def fetch(self, url: str, *, max_chars: int = 60_000) -> dict: ...


@dataclass(frozen=True, slots=True)
class HttpResponse:
    url: str
    content_type: str
    body: bytes
    truncated: bool


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SafeHttpClient:
    """Small HTTP client which rejects local/private targets and oversized bodies."""

    ALLOWED_TYPES = frozenset(
        {"text/html", "application/xhtml+xml", "text/plain", "application/json"}
    )

    def __init__(
        self,
        *,
        timeout_seconds: float = 12.0,
        max_bytes: int = 2 * 1024 * 1024,
        max_redirects: int = 4,
        resolver=socket.getaddrinfo,
        opener=None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.resolver = resolver
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    def _validate_url(self, url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in {"http", "https"}:
            raise WebProviderError("Only public HTTP(S) URLs are supported")
        if not parts.hostname or parts.username is not None or parts.password is not None:
            raise WebProviderError("URL must contain a public host and no credentials")
        try:
            port = parts.port or (443 if parts.scheme == "https" else 80)
        except ValueError as exc:
            raise WebProviderError("URL has an invalid port") from exc
        host = parts.hostname.encode("idna").decode("ascii")
        try:
            addresses = self.resolver(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise WebProviderError(f"Could not resolve web host: {host}") from exc
        if not addresses:
            raise WebProviderError(f"Could not resolve web host: {host}")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address[4][0])
            except ValueError as exc:
                raise WebProviderError("Web host resolved to an invalid address") from exc
            if not ip.is_global:
                raise WebProviderError("Local, private, and reserved web hosts are blocked")
        return urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc, parts.path or "/", parts.query, "")
        )

    def get(self, url: str) -> HttpResponse:
        current = url
        for redirect_count in range(self.max_redirects + 1):
            current = self._validate_url(current)
            request = urllib.request.Request(
                current,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36 "
                        "AI2Apps-Research/1.0"
                    ),
                    "Accept": "text/html,application/xhtml+xml,text/plain,application/json",
                    "Accept-Encoding": "identity",
                },
            )
            try:
                response = self.opener.open(request, timeout=self.timeout_seconds)
            except urllib.error.HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    location = exc.headers.get("Location")
                    if not location or redirect_count >= self.max_redirects:
                        raise WebProviderError("Web redirect limit exceeded") from exc
                    current = urllib.parse.urljoin(current, location)
                    continue
                raise WebProviderError(f"Web request failed with HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise WebProviderError(f"Web request failed: {exc}") from exc
            with response:
                final_url = response.geturl() or current
                # urllib handlers may still supply a final redirected URL.
                self._validate_url(final_url)
                content_type = response.headers.get_content_type().lower()
                if content_type not in self.ALLOWED_TYPES:
                    raise WebProviderError(f"Unsupported web content type: {content_type}")
                declared = response.headers.get("Content-Length")
                if declared and declared.isdigit() and int(declared) > self.max_bytes:
                    raise WebProviderError("Web response exceeds the configured size limit")
                body = response.read(self.max_bytes + 1)
                truncated = len(body) > self.max_bytes
                return HttpResponse(
                    url=final_url,
                    content_type=content_type,
                    body=body[: self.max_bytes],
                    truncated=truncated,
                )
        raise WebProviderError("Web redirect limit exceeded")


def _source_id(url: str) -> str:
    normalized = urllib.parse.urlunsplit(urllib.parse.urlsplit(url)._replace(fragment=""))
    return "src_" + hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _decode_body(response: HttpResponse) -> str:
    # UTF-8 covers modern search responses; replacement keeps extraction bounded
    # and deterministic when a page advertises an incorrect charset.
    return response.body.decode("utf-8", errors="replace")


class _BingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._result: dict[str, str] | None = None
        self._in_h2 = False
        self._link: dict[str, str] | None = None
        self._snippet: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        classes = set(values.get("class", "").split())
        if tag == "li" and "b_algo" in classes:
            self._result = {"url": "", "title": "", "snippet": ""}
        elif self._result is not None and tag == "h2":
            self._in_h2 = True
        elif self._result is not None and self._in_h2 and tag == "a":
            self._link = {"url": values.get("href", ""), "title": ""}
        elif self._result is not None and tag == "p" and not self._result["snippet"]:
            self._snippet = []

    def handle_data(self, data: str) -> None:
        if self._link is not None:
            self._link["title"] += data
        if self._snippet is not None:
            self._snippet.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link is not None:
            raw_url = html.unescape(self._link["url"])
            title = " ".join(self._link["title"].split())
            if (
                self._result is not None
                and title
                and raw_url.startswith(("http://", "https://"))
            ):
                self._result.update(title=title, url=raw_url)
            self._link = None
        if tag == "h2":
            self._in_h2 = False
        if self._snippet is not None and tag == "p":
            snippet = " ".join("".join(self._snippet).split())
            if snippet and self._result is not None:
                self._result["snippet"] = snippet
            self._snippet = None
        if tag == "li" and self._result is not None:
            if self._result["url"] and self._result["title"]:
                self.results.append(self._result)
            self._result = None


class _ReadableHTMLParser(HTMLParser):
    SKIP = frozenset({"script", "style", "noscript", "svg", "canvas", "template"})
    BLOCK = frozenset(
        {"article", "main", "section", "p", "div", "li", "h1", "h2", "h3", "h4", "br"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self.text: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if not self._skip_depth and tag in self.BLOCK:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        if not self._skip_depth and tag in self.BLOCK:
            self.text.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title.append(data)
        self.text.append(data)

    def result(self) -> tuple[str, str]:
        title = " ".join("".join(self.title).split())
        lines = []
        for line in "".join(self.text).splitlines():
            cleaned = " ".join(line.split())
            if cleaned and (not lines or lines[-1] != cleaned):
                lines.append(cleaned)
        return title, "\n".join(lines)


class BingWebProvider:
    """No-key search provider plus safe public-page extraction."""

    name = "bing"

    def __init__(self, client: SafeHttpClient | None = None, *, cache_ttl: int = 300):
        self.client = client or SafeHttpClient()
        self.cache_ttl = cache_ttl
        self._cache: dict[tuple, tuple[float, dict]] = {}

    def _cached(self, key: tuple):
        item = self._cache.get(key)
        if item is None or item[0] <= time.monotonic():
            self._cache.pop(key, None)
            return None
        # Provider results are JSON data; copying avoids callers mutating cache state.
        return json.loads(json.dumps(item[1], ensure_ascii=False))

    def _store(self, key: tuple, value: dict) -> dict:
        self._cache[key] = (time.monotonic() + self.cache_ttl, value)
        return json.loads(json.dumps(value, ensure_ascii=False))

    def search(self, query: str, *, limit: int = 5) -> dict:
        query = " ".join(query.split())
        key = ("search", query.casefold(), limit)
        cached = self._cached(key)
        if cached is not None:
            cached["cached"] = True
            return cached
        url = "https://www.bing.com/search?" + urllib.parse.urlencode(
            {"q": query, "count": limit}
        )
        response = self.client.get(url)
        parser = _BingParser()
        parser.feed(_decode_body(response))
        results = []
        seen = set()
        for item in parser.results:
            normalized = item["url"].split("#", 1)[0]
            if normalized in seen:
                continue
            seen.add(normalized)
            results.append({**item, "url": normalized, "source_id": _source_id(normalized)})
            if len(results) >= limit:
                break
        if not results:
            raise WebProviderError("Search provider returned no readable results")
        return self._store(
            key,
            {
                "provider": self.name,
                "query": query,
                "count": len(results),
                "results": results,
                "cached": False,
            },
        )

    def fetch(self, url: str, *, max_chars: int = 60_000) -> dict:
        key = ("fetch", url, max_chars)
        cached = self._cached(key)
        if cached is not None:
            cached["cached"] = True
            return cached
        response = self.client.get(url)
        decoded = _decode_body(response)
        if response.content_type in {"text/html", "application/xhtml+xml"}:
            parser = _ReadableHTMLParser()
            parser.feed(decoded)
            title, text = parser.result()
        elif response.content_type == "application/json":
            title = ""
            try:
                text = json.dumps(json.loads(decoded), ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                text = decoded
        else:
            title, text = "", decoded
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        char_truncated = len(text) > max_chars
        text = text[:max_chars]
        value = {
            "provider": self.name,
            "source_id": _source_id(response.url),
            "url": response.url,
            "title": title,
            "content_type": response.content_type,
            "text": text,
            "bytes_read": len(response.body),
            "truncated": response.truncated or char_truncated,
            "fetched_at": datetime.now(UTC).isoformat(),
            "cached": False,
        }
        return self._store(key, value)
