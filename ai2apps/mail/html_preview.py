"""Rebuild passive email markup for the sandboxed Mail reading pane."""

from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

from .remote_images import image_url

_TAGS = frozenset("""
    a address article b blockquote br caption center code col colgroup dd div dl dt
    body em font h1 h2 h3 h4 h5 h6 hr i li ol p pre s section small span strong sub sup
    table tbody td tfoot th thead tr u ul wbr
""".split())
_VOID = frozenset({"br", "col", "hr", "wbr"})
_SKIP = frozenset({
    "head", "title", "script", "style", "template", "noscript", "iframe", "svg", "math",
    "object", "audio", "video", "textarea", "select",
})
_STYLES = frozenset("""
    background-color border border-top border-right border-bottom border-left
    border-color border-style border-width border-collapse border-spacing border-radius
    color display font-family font-size font-style font-weight height letter-spacing
    line-height margin margin-top margin-right margin-bottom margin-left max-width
    min-width max-height min-height table-layout box-sizing
    padding padding-top padding-right padding-bottom padding-left text-align
    text-decoration text-transform vertical-align width white-space
""".split())
_STYLE_VALUE = re.compile(r"""[a-zA-Z0-9 #.,%'"-]{1,160}""")
_DIMENSION = re.compile(r"(?:[0-9]{1,4}%?)")
_COLOR = re.compile(r"(?:#[0-9a-fA-F]{3,8}|[a-zA-Z]{1,24})")
_IDENTIFIERS = re.compile(r"[\w -]{1,240}", re.ASCII)
_SELECTOR = re.compile(r"""[a-zA-Z0-9_#. ,>+~*:\[\]="'-]{1,400}""")
_WIDTH_QUERY = r"\(\s*(?:min-|max-)?(?:device-)?width\s*:\s*[0-9]{1,4}(?:\.\d{1,2})?(?:px|em|rem)\s*\)"
_MEDIA = re.compile(
    rf"(?:@media\s+)(?:(?:only\s+)?screen\s+and\s+)?{_WIDTH_QUERY}(?:\s+and\s+{_WIDTH_QUERY})*",
    re.IGNORECASE,
)


def _styles(value):
    rules = []
    for declaration in value.split(";"):
        key, _, raw = declaration.partition(":")
        key, raw = key.strip().lower(), raw.strip()
        # No functions, escapes, URLs, imports, or custom properties.
        important = re.search(r"\s*!\s*important$", raw, re.IGNORECASE)
        if important:
            raw = raw[:important.start()].rstrip()
        # Keep solid fills written as shorthand without allowing background
        # images. Email buttons often pair this fill with dark text.
        if key == "background" and _COLOR.fullmatch(raw):
            key = "background-color"
        if key in _STYLES and _STYLE_VALUE.fullmatch(raw):
            rules.append(f"{key}:{raw}" + (" !important" if important else ""))
    return ";".join(rules)


def _stylesheet(source):
    """Retain simple layout rules and width queries, never resource declarations."""
    source = re.sub(r"/\*.*?\*/", "", source[:32768], flags=re.DOTALL)
    tokens = iter(re.findall(r"[^{}]+|[{}]", source))

    def rules(depth=0):
        output = []
        for token in tokens:
            selector = token.strip()
            if selector == "}":
                break
            if selector == "{" or next(tokens, None) != "{":
                break
            # Drop preceding statement rules such as @import, not the next selector.
            selector = selector.rsplit(";", 1)[-1].strip()
            if depth == 0 and _MEDIA.fullmatch(selector):
                inner = rules(1)
                if inner:
                    query = re.sub(r"device-width", "width", selector, flags=re.IGNORECASE)
                    output.append(f"{query}{{{inner}}}")
                continue
            parts = []
            braces = 1
            for part in tokens:
                if part == "{":
                    braces += 1
                elif part == "}":
                    braces -= 1
                    if not braces:
                        break
                parts.append(part)
            if _SELECTOR.fullmatch(selector) and not any(part in {"{", "}"} for part in parts):
                style = _styles("".join(parts))
                if style:
                    output.append(f"{selector}{{{style}}}")
        return "".join(output)

    return rules()


