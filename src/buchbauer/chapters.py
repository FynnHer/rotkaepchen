"""Einlesen der Kapitel-Dateien und Verteilen der Illustrationen."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .assets import AssetLibrary, ChapterAssets, slugify
from .config import BookConfig, Palette
from .markdown import Block, Document, parse_file

__all__ = ["Chapter", "load_chapters", "place_images"]


@dataclass
class Chapter:
    number: int
    title: str
    subtitle: str
    slug: str
    source: Path
    document: Document
    palette: Palette
    assets: ChapterAssets = field(default_factory=ChapterAssets)
    body: list[Block] = field(default_factory=list)

    @property
    def running_head(self) -> str:
        return self.title


def _title_of(document: Document, source: Path) -> str:
    meta = document.meta
    for key in ("title", "titel"):
        if meta.get(key):
            return str(meta[key])
    for block in document.blocks:
        if block.kind == "heading" and block.level == 1:
            return block.text
    stem = source.stem
    parts = stem.split("-", 1)
    if len(parts) == 2 and parts[0].isdigit():
        stem = parts[1]
    return stem.replace("-", " ").replace("_", " ").strip().capitalize()


def _sort_key(item: tuple[Path, Document]) -> tuple:
    path, document = item
    order = document.meta.get("order", document.meta.get("nummer"))
    if isinstance(order, int):
        return (0, order, path.name)
    return (1, 0, path.name)


def place_images(blocks: list[Block], assets: ChapterAssets) -> list[Block]:
    """Verteilt die Kapitel-Illustrationen gleichmaessig ueber den Text.

    Bilder, die bereits explizit im Markdown stehen, bleiben an ihrem
    Platz; automatisch zugeordnete Illustrationen werden bevorzugt auf
    Szenentrenner gesetzt und sonst gleichmaessig zwischen die Absaetze
    verteilt.
    """
    pending = [m for m in assets.inline if m.source != "markdown"]
    if not pending:
        return list(blocks)

    result = list(blocks)
    breaks = [i for i, b in enumerate(result) if b.kind == "break"]
    for index in breaks:
        if not pending:
            break
        match = pending.pop(0)
        result[index] = Block(
            kind="image", src=match.asset.key, alt=match.caption
        )

    if not pending:
        return result

    paragraphs = [i for i, b in enumerate(result) if b.kind == "paragraph"]
    if len(paragraphs) < 2:
        return result + [
            Block(kind="image", src=m.asset.key, alt=m.caption) for m in pending
        ]

    slots = len(pending) + 1
    positions = sorted(
        {paragraphs[min(len(paragraphs) - 1, round(len(paragraphs) * n / slots))]
         for n in range(1, slots)}
    )
    for offset, (position, match) in enumerate(zip(positions, pending)):
        result.insert(
            position + 1 + offset,
            Block(kind="image", src=match.asset.key, alt=match.caption),
        )
    return result


def load_chapters(config: BookConfig, library: AssetLibrary | None = None) -> list[Chapter]:
    """Liest alle Markdown-Dateien des Kapitel-Ordners in Lese-Reihenfolge."""
    directory = config.chapters_dir
    if not directory.is_dir():
        raise FileNotFoundError(f"Kapitel-Ordner nicht gefunden: {directory}")

    files = sorted(p for p in directory.glob("*.md") if p.is_file())
    if not files:
        raise FileNotFoundError(f"Keine .md-Dateien in {directory}")

    library = library or AssetLibrary(
            config.assets_dir, config.asset_aliases, config.asset_captions
        )
    parsed = sorted(((p, parse_file(p)) for p in files), key=_sort_key)

    chapters: list[Chapter] = []
    used_assets: set[str] = set()
    for index, (path, document) in enumerate(parsed):
        title = _title_of(document, path)
        body = [b for b in document.blocks if not (b.kind == "heading" and b.level == 1)]
        explicit = [b.src for b in body if b.kind == "image"]

        matched = library.match_chapter(
            text=document.plain_text,
            meta=document.meta,
            title=title,
            title_weight=config.images.title_weight,
            explicit_refs=explicit,
            used=used_assets,
            min_score=config.images.auto_min_score,
            max_auto_inline=config.images.max_auto_illustrations,
        )
        used_assets.update(m.asset.key for m in matched.all)

        chapter = Chapter(
            number=index + 1,
            title=title,
            subtitle=str(document.meta.get("subtitle", document.meta.get("untertitel", ""))),
            slug=slugify(title),
            source=path,
            document=document,
            palette=config.colors.for_chapter(index, document.meta.get("palette")),
            assets=matched,
            body=place_images(body, matched),
        )
        chapters.append(chapter)
    return chapters
