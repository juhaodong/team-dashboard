#!/usr/bin/env python3
"""Convert Markdown to an Atlassian Document Format (ADF) doc on stdout.

Usage: md2adf.py <file.md | ->

Blocks: ATX headings, paragraphs, bullet/ordered lists (nested by indentation), fenced code,
horizontal rules, GFM tables. Inline: **bold**, *italic*/_italic_, ~~strike~~, `code`,
[text](url), bare http(s) URLs, backslash escapes, trailing-two-space hard breaks, and
[@Name](accountid:<accountId>) for a Jira mention.
"""
import json
import re
import sys

FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
HR = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")

INLINE = re.compile(
    r"(?P<esc>\\([\\`*_{}\[\]()#+\-.!|~>]))"
    r"|(?P<code>`+)(?P<codetext>.+?)(?P=code)"
    r"|\[@(?P<mname>[^\]]+)\]\(accountid:(?P<mid>[^)\s]+)\)"
    r"|\[(?P<ltext>[^\]]+)\]\((?P<lurl>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
    r"|<(?P<auto>https?://[^>\s]+)>"
    r"|(?P<bare>https?://[^\s<>()]+[^\s<>().,;:!?'\"])"
    r"|\*\*(?P<b1>.+?)\*\*|__(?P<b2>.+?)__"
    r"|~~(?P<s>.+?)~~"
    r"|\*(?P<i1>[^*\s](?:[^*]*[^*\s])?)\*"
    r"|(?<![\w])_(?P<i2>[^_\s](?:[^_]*[^_\s])?)_(?![\w])"
)


def text_node(text, marks):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = [dict(m) for m in marks]
    return node


def inline(src, marks=()):
    out = []
    pos = 0

    def emit(text, m):
        if not text:
            return
        if out and out[-1]["type"] == "text" and out[-1].get("marks") == (list(m) or None):
            out[-1]["text"] += text
        else:
            out.append(text_node(text, list(m)))

    for match in INLINE.finditer(src):
        emit(src[pos:match.start()], marks)
        pos = match.end()
        g = match.groupdict()
        link_marks = [m for m in marks if m["type"] == "link"]
        if g["esc"]:
            emit(match.group(2), marks)
        elif g["code"]:
            emit(g["codetext"].strip() or g["codetext"], link_marks + [{"type": "code"}])
        elif g["mid"]:
            out.append({"type": "mention", "attrs": {"id": g["mid"], "text": "@" + g["mname"]}})
        elif g["lurl"]:
            out.extend(inline(g["ltext"], marks + ({"type": "link", "attrs": {"href": g["lurl"]}},)))
        elif g["auto"] or g["bare"]:
            url = g["auto"] or g["bare"]
            emit(url, marks + ({"type": "link", "attrs": {"href": url}},))
        elif g["b1"] or g["b2"]:
            out.extend(inline(g["b1"] or g["b2"], marks + ({"type": "strong"},)))
        elif g["s"]:
            out.extend(inline(g["s"], marks + ({"type": "strike"},)))
        else:
            out.extend(inline(g["i1"] or g["i2"], marks + ({"type": "em"},)))
    emit(src[pos:], marks)
    return out


def paragraph_lines(lines):
    content = []
    for n, line in enumerate(lines):
        hard = line.endswith("  ") or line.endswith("\\")
        line = line.rstrip("\\").strip()
        if content and content[-1]["type"] != "hardBreak":
            content.append(text_node(" ", []))
        content.extend(inline(line))
        if hard and n < len(lines) - 1:
            content.append({"type": "hardBreak"})
    merged = []
    for node in content:
        if merged and node["type"] == "text" == merged[-1]["type"] and node.get("marks") == merged[-1].get("marks"):
            merged[-1]["text"] += node["text"]
        else:
            merged.append(node)
    return {"type": "paragraph", "content": merged} if merged else None


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]


def table(header, rows):
    width = len(header)

    def row(cells, kind):
        cells = (cells + [""] * width)[:width]
        out = []
        for c in cells:
            para = paragraph_lines([c]) if c else None
            out.append({"type": kind, "attrs": {}, "content": [para or {"type": "paragraph", "content": []}]})
        return {"type": "tableRow", "content": out}

    return {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": [row(header, "tableHeader")] + [row(r, "tableCell") for r in rows],
    }


def indent_of(line):
    return len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())


def build_list(items, start, base):
    ordered = items[start][1]
    node = {"type": "orderedList" if ordered else "bulletList", "content": []}
    if ordered:
        node["attrs"] = {"order": items[start][3] or 1}
    i = start
    while i < len(items):
        ind, is_ordered, lines, _ = items[i]
        if ind < base or (ind == base and is_ordered != ordered and node["content"]):
            break
        if ind > base:
            sub, i = build_list(items, i, ind)
            node["content"][-1]["content"].append(sub)
            continue
        para = paragraph_lines(lines)
        node["content"].append({"type": "listItem", "content": [para or {"type": "paragraph", "content": []}]})
        i += 1
    return node, i


def convert(md):
    lines = md.splitlines()
    blocks = []
    para = []
    i = 0

    def flush():
        if para:
            p = paragraph_lines(para)
            if p:
                blocks.append(p)
            para.clear()

    while i < len(lines):
        line = lines[i]
        fence = FENCE.match(line)
        if fence:
            flush()
            marker, lang = fence.group(1), fence.group(2)
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(marker[0] * len(marker)):
                body.append(lines[i])
                i += 1
            i += 1
            node = {"type": "codeBlock", "attrs": {"language": lang} if lang else {}}
            if body:
                node["content"] = [{"type": "text", "text": "\n".join(body)}]
            blocks.append(node)
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        heading = HEADING.match(line)
        if heading:
            flush()
            node = {"type": "heading", "attrs": {"level": len(heading.group(1))}}
            content = inline(heading.group(2))
            if content:
                node["content"] = content
            blocks.append(node)
            i += 1
            continue
        if HR.match(line) and not para:
            flush()
            blocks.append({"type": "rule"})
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]) and "-" in lines[i + 1]:
            flush()
            header = split_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                rows.append(split_row(lines[i]))
                i += 1
            blocks.append(table(header, rows))
            continue
        item = LIST_ITEM.match(line)
        if item and not (para and item.group(2)[0].isdigit() and item.group(2) != "1."):
            flush()
            items = []
            while i < len(lines):
                cur = lines[i]
                m = LIST_ITEM.match(cur)
                if m:
                    marker = m.group(2)
                    order = int(marker[:-1]) if marker[0].isdigit() else None
                    items.append([indent_of(cur), order is not None, [m.group(3)], order])
                elif cur.strip() and items and (indent_of(cur) > 0 or not lines[i - 1].strip() == ""):
                    if FENCE.match(cur) or HEADING.match(cur) or (indent_of(cur) == 0 and HR.match(cur)):
                        break
                    items[-1][2].append(cur.strip())
                elif not cur.strip() and i + 1 < len(lines) and (
                    LIST_ITEM.match(lines[i + 1]) or (lines[i + 1].strip() and indent_of(lines[i + 1]) > 0)
                ):
                    pass
                else:
                    break
                i += 1
            pos = 0
            while pos < len(items):
                node, pos = build_list(items, pos, items[pos][0])
                blocks.append(node)
            continue
        para.append(line)
        i += 1
    flush()
    return {"type": "doc", "version": 1, "content": blocks}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: md2adf.py <file.md | ->")
    src = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8").read()
    json.dump(convert(src), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
