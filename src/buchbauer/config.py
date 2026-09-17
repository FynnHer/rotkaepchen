"""Zentrale Konfiguration des Buchbauers.

Alle Layout-, Typografie- und Farbparameter werden aus einer einzigen
TOML-Datei (standardmaessig ``book.toml``) geladen. Kapitel-Dateien
enthalten damit ausschliesslich Inhalt, niemals Layout.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reportlab.lib import pagesizes
from reportlab.lib.units import mm

__all__ = [
    "BookConfig",
    "PageConfig",
    "TypographyConfig",
    "ImageConfig",
    "ColorConfig",
    "TocConfig",
    "PrintConfig",
    "CoverConfig",
    "ActivityPage",
    "ActivityConfig",
    "Palette",
    "ConfigError",
    "load_config",
]


class ConfigError(ValueError):
    """Die Konfigurationsdatei ist unvollstaendig oder widerspruechlich."""


PAGE_FORMATS: dict[str, tuple[float, float]] = {
    "A4": pagesizes.A4,
    "A5": pagesizes.A5,
    "A6": pagesizes.A6,
    "B5": pagesizes.B5,
    "LETTER": pagesizes.LETTER,
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Mischt ``override`` rekursiv in eine Kopie von ``base``."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass(frozen=True)
class Palette:
    """Eine Seitenpalette.

    Bewusst genau drei Farben: ``paper`` (Traegerflaeche), ``ink``
    (Text/Linien) und ``accent`` (Hervorhebungen). Mehr Rollen gibt es
    nicht, damit die Drei-Farben-Regel strukturell und nicht nur per
    Konvention eingehalten wird.
    """

    name: str
    paper: str
    ink: str
    accent: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.paper, self.ink, self.accent)

    def rgb_tuple(self) -> tuple[tuple[int, int, int], ...]:
        return tuple(hex_to_rgb(c) for c in self.as_tuple())


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ConfigError(f"Ungueltiger Farbwert: {value!r}")
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError as exc:  # pragma: no cover - defensiv
        raise ConfigError(f"Ungueltiger Farbwert: {value!r}") from exc


def normalize_hex(value: str) -> str:
    r, g, b = hex_to_rgb(value)
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass(frozen=True)
class PageConfig:
    format: str = "A5"
    width: float = pagesizes.A5[0]
    height: float = pagesizes.A5[1]
    margin_top: float = 18 * mm
    margin_bottom: float = 20 * mm
    margin_left: float = 18 * mm
    margin_right: float = 18 * mm
    bleed: float = 0.0

    @property
    def size(self) -> tuple[float, float]:
        """Endformat nach dem Beschnitt."""
        return (self.width, self.height)

    @property
    def media_size(self) -> tuple[float, float]:
        """Format der PDF-Seite inklusive Anschnitt."""
        return (self.width + 2 * self.bleed, self.height + 2 * self.bleed)

    @property
    def frame_width(self) -> float:
        return self.width - self.margin_left - self.margin_right

    @property
    def frame_height(self) -> float:
        return self.height - self.margin_top - self.margin_bottom


@dataclass(frozen=True)
class TypographyConfig:
    serif: str = "Times-Roman"
    serif_bold: str = "Times-Bold"
    serif_italic: str = "Times-Italic"
    sans: str = "Helvetica"
    font_files: dict[str, str] = field(default_factory=dict)
    body_size: float = 11.0
    leading_factor: float = 1.45
    chapter_title_size: float = 26.0
    chapter_number_size: float = 9.0
    quote_size: float = 11.0
    caption_size: float = 8.5
    running_head_size: float = 7.5
    folio_size: float = 8.5
    space_after_paragraph: float = 0.0
    first_line_indent: float = 5 * mm
    opening_initial: bool = True
    initial_scale: float = 2.0
    cover_title_size: float = 40.0
    cover_subtitle_size: float = 12.0

    @property
    def body_leading(self) -> float:
        return self.body_size * self.leading_factor


@dataclass(frozen=True)
class ImageConfig:
    width_ratio: float = 0.82
    max_height_ratio: float = 0.42
    opener_width_ratio: float = 1.0
    opener_max_height_ratio: float = 0.34
    tritone: bool = True
    dither: bool = True
    space_before: float = 6 * mm
    space_after: float = 4 * mm
    captions: bool = True
    auto_min_score: int = 3
    max_auto_illustrations: int = 1
    title_weight: int = 5


@dataclass(frozen=True)
class ColorConfig:
    max_per_page: int = 3
    max_total: int = 3
    paper_counts: bool = True
    default_palette: str = "default"
    palettes: dict[str, Palette] = field(default_factory=dict)
    rotate: list[str] = field(default_factory=list)

    def get(self, name: str | None) -> Palette:
        key = name or self.default_palette
        if key not in self.palettes:
            raise ConfigError(
                f"Unbekannte Palette {key!r}. Verfuegbar: {sorted(self.palettes)}"
            )
        return self.palettes[key]

    def for_chapter(self, index: int, explicit: str | None) -> Palette:
        """Palette eines Kapitels: explizit aus dem Frontmatter, sonst Rotation."""
        if explicit:
            return self.get(explicit)
        if self.rotate:
            return self.get(self.rotate[index % len(self.rotate)])
        return self.get(None)


@dataclass(frozen=True)
class PrintConfig:
    """Parameter der Druckvorstufe."""

    bleed: float = 0.0
    crop_marks: bool = False
    crop_mark_length: float = 4 * mm
    crop_mark_offset: float = 1.5 * mm
    crop_mark_width: float = 0.25
    min_image_dpi: float = 300.0
    color_space: str = "rgb"
    jpeg_quality: int = 95


@dataclass(frozen=True)
class CoverConfig:
    full_page_image: bool = True
    band_height_ratio: float = 0.34
    band_inset_mm: float = 0.0


@dataclass(frozen=True)
class ActivityPage:
    """Eine Mitmach-Seite (Raetsel) zwischen zwei Kapiteln.

    ``after`` ist die Nummer des Kapitels, hinter dem die Seite steht;
    ``0`` stellt sie vor das erste Kapitel.
    """

    image: str
    after: int
    title: str = ""


@dataclass(frozen=True)
class ActivityConfig:
    """Die Raetselseiten und ihr eigener Bildordner."""

    enabled: bool = True
    directory: Path | None = None
    tritone: bool = False
    in_toc: bool = True
    pages: tuple[ActivityPage, ...] = ()

    def after(self, chapter_number: int) -> list[ActivityPage]:
        """Alle Seiten, die hinter diesem Kapitel stehen."""
        if not self.enabled:
            return []
        return [page for page in self.pages if page.after == chapter_number]

    def beyond(self, last_chapter: int) -> list[ActivityPage]:
        """Seiten, deren Anker hinter dem letzten Kapitel liegt."""
        if not self.enabled:
            return []
        return [page for page in self.pages if page.after > last_chapter]


@dataclass(frozen=True)
class TocConfig:
    enabled: bool = True
    title: str = "Inhalt"


@dataclass(frozen=True)
class BookConfig:
    root: Path
    title: str
    subtitle: str
    author: str
    chapters_dir: Path
    assets_dir: Path
    output: Path
    cover_image: str | None
    cover_palette: str
    page: PageConfig
    typography: TypographyConfig
    images: ImageConfig
    colors: ColorConfig
    toc: TocConfig
    printing: PrintConfig
    cover: CoverConfig
    activities: ActivityConfig
    asset_aliases: dict[str, list[str]]
    asset_captions: dict[str, str]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


DEFAULTS: dict[str, Any] = {
    "book": {
        "title": "Unbenanntes Buch",
        "subtitle": "",
        "author": "",
        "chapters_dir": "chapters",
        "assets_dir": "assets/images",
        "output": "build/buch.pdf",
        "cover_image": None,
        "cover_palette": "default",
    },
    "page": {
        "format": "A5",
        "margin_top_mm": 18.0,
        "margin_bottom_mm": 20.0,
        "margin_left_mm": 18.0,
        "margin_right_mm": 18.0,
    },
    "typography": {
        "serif": "Times-Roman",
        "serif_bold": "Times-Bold",
        "serif_italic": "Times-Italic",
        "sans": "Helvetica",
        "body_size_pt": 11.0,
        "leading_factor": 1.45,
        "chapter_title_size_pt": 26.0,
        "chapter_number_size_pt": 9.0,
        "quote_size_pt": 11.0,
        "caption_size_pt": 8.5,
        "running_head_size_pt": 7.5,
        "folio_size_pt": 8.5,
        "space_after_paragraph_pt": 0.0,
        "first_line_indent_mm": 5.0,
        "opening_initial": True,
        "initial_scale": 2.0,
        "cover_title_size_pt": 40.0,
        "cover_subtitle_size_pt": 12.0,
        "font_files": {},
    },
    "images": {
        "width_ratio": 0.82,
        "max_height_ratio": 0.42,
        "opener_width_ratio": 1.0,
        "opener_max_height_ratio": 0.34,
        "tritone": True,
        "dither": True,
        "space_before_mm": 6.0,
        "space_after_mm": 4.0,
        "captions": True,
        "auto_min_score": 3,
        "title_weight": 5,
        "max_auto_illustrations": 1,
    },
    "colors": {
        "max_per_page": 3,
        "max_total": 3,
        "paper_counts": True,
        "default_palette": "default",
        "rotate": [],
        "palettes": {},
    },
    "toc": {"enabled": True, "title": "Inhalt"},
    "print": {
        "bleed_mm": 0.0,
        "crop_marks": False,
        "crop_mark_length_mm": 4.0,
        "crop_mark_offset_mm": 1.5,
        "crop_mark_width_pt": 0.25,
        "min_image_dpi": 300.0,
        "color_space": "rgb",
        "jpeg_quality": 95,
    },
    "cover": {
        "full_page_image": True,
        "band_height_ratio": 0.34,
        "band_inset_mm": 0.0,
    },
    "assets": {"aliases": {}, "captions": {}},
    "activities": {
        "enabled": True,
        "dir": "assets/raetsel",
        "tritone": False,
        "in_toc": True,
        "pages": [],
    },
}


def _page_size(spec: Any) -> tuple[float, float]:
    if isinstance(spec, str):
        try:
            return PAGE_FORMATS[spec.strip().upper()]
        except KeyError:
            raise ConfigError(
                f"Unbekanntes Seitenformat {spec!r}. "
                f"Erlaubt: {sorted(PAGE_FORMATS)} oder [breite_mm, hoehe_mm]"
            ) from None
    if isinstance(spec, (list, tuple)) and len(spec) == 2:
        return (float(spec[0]) * mm, float(spec[1]) * mm)
    raise ConfigError(f"Ungueltige Angabe fuer page.format: {spec!r}")


def _build_activities(raw: dict[str, Any], root: Path) -> ActivityConfig:
    """Liest ``[activities]`` samt der Liste ``[[activities.pages]]``."""
    pages: list[ActivityPage] = []
    for entry in raw.get("pages") or []:
        if not isinstance(entry, dict):
            raise ConfigError(
                "Jede Raetselseite ist eine Tabelle [[activities.pages]] "
                f"mit image/after, nicht {entry!r}."
            )
        image = str(entry.get("image", "")).strip()
        if not image:
            raise ConfigError("Einer Raetselseite fehlt der Schluessel 'image'.")
        after = entry.get("after")
        if not isinstance(after, int) or isinstance(after, bool) or after < 0:
            raise ConfigError(
                f"Raetselseite {image!r}: 'after' ist die Nummer des Kapitels, "
                f"hinter dem sie steht (0 = vor dem ersten Kapitel), nicht {after!r}."
            )
        pages.append(
            ActivityPage(image=image, after=after, title=str(entry.get("title", "")))
        )
    # Sortiert nach Anker, damit die Reihenfolge im Buch nicht von der
    # Reihenfolge in der Konfiguration abhaengt.
    pages.sort(key=lambda page: (page.after, page.image))
    return ActivityConfig(
        enabled=bool(raw.get("enabled", True)),
        directory=(root / str(raw.get("dir", "assets/raetsel"))).resolve(),
        tritone=bool(raw.get("tritone", False)),
        in_toc=bool(raw.get("in_toc", True)),
        pages=tuple(pages),
    )


def _build_palettes(raw: dict[str, Any]) -> dict[str, Palette]:
    palettes: dict[str, Palette] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"Palette {name!r} muss eine Tabelle sein.")
        missing = {"paper", "ink", "accent"} - set(spec)
        if missing:
            raise ConfigError(
                f"Palette {name!r} fehlen die Farben: {sorted(missing)}"
            )
        extra = set(spec) - {"paper", "ink", "accent"}
        if extra:
            raise ConfigError(
                f"Palette {name!r} hat unerlaubte Farbrollen {sorted(extra)}. "
                "Eine Palette besteht aus genau paper/ink/accent."
            )
        palettes[name] = Palette(
            name=name,
            paper=normalize_hex(spec["paper"]),
            ink=normalize_hex(spec["ink"]),
            accent=normalize_hex(spec["accent"]),
        )
    return palettes


def load_config(path: str | Path) -> BookConfig:
    """Laedt ``book.toml`` und fuellt fehlende Werte mit den Defaults."""
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {config_path}")
    with config_path.open("rb") as handle:
        user = tomllib.load(handle)

    data = _deep_merge(DEFAULTS, user)
    root = config_path.parent

    book = data["book"]
    printing_raw = data["print"]
    printing = PrintConfig(
        bleed=float(printing_raw["bleed_mm"]) * mm,
        crop_marks=bool(printing_raw["crop_marks"]),
        crop_mark_length=float(printing_raw["crop_mark_length_mm"]) * mm,
        crop_mark_offset=float(printing_raw["crop_mark_offset_mm"]) * mm,
        crop_mark_width=float(printing_raw["crop_mark_width_pt"]),
        min_image_dpi=float(printing_raw["min_image_dpi"]),
        color_space=str(printing_raw["color_space"]).lower(),
        jpeg_quality=int(printing_raw["jpeg_quality"]),
    )
    if printing.color_space not in ("rgb", "cmyk"):
        raise ConfigError(
            f"print.color_space muss 'rgb' oder 'cmyk' sein, nicht "
            f"{printing.color_space!r}."
        )
    if printing.crop_marks and printing.bleed <= 0:
        raise ConfigError(
            "Schnittmarken brauchen einen Anschnitt: print.bleed_mm muss > 0 sein."
        )

    page_raw = data["page"]
    width, height = _page_size(page_raw["format"])
    page = PageConfig(
        format=str(page_raw["format"]),
        width=width,
        height=height,
        margin_top=float(page_raw["margin_top_mm"]) * mm,
        margin_bottom=float(page_raw["margin_bottom_mm"]) * mm,
        margin_left=float(page_raw["margin_left_mm"]) * mm,
        margin_right=float(page_raw["margin_right_mm"]) * mm,
        bleed=printing.bleed,
    )
    if page.frame_width <= 0 or page.frame_height <= 0:
        raise ConfigError("Die Raender lassen keinen Satzspiegel uebrig.")

    t = data["typography"]
    typography = TypographyConfig(
        serif=t["serif"],
        serif_bold=t["serif_bold"],
        serif_italic=t["serif_italic"],
        sans=t["sans"],
        font_files={k: str(v) for k, v in (t.get("font_files") or {}).items()},
        body_size=float(t["body_size_pt"]),
        leading_factor=float(t["leading_factor"]),
        chapter_title_size=float(t["chapter_title_size_pt"]),
        chapter_number_size=float(t["chapter_number_size_pt"]),
        quote_size=float(t["quote_size_pt"]),
        caption_size=float(t["caption_size_pt"]),
        running_head_size=float(t["running_head_size_pt"]),
        folio_size=float(t["folio_size_pt"]),
        space_after_paragraph=float(t["space_after_paragraph_pt"]),
        first_line_indent=float(t["first_line_indent_mm"]) * mm,
        opening_initial=bool(t["opening_initial"]),
        initial_scale=float(t["initial_scale"]),
        cover_title_size=float(t["cover_title_size_pt"]),
        cover_subtitle_size=float(t["cover_subtitle_size_pt"]),
    )

    i = data["images"]
    images = ImageConfig(
        width_ratio=float(i["width_ratio"]),
        max_height_ratio=float(i["max_height_ratio"]),
        opener_width_ratio=float(i["opener_width_ratio"]),
        opener_max_height_ratio=float(i["opener_max_height_ratio"]),
        tritone=bool(i["tritone"]),
        dither=bool(i["dither"]),
        space_before=float(i["space_before_mm"]) * mm,
        space_after=float(i["space_after_mm"]) * mm,
        captions=bool(i["captions"]),
        auto_min_score=int(i["auto_min_score"]),
        title_weight=int(i["title_weight"]),
        max_auto_illustrations=int(i["max_auto_illustrations"]),
    )

    c = data["colors"]
    palettes = _build_palettes(c.get("palettes") or {})
    if not palettes:
        raise ConfigError(
            "Es ist keine Palette definiert. Mindestens [colors.palettes.default] "
            "mit paper/ink/accent wird benoetigt."
        )
    max_per_page = int(c["max_per_page"])
    paper_counts = bool(c["paper_counts"])
    allowed = 3 if paper_counts else 2
    if max_per_page < allowed:
        raise ConfigError(
            f"colors.max_per_page={max_per_page} ist kleiner als die "
            f"{allowed} Farben, die eine Palette mindestens braucht."
        )
    total = {c for palette in palettes.values() for c in palette.as_tuple()}
    max_total = int(c["max_total"])
    if max_total > 0 and len(total) > max_total:
        raise ConfigError(
            f"Das Buch verwendet {len(total)} verschiedene Farben "
            f"({sorted(total)}), erlaubt sind colors.max_total={max_total}. "
            "Mehrere Paletten muessen sich dieselben Farben teilen."
        )

    colors = ColorConfig(
        max_per_page=max_per_page,
        max_total=max_total,
        paper_counts=paper_counts,
        default_palette=str(c["default_palette"]),
        palettes=palettes,
        rotate=[str(x) for x in (c.get("rotate") or [])],
    )
    colors.get(colors.default_palette)  # frueh scheitern bei Tippfehlern
    for name in colors.rotate:
        colors.get(name)

    aliases = {
        str(key): [str(word) for word in words]
        for key, words in (data["assets"].get("aliases") or {}).items()
    }

    captions = {
        str(key): str(text)
        for key, text in (data["assets"].get("captions") or {}).items()
    }

    cover_palette = str(book["cover_palette"])
    colors.get(cover_palette)

    activities = _build_activities(data["activities"], root)

    return BookConfig(
        root=root,
        title=str(book["title"]),
        subtitle=str(book["subtitle"]),
        author=str(book["author"]),
        chapters_dir=(root / str(book["chapters_dir"])).resolve(),
        assets_dir=(root / str(book["assets_dir"])).resolve(),
        output=(root / str(book["output"])).resolve(),
        cover_image=book["cover_image"],
        cover_palette=cover_palette,
        page=page,
        typography=typography,
        images=images,
        colors=colors,
        toc=TocConfig(
            enabled=bool(data["toc"]["enabled"]), title=str(data["toc"]["title"])
        ),
        printing=printing,
        cover=CoverConfig(
            full_page_image=bool(data["cover"]["full_page_image"]),
            band_height_ratio=float(data["cover"]["band_height_ratio"]),
            band_inset_mm=float(data["cover"]["band_inset_mm"]) * mm,
        ),
        activities=activities,
        asset_aliases=aliases,
        asset_captions=captions,
        raw=data,
    )
