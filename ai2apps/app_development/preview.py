"""Bounded local asset embedding for opaque-origin, authenticated previews."""

import posixpath
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from .core import DraftError


def document(path, resource, resolve):
    """Embed classic JS/CSS only; do not grant the frame login or same-origin access."""
    limit = 2 * 1024 * 1024
    if path.stat().st_size > limit:
        raise DraftError("preview_too_large", "HTML preview exceeds 2 MiB.")
    budget = [path.stat().st_size]

    def asset(url):
        value = urlsplit(url)
        if value.scheme or value.netloc or value.path.startswith("/"):
            raise DraftError(
                "preview_external_asset", "Preview assets must be relative local files."
            )
        relative = posixpath.normpath(
            posixpath.join(posixpath.dirname(resource), unquote(value.path))
        )
        target = resolve(relative)
        with target.open("rb") as stream:
            data = stream.read(1024 * 1024 + 1)
        size = len(data)
        budget[0] += size
        if size > 1024 * 1024 or budget[0] > limit:
            raise DraftError(
                "preview_too_large", "Embedded preview assets exceed 2 MiB."
            )
        return data.decode("utf-8")

    class Embed(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.parts = []
            self.deferred = []
            self.replaced_script = False

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "script" and values.get("src"):
                if (
                    values.get("type", "").lower()
                    not in {"", "text/javascript", "application/javascript"}
                    or "async" in values
                ):
                    raise DraftError(
                        "preview_unsupported_script",
                        "Module and async scripts require host integration acceptance.",
                    )
                code = re.sub(
                    r"</script",
                    r"<\\/script",
                    asset(values["src"]),
                    flags=re.IGNORECASE,
                )
                block = "<script>" + code + "</script>"
                if "defer" in values:
                    self.deferred.append(block)
                else:
                    self.parts.append(block)
                self.replaced_script = True
            elif (
                tag == "link"
                and values.get("rel", "").lower() == "stylesheet"
                and values.get("href")
            ):
                css = re.sub(
                    r"</style", r"<\\/style", asset(values["href"]), flags=re.IGNORECASE
                )
                self.parts.append("<style>" + css + "</style>")
            else:
                self.parts.append(self.get_starttag_text())

        def handle_endtag(self, tag):
            if tag == "script" and self.replaced_script:
                self.replaced_script = False
                return
            if tag == "body":
                self.flush_deferred()
            self.parts.append("</" + tag + ">")

        def flush_deferred(self):
            self.parts.extend(self.deferred)
            self.deferred.clear()

        def handle_data(self, data):
            if not self.replaced_script:
                self.parts.append(data)

        def handle_startendtag(self, tag, attrs):
            if tag == "link":
                self.handle_starttag(tag, attrs)
            else:
                self.parts.append(self.get_starttag_text())

        def handle_entityref(self, name):
            self.handle_data("&" + name + ";")

        def handle_charref(self, name):
            self.handle_data("&#" + name + ";")

        def handle_comment(self, data):
            self.parts.append("<!--" + data + "-->")

        def handle_decl(self, data):
            self.parts.append("<!" + data + ">")

    parser = Embed()
    try:
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
        parser.flush_deferred()
    except UnicodeError as error:
        raise DraftError(
            "preview_encoding", "Preview HTML/JS/CSS must be UTF-8."
        ) from error
    return "".join(parser.parts)