def _attributes(attrs):
    safe = {}
    for name, value in attrs:
        if not value:
            continue
        if name == "style":
            value = _styles(value)
            if not value:
                continue
        elif name in {"class", "id"}:
            if not _IDENTIFIERS.fullmatch(value):
                continue
        elif name in {"width", "height", "colspan", "rowspan", "cellspacing", "cellpadding", "border", "size"}:
            if not _DIMENSION.fullmatch(value):
                continue
        elif name in {"color", "bgcolor"}:
            if not _COLOR.fullmatch(value):
                continue
        elif name in {"align", "valign", "dir"}:
            if value not in {"left", "right", "center", "justify", "top", "middle", "bottom", "ltr", "rtl", "auto"}:
                continue
        else:
            continue
        safe[name] = value
    return "".join(f' {name}="{escape(value, quote=True)}"' for name, value in safe.items())


def _web_link(value):
    if not value or len(value) > 2048 or re.search(r"[\s\x00-\x1f\x7f\\]", value):
        return None
    try:
        target = urlsplit(value)
        if target.scheme in {"http", "https"} and target.hostname and target.username is None:
            return value
    except ValueError:
        pass
    return None


class _PassiveHTML(HTMLParser):
    def __init__(self, load_image=None):
        super().__init__(convert_charrefs=True)
        self.fragments = []
        self.skipped = []
        self.stack = []
        self.has_text = False
        self.load_image = load_image
        self.remote_images = 0
        self.loaded_images = 0
        self.style_data = None
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        if tag == "style" and self.skipped in ([], ["head"]):
            self.style_data = []
            return
        if tag in _SKIP:
            self.skipped.append(tag)
            return
        if tag == "img" and not self.skipped:
            self._image(dict(attrs))
            return
        if self.skipped or tag not in _TAGS or len(self.stack) >= 128:
            return
        link = _web_link(dict(attrs).get("href")) if tag == "a" else None
        safe_tag = "span" if tag == "a" and not link else tag
        # A live URL would let the frame navigate itself. Mail handles activation.
        action = f' href="#" data-mail-url="{escape(link, quote=True)}"' if link else ""
        self.fragments.append(f"<{safe_tag}{_attributes(attrs)}{action}>")
        if tag not in _VOID:
            self.stack.append((tag, safe_tag))

    def handle_startendtag(self, tag, attrs):
        if tag in _TAGS or tag == "img":
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "style" and self.style_data is not None:
            style = _stylesheet("".join(self.style_data))
            if style:
                self.stylesheets.append(f"<style>{style}</style>")
            self.style_data = None
            return
        if self.skipped:
            if tag == self.skipped[-1]:
                self.skipped.pop()
            return
        if tag in _TAGS and tag not in _VOID:
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    self._close_to(index)
                    break

    def _close_to(self, index):
        while len(self.stack) > index:
            self.fragments.append(f"</{self.stack.pop()[1]}>")

    def handle_data(self, data):
        if self.style_data is not None:
            self.style_data.append(data)
        elif not self.skipped:
            self.has_text |= bool(data.strip())
            self.fragments.append(escape(data))

    def markup(self):
        self._close_to(0)
        return "".join(self.stylesheets + self.fragments) if self.has_text or self.loaded_images else ""

    def _image(self, attrs):
        width, height = (attrs.get(name) or "" for name in ("width", "height"))
        if (not (attrs.get("alt") or "").strip()
                and all(re.fullmatch(r"[0-9]{1,3}", value) for value in (width, height))
                and min(int(width), int(height)) <= 1 and max(int(width), int(height)) <= 256):
            # Mail templates use single-pixel strips to size empty table rows
            # and columns. Keep the dimensions without fetching those pixels.
            style = _styles(attrs.get("style") or "")
            attributes = _attributes((("class", attrs.get("class")), ("id", attrs.get("id")),
                                      ("style", f"display:inline-block;width:{width}px;height:{height}px;{style}")))
            self.fragments.append(f'<span aria-hidden="true"{attributes}></span>')
            return
        url = image_url(attrs.get("src") or "")
        if not url or self.remote_images >= 12:
            return
        self.remote_images += 1
        src = self.load_image(url) if self.load_image else None
        if not src:
            return
        self.loaded_images += 1
        alt = escape((attrs.get("alt") or "")[:200], quote=True)
        attributes = _attributes((name, attrs.get(name)) for name in ("width", "height", "style", "class", "id"))
        self.fragments.append(f'<img src="{escape(src, quote=True)}" alt="{alt}"{attributes}>')


def formatted_html(source, load_image=None):
    parser = _PassiveHTML(load_image)
    parser.feed(source)
    parser.close()
    return parser.markup(), parser.remote_images, parser.loaded_images


def passive_html(source):
    return formatted_html(source)[0]
