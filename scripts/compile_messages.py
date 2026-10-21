"""Compile project gettext catalogs without requiring GNU gettext."""

import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ESCAPES = {
    r"\n": "\n",
    r"\t": "\t",
    r"\r": "\r",
    r"\\": "\\",
    r"\"": '"',
}


def unescape(value):
    return re.sub(r"\\.", lambda match: ESCAPES.get(match.group(0), match.group(0)), value)


def parse_po(text):
    entries = []
    msgid = None
    msgstr = None
    mode = None

    def flush():
        nonlocal msgid, msgstr
        if msgid is not None and msgstr is not None:
            entries.append((msgid, msgstr))
        msgid = None
        msgstr = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            flush()
            mode = "id"
            msgid = unescape(line[6:].strip().strip('"'))
        elif line.startswith("msgstr "):
            mode = "str"
            msgstr = unescape(line[7:].strip().strip('"'))
        elif line.startswith('"') and line.endswith('"'):
            chunk = unescape(line[1:-1])
            if mode == "id":
                msgid += chunk
            elif mode == "str":
                msgstr += chunk
    flush()
    return entries


def write_mo(entries, path):
    pairs = sorted((key.encode("utf-8"), value.encode("utf-8")) for key, value in entries)
    keys = [pair[0] for pair in pairs]
    values = [pair[1] for pair in pairs]
    count = len(keys)
    table_size = 8 * count
    string_offset = 28 + (table_size * 2)
    origin = bytearray()
    translation = bytearray()
    blob = bytearray()
    position = string_offset
    for key in keys:
        origin += struct.pack("<II", len(key), position)
        blob += key + b"\x00"
        position += len(key) + 1
    for value in values:
        translation += struct.pack("<II", len(value), position)
        blob += value + b"\x00"
        position += len(value) + 1
    output = struct.pack("<Iiiiiii", 0x950412DE, 0, count, 28, 28 + table_size, 0, 0)
    path.write_bytes(output + origin + translation + blob)


def main():
    for po_path in (ROOT / "locale").glob("*/LC_MESSAGES/django.po"):
        mo_path = po_path.with_suffix(".mo")
        write_mo(parse_po(po_path.read_text(encoding="utf-8")), mo_path)
        print(mo_path)


if __name__ == "__main__":
    main()
