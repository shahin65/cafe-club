PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_SKIP_TAGS = {"script", "style", "textarea", "noscript"}


def persian_digits(value):
    return str(value).translate(PERSIAN_DIGITS)


def persianize_html_digits(html):
    html = str(html)
    out = []
    index = 0
    length = len(html)
    lower = html.lower()
    while index < length:
        if html.startswith("<!--", index):
            end = html.find("-->", index + 4)
            if end == -1:
                out.append(html[index:])
                break
            out.append(html[index : end + 3])
            index = end + 3
            continue
        if html[index] != "<":
            next_tag = html.find("<", index)
            chunk = html[index:] if next_tag == -1 else html[index:next_tag]
            out.append(chunk.translate(PERSIAN_DIGITS))
            if next_tag == -1:
                break
            index = next_tag
            continue
        close = html.find(">", index)
        if close == -1:
            out.append(html[index:])
            break
        tag = html[index + 1 : close].strip()
        name = tag.split(None, 1)[0].rstrip("/").lower() if tag else ""
        out.append(html[index : close + 1])
        index = close + 1
        if name in _SKIP_TAGS:
            closing = f"</{name}>"
            end = lower.find(closing, index)
            if end == -1:
                out.append(html[index:])
                break
            out.append(html[index : end + len(closing)])
            index = end + len(closing)
    return "".join(out)
