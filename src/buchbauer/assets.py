"""Automatische Zuordnung von Bild-Assets zu Kapiteln.

Die Zuordnung laeuft in drei Stufen, von der staerksten zur schwaechsten
Quelle. Eine spaetere Stufe kann eine fruehere nie ueberstimmen:

1. **Explizit im Frontmatter** - ``hero:`` und ``images: [...]``
2. **Explizit im Markdown** - ``![Bildunterschrift](wolf)``
3. **Automatisch ueber Stichworte** - die in ``[assets.aliases]``
   hinterlegten Begriffe werden im Kapiteltext gezaehlt; das Asset mit
   den meisten Treffern wird zum Kapitelbild, weitere Treffer werden als
   Illustrationen zwischen die Absaetze verteilt.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Asset", "AssetLibrary", "AssetMatch", "AssetError"]

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff", ".bmp", ".webp")

_UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


class AssetError(ValueError):
    """Ein referenziertes Bild existiert nicht."""


def slugify(value: str) -> str:
    """``"Großmutters Hütte"`` -> ``"grossmutters-huette"``."""
    text = value.strip().lower()
    for src, dst in _UMLAUTS.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


@dataclass(frozen=True)
class Asset:
    key: str
    path: Path
    aliases: tuple[str, ...] = ()
    caption: str = ""


@dataclass
class AssetMatch:
    """Ein Asset im Kontext eines Kapitels."""

    asset: Asset
    caption: str = ""
    score: int = 0
    source: str = "auto"  # frontmatter | markdown | auto


@dataclass
class ChapterAssets:
    hero: AssetMatch | None = None
    inline: list[AssetMatch] = field(default_factory=list)

    @property
    def all(self) -> list[AssetMatch]:
        return ([self.hero] if self.hero else []) + self.inline


class AssetLibrary:
    """Index ueber den Asset-Ordner inklusive Stichwort-Zuordnung."""

    def __init__(
        self,
        directory: Path,
        aliases: dict[str, list[str]] | None = None,
        captions: dict[str, str] | None = None,
    ):
        self.directory = Path(directory)
        self._aliases = aliases or {}
        self._captions = captions or {}
        self.assets: dict[str, Asset] = {}
        self._scan()

    def _scan(self) -> None:
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.iterdir()):
            if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
                continue
            key = slugify(path.stem)
            # Ein fuehrender Ordnungspraefix wie "02-" gehoert nicht zum Schluessel.
            key = re.sub(r"\A\d+[-_]", "", key)
            if key in self.assets:
                continue
            # Aliase werden als Slug abgelegt und dabei entdoppelt: sonst
            # zaehlen "wolf" und "Wolf" denselben Treffer zweimal.
            words = [key.replace("-", " ")] + list(self._aliases.get(key, []))
            slugs = dict.fromkeys(s for s in (slugify(w) for w in words) if s)
            self.assets[key] = Asset(
                key=key,
                path=path,
                aliases=tuple(slugs),
                caption=self._captions.get(key, ""),
            )

    def __len__(self) -> int:
        return len(self.assets)

    def __contains__(self, key: str) -> bool:
        return slugify(key) in self.assets

    def resolve(self, reference: str) -> Asset:
        """Loest einen Asset-Schluessel *oder* einen Dateipfad auf."""
        key = slugify(Path(reference).stem if "/" in reference or "." in reference else reference)
        if key in self.assets:
            return self.assets[key]
        candidate = (self.directory / reference).resolve()
        if candidate.is_file():
            return Asset(key=key or candidate.stem, path=candidate)
        raise AssetError(
            f"Bild {reference!r} nicht gefunden. "
            f"Bekannte Assets: {sorted(self.assets) or '(keine)'}"
        )

    def _count_mentions(self, text: str) -> dict[str, int]:
        haystack = slugify(text).replace("-", " ")
        scores: dict[str, int] = {}
        for key, asset in self.assets.items():
            total = 0
            for alias in asset.aliases:
                needle = alias.replace("-", " ")
                total += len(
                    re.findall(rf"(?<![a-z0-9]){re.escape(needle)}", haystack)
                )
            if total:
                scores[key] = total
        return scores

    def match_chapter(
        self,
        text: str,
        meta: dict,
        title: str = "",
        title_weight: int = 5,
        explicit_refs: list[str] | None = None,
        used: set[str] | None = None,
        min_score: int = 1,
        max_auto_inline: int | None = None,
    ) -> ChapterAssets:
        """Bestimmt Kapitelbild und Illustrationen fuer ein Kapitel."""
        used = used or set()
        explicit_refs = explicit_refs or []
        result = ChapterAssets()
        taken: set[str] = set()

        def take(asset: Asset, source: str, score: int = 0) -> AssetMatch | None:
            if asset.key in taken:
                return None
            taken.add(asset.key)
            return AssetMatch(asset=asset, score=score, source=source)

        hero_ref = meta.get("hero") or meta.get("kapitelbild")
        if hero_ref:
            result.hero = take(self.resolve(str(hero_ref)), "frontmatter")

        for ref in meta.get("images", []) or meta.get("bilder", []) or []:
            match = take(self.resolve(str(ref)), "frontmatter")
            if match:
                result.inline.append(match)

        for ref in explicit_refs:
            match = take(self.resolve(ref), "markdown")
            if match:
                result.inline.append(match)

        # Der Kapiteltitel benennt das Thema des Kapitels - ein Treffer dort
        # wiegt schwerer als eine beilaeufige Erwaehnung im Fliesstext.
        scores = self._count_mentions(text)
        for key, count in self._count_mentions(title).items():
            scores[key] = scores.get(key, 0) + count * title_weight

        def rank(key: str) -> tuple:
            # Ein im Buch schon verwendetes Asset wird abgewertet, damit
            # sich die Bildfolge ueber die Kapitel hinweg abwechselt.
            weight = 0.55 if key in used else 1.0
            return (-scores[key] * weight, key)

        ranked = sorted((k for k in scores if k not in taken), key=rank)
        # Das Kapitelbild darf den Schwellwert unterschreiten, die
        # zusaetzlichen Illustrationen nicht - sonst wird das Buch bunt
        # von Randnotizen illustriert.
        if result.hero is None and ranked:
            best = ranked.pop(0)
            result.hero = take(self.assets[best], "auto", scores[best])
        budget = len(ranked) if max_auto_inline is None else max_auto_inline
        for key in ranked:
            if budget <= 0 or scores[key] < min_score:
                break
            match = take(self.assets[key], "auto", scores[key])
            if match:
                result.inline.append(match)
                budget -= 1

        # Ohne gepflegte Bildunterschrift bleibt die Illustration
        # unbeschriftet - ein Dateiname unter dem Bild ist keine.
        for match in result.all:
            if not match.caption:
                match.caption = match.asset.caption
        return result
