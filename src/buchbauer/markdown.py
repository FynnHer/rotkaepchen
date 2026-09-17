"""Ein kleiner, bewusst eng gehaltener Markdown-Leser.

Es wird nur die Teilmenge unterstuetzt, die ein Maerchenbuch braucht.
Der Parser erzeugt Bloecke, die der Builder direkt in ReportLab-Flowables
uebersetzen kann, und liefert Inline-Auszeichnungen bereits im
Mini-HTML von ReportLab (``<b>``/``<i>``) zurueck.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal

__all__ = ["Block", "Document", "parse_markdown", "parse_file", "inline_to_markup"]

BlockKind = Literal["heading", "paragraph", "quote", "list", "image", "break"]

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_IMAGE_LINE = re.compile(r"\A!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)\s*\Z")
_HEADING = re.compile(r"\A(?P<level>#{1,6})\s+(?P<text>.+?)\s*#*\s*\Z")
_LIST_ITEM = re.compile(r"\A[-*+]\s+(?P<text>.+)\Z")
_RULE = re.compile(r"\A(?:\*\s*){3,}\Z|\A(?:-\s*){3,}\Z|\A(?:_\s*){3,}\Z")


@dataclass
class Block:
    kind: BlockKind
    text: str = ""
    level: int = 0
    items: list[str] = field(default_factory=list)
    src: str = ""
    alt: str = ""


@dataclass
class Document:
    meta: dict[str, Any]
    blocks: list[Block]
    source: Path | None = None

    @property
    def plain_text(self) -> str:
        """Fliesstext ohne Auszeichnung - Grundlage der Asset-Zuordnung."""
        parts: list[str] = []
        for block in self.blocks:
            if block.kind in ("paragraph", "quote", "heading"):
                parts.append(block.text)
            elif block.kind == "list":
                parts.extend(block.items)
            elif block.kind == "image":
                parts.append(block.alt)
        return "\n".join(_strip_markup(p) for p in parts)


def _strip_markup(text: str) -> str:
    """Entfernt Auszeichnung, damit die Asset-Zuordnung nur Text sieht.

    Die Bloecke tragen bereits ReportLab-Markup, deshalb muessen auch die
    Tags weg - sonst zaehlen Alias-Treffer in Tagnamen mit.
    """
    without_tags = re.sub(r"<[^>]+>", "", text)
    without_entities = re.sub(r"&(?:amp|lt|gt|quot|#\d+);", " ", without_tags)
    return re.sub(r"[*_`]", "", without_entities)


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    lowered = value.lower()
    if lowered in ("true", "ja", "yes"):
        return True
    if lowered in ("false", "nein", "no"):
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """Liest den ``---``-Kopf einer Kapiteldatei (key: value, Listen inline)."""
    match = _FRONTMATTER.match(raw)
    if not match:
        return {}, raw
    meta: dict[str, Any] = {}
    pending_list_key: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if pending_list_key and line.lstrip().startswith("- "):
            meta.setdefault(pending_list_key, [])
            meta[pending_list_key].append(_parse_scalar(line.lstrip()[2:]))
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        if not value.strip():
            pending_list_key = key
            meta.setdefault(key, [])
            continue
        pending_list_key = None
        meta[key] = _parse_scalar(value)
    return meta, raw[match.end():]


def inline_to_markup(text: str) -> str:
    """Wandelt Inline-Markdown in das Mini-HTML von ReportLab um."""
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<b>\1</b>", out, flags=re.S)
    out = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<i>\1</i>", out, flags=re.S)
    out = re.sub(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])", r"<i>\1</i>", out, flags=re.S)
    out = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", out, flags=re.S)
    # Typografie: gerade Anfuehrungszeichen zu deutschen Gaensefuesschen.
    # Oeffnend ist ein Zitatzeichen nur am Textanfang oder nach Leerraum
    # bzw. einer oeffnenden Klammer - alles andere schliesst.
    out = re.sub(r'(?:\A|(?<=[\s(\[{\u2013\u2014-]))"', "„", out)
    out = out.replace('"', "“")
    out = out.replace("--", "–")
    out = out.replace("...", "…")
    return out.strip()


def _iter_groups(lines: list[str]) -> Iterator[list[str]]:
    buffer: list[str] = []
    for line in lines:
        if line.strip():
            buffer.append(line)
        elif buffer:
            yield buffer
            buffer = []
    if buffer:
        yield buffer


def parse_markdown(raw: str, source: Path | None = None) -> Document:
    meta, body = _parse_frontmatter(raw)
    blocks: list[Block] = []

    for group in _iter_groups(body.replace("\r\n", "\n").split("\n")):
        first = group[0].strip()

        if _RULE.match(first) and len(group) == 1:
            blocks.append(Block(kind="break"))
            continue

        image = _IMAGE_LINE.match(first)
        if image and len(group) == 1:
            blocks.append(
                Block(
                    kind="image",
                    src=image.group("src"),
                    alt=inline_to_markup(image.group("alt")),
                )
            )
            continue

        heading = _HEADING.match(first)
        if heading:
            blocks.append(
                Block(
                    kind="heading",
                    level=len(heading.group("level")),
                    text=inline_to_markup(heading.group("text")),
                )
            )
            rest = group[1:]
            if rest:
                blocks.extend(parse_markdown("\n".join(rest)).blocks)
            continue

        if _LIST_ITEM.match(first):
            items = []
            for line in group:
                item = _LIST_ITEM.match(line.strip())
                if item:
                    items.append(inline_to_markup(item.group("text")))
                elif items:
                    items[-1] += " " + inline_to_markup(line.strip())
            blocks.append(Block(kind="list", items=items))
            continue

        if first.startswith(">"):
            text = " ".join(line.strip().lstrip(">").strip() for line in group)
            blocks.append(Block(kind="quote", text=inline_to_markup(text)))
            continue

        blocks.append(
            Block(kind="paragraph", text=inline_to_markup(" ".join(l.strip() for l in group)))
        )

    return Document(meta=meta, blocks=blocks, source=source)


def parse_file(path: str | Path) -> Document:
    file_path = Path(path)
    return parse_markdown(file_path.read_text(encoding="utf-8"), source=file_path)
