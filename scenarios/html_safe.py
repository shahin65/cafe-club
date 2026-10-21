import re
from html import escape, unescape
from html.parser import HTMLParser
from urllib.parse import urlparse

from django.utils.html import linebreaks, strip_tags

ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "h2",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "span",
    "div",
    "blockquote",
    "figure",
    "figcaption",
}
VOID_TAGS = {"br", "img"}
ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
    "p": {"style"},
    "div": {"style"},
    "h2": {"style"},
    "h3": {"style"},
    "h4": {"style"},
    "span": {"style"},
}
STYLE_OK = re.compile(
    r"^(text-align|width|height|max-width|margin|margin-left|margin-right|float)\s*:\s*[^;]+$",
    re.I,
)


def _safe_style(value):
    parts = []
    for chunk in (value or "").split(";"):
        item = chunk.strip()
        if item and STYLE_OK.match(item):
            parts.append(item)
    return "; ".join(parts)


def _safe_href(value):
    url = (value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https", "mailto"}:
        return url
    if url.startswith("#") or url.startswith("/"):
        return url
    return ""


def _safe_src(value):
    url = (value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        return url
    if url.startswith("/media/") or url.startswith("/static/"):
        return url
    return ""


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            if tag not in VOID_TAGS:
                self.skip += 1
            return
        if self.skip:
            return
        bits = [tag]
        allowed = ALLOWED_ATTRS.get(tag, set())
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or value is None:
                continue
            if name == "style":
                value = _safe_style(value)
                if not value:
                    continue
            elif name == "href":
                value = _safe_href(value)
                if not value:
                    continue
            elif name == "src":
                value = _safe_src(value)
                if not value:
                    continue
            elif name == "target" and value != "_blank":
                continue
            bits.append(f'{name}="{escape(value, quote=True)}"')
        if tag == "img" and not any(part.startswith("src=") for part in bits[1:]):
            return
        if tag == "a" and any(item[0].lower() == "target" for item in attrs):
            bits.append('rel="noopener noreferrer"')
        if tag in VOID_TAGS:
            self.out.append("<" + " ".join(bits) + " />")
        else:
            self.out.append("<" + " ".join(bits) + ">")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            if tag not in VOID_TAGS and self.skip:
                self.skip -= 1
            return
        if self.skip:
            return
        if tag not in VOID_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(escape(data, quote=False))

    def handle_entityref(self, name):
        if not self.skip:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skip:
            self.out.append(f"&#{name};")


def sanitize_page_html(value):
    raw = unescape(value or "").strip()
    if not raw:
        return ""
    if "<" not in raw:
        return linebreaks(raw)
    parser = _Sanitizer()
    parser.feed(raw)
    parser.close()
    return "".join(parser.out)


def plain_page_text(value):
    return " ".join(strip_tags(value or "").split())
