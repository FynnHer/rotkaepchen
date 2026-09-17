"""Der eigentliche PDF-Bau.

Pro Palette gibt es zwei Seitenvorlagen (Kapitelaufschlag und Fliesstext)
plus eine Titelseite. Dadurch ist die Palette einer Seite bereits durch
die Vorlage festgelegt und muss nicht zur Zeichenzeit erraten werden.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from reportlab.platypus.tables import TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

from .assets import AssetLibrary
from .chapters import Chapter, load_about, load_chapters
from .colors import ColorRecorder, hex_color as _hex_color, make_canvasmaker
from .config import ActivityPage, BookConfig, Palette
from .images import fit_size, prepare_image
from .markdown import Block

__all__ = ["BookBuilder", "BuildResult", "build_book"]

ORDINALS = [
    "Erstes", "Zweites", "Drittes", "Viertes", "Fünftes", "Sechstes",
    "Siebtes", "Achtes", "Neuntes", "Zehntes", "Elftes", "Zwölftes",
]


def chapter_label(number: int) -> str:
    """Die Zeile ueber dem Kapiteltitel. Seiten ohne Nummer bekommen keine."""
    if number < 1:
        return ""
    if number <= len(ORDINALS):
        return f"{ORDINALS[number - 1]} Kapitel"
    return f"Kapitel {number}"


@dataclass
class BuildResult:
    output: Path
    pages: int
    chapters: list[Chapter]
    recorder: ColorRecorder
    warnings: list[str] = field(default_factory=list)

    @property
    def violations(self):
        return self.recorder.violations()


class ChapterTitle(Paragraph):
    """Paragraph, den das Dokument fuer das Inhaltsverzeichnis erkennt."""

    def __init__(self, text: str, style, chapter: Chapter):
        super().__init__(text, style)
        self.chapter = chapter


class Ornament(Flowable):
    """Dezenter Szenentrenner aus drei Rauten in der Akzentfarbe."""

    def __init__(self, width: float, color, size: float = 3.0, gap: float = 9.0):
        super().__init__()
        self.width = width
        self.color = color
        self.size = size
        self.gap = gap
        self.height = size * 4

    def draw(self):
        canv = self.canv
        canv.setFillColor(self.color)
        middle = self.width / 2
        y = self.height / 2
        for offset in (-self.gap, 0.0, self.gap):
            canv.saveState()
            canv.translate(middle + offset, y)
            canv.rotate(45)
            canv.rect(-self.size / 2, -self.size / 2, self.size, self.size, stroke=0, fill=1)
            canv.restoreState()


class WideImage(Flowable):
    """Bild, das breiter sein darf als der Satzspiegel.

    Der Flowable meldet dem Rahmen nur dessen eigene Breite und zeichnet
    darueber hinaus mittig in die Raender hinein. So wirken Illustrationen
    praesent, ohne dass der Rahmen den Umbruch verwirft.
    """

    def __init__(self, path: str, width: float, height: float):
        super().__init__()
        self.path = path
        self.image_width = width
        self.image_height = height
        self.width = width
        self.height = height

    def wrap(self, available_width: float, available_height: float):
        self.width = available_width
        return (available_width, self.image_height)

    def draw(self):
        x = (self.width - self.image_width) / 2.0
        self.canv.drawImage(
            self.path, x, 0, self.image_width, self.image_height, mask=None
        )


class ActivityImage(Flowable):
    """Eine Raetselseite: ein Bild randabfallend ueber die ganze Seite.

    Die Seite bringt Titel und Aufgabenstellung selbst mit, deshalb setzt
    das Buch nichts darueber. Gezeichnet wird ab dem Ursprung der
    PDF-Seite, nicht ab dem Satzspiegel - der Rahmen dient nur dazu, dem
    Umbruch eine volle Seite abzuverlangen.
    """

    def __init__(self, path: str, media_size: tuple[float, float],
                 origin: tuple[float, float], title: str = "", key: str = ""):
        super().__init__()
        self.path = path
        self.media_width, self.media_height = media_size
        self.origin_x, self.origin_y = origin
        self.title = title
        self.key = key
        self.width = 0.0
        self.height = 0.0

    def wrap(self, available_width: float, available_height: float):
        self.width = available_width
        self.height = available_height
        return (available_width, available_height)

    def draw(self):
        canv = self.canv
        canv.saveState()
        canv.translate(-self.origin_x, -self.origin_y)
        path = canv.beginPath()
        path.rect(0, 0, self.media_width, self.media_height)
        canv.clipPath(path, stroke=0, fill=0)
        canv.drawImage(
            self.path, *self._placement(), mask=None
        )
        canv.restoreState()

    def _placement(self) -> tuple[float, float, float, float]:
        """Formatfuellend zentriert - der Ueberstand laeuft in den Anschnitt."""
        image = ImageReader(self.path)
        source_width, source_height = image.getSize()
        scale = max(
            self.media_width / source_width, self.media_height / source_height
        )
        width = source_width * scale
        height = source_height * scale
        return (
            (self.media_width - width) / 2.0,
            (self.media_height - height) / 2.0,
            width,
            height,
        )


class Rule(Flowable):
    """Eine haarfeine Linie in einer Palettenfarbe."""

    def __init__(self, width: float, color, thickness: float = 0.6):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness
        self.height = thickness

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


class BookDocTemplate(BaseDocTemplate):
    """Dokument mit Inhaltsverzeichnis-Rueckmeldung."""

    def __init__(self, *args, recorder: ColorRecorder, **kwargs):
        super().__init__(*args, **kwargs)
        self.recorder = recorder

    def beforeDocument(self):
        # multiBuild laeuft mehrfach; das Farbprotokoll gilt nur fuer den
        # letzten, tatsaechlich geschriebenen Durchlauf.
        self.recorder.reset()

    def afterFlowable(self, flowable):
        if isinstance(flowable, ChapterTitle):
            key = flowable.chapter.slug
            # Sprungziel fuer Inhaltsverzeichnis und PDF-Lesezeichen.
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.chapter.title, key, level=0)
            self.notify("TOCEntry", (0, flowable.chapter.title, self.page, key))
        elif isinstance(flowable, ActivityImage) and flowable.title:
            self.canv.bookmarkPage(flowable.key)
            self.canv.addOutlineEntry(flowable.title, flowable.key, level=0)
            self.notify("TOCEntry", (0, flowable.title, self.page, flowable.key))


class BookBuilder:
    def __init__(self, config: BookConfig, library: AssetLibrary | None = None):
        self.config = config
        self.library = library or AssetLibrary(
            config.assets_dir, config.asset_aliases, config.asset_captions
        )
        # Die Raetselseiten liegen in einem eigenen Ordner und nehmen an der
        # Stichwort-Zuordnung der Kapitel bewusst nicht teil.
        self.activities = AssetLibrary(
            config.activities.directory or config.assets_dir
        )
        self.recorder = ColorRecorder(max_per_page=config.colors.max_per_page)
        self.cache_dir = config.output.parent / ".cache"
        self._fonts = self._register_fonts()
        self._styles: dict[str, dict[str, ParagraphStyle]] = {}
        self.warnings: list[str] = []

    def color(self, value: str) -> object:
        """Palettenfarbe im konfigurierten Ausgabefarbraum."""
        return _hex_color(value, self.config.printing.color_space)

    def _check_dpi(self, key: str, prepared, width_pt: float, height_pt: float) -> None:
        """Meldet Bilder, deren Aufloesung fuer den Druck nicht reicht."""
        limit = self.config.printing.min_image_dpi
        if limit <= 0 or width_pt <= 0 or height_pt <= 0:
            return
        dpi = min(prepared.width / (width_pt / 72.0), prepared.height / (height_pt / 72.0))
        if dpi < limit:
            message = (
                f"Bild '{key}' liegt bei {dpi:.0f} dpi, "
                f"gefordert sind {limit:.0f} dpi."
            )
            if message not in self.warnings:
                self.warnings.append(message)

    # ------------------------------------------------------------------ Fonts
    def _register_fonts(self) -> dict[str, str]:
        t = self.config.typography
        names = {
            "regular": t.serif,
            "bold": t.serif_bold,
            "italic": t.serif_italic,
            "sans": t.sans,
        }
        files = t.font_files
        if not files:
            return names

        family = "BookSerif"
        mapping = {
            "regular": (family, files.get("regular")),
            "bold": (f"{family}-Bold", files.get("bold")),
            "italic": (f"{family}-Italic", files.get("italic")),
            "bolditalic": (f"{family}-BoldItalic", files.get("bolditalic")),
        }
        registered: dict[str, str] = {}
        for role, (font_name, file_name) in mapping.items():
            if not file_name:
                continue
            path = Path(file_name)
            if not path.is_absolute():
                path = (self.config.root / path).resolve()
            if not path.is_file():
                continue
            pdfmetrics.registerFont(TTFont(font_name, str(path)))
            registered[role] = font_name

        if "regular" not in registered:
            return names  # keine brauchbare Datei gefunden - Base-14 behalten

        pdfmetrics.registerFontFamily(
            family,
            normal=registered["regular"],
            bold=registered.get("bold", registered["regular"]),
            italic=registered.get("italic", registered["regular"]),
            boldItalic=registered.get("bolditalic", registered["regular"]),
        )
        names["regular"] = registered["regular"]
        names["bold"] = registered.get("bold", registered["regular"])
        names["italic"] = registered.get("italic", registered["regular"])
        return names

    # ----------------------------------------------------------------- Styles
    def styles(self, palette: Palette) -> dict[str, ParagraphStyle]:
        if palette.name in self._styles:
            return self._styles[palette.name]

        t = self.config.typography
        ink, accent = palette.ink, palette.accent
        body = ParagraphStyle(
            f"body-{palette.name}",
            fontName=self._fonts["regular"],
            fontSize=t.body_size,
            leading=t.body_leading,
            textColor=self.color(ink),
            alignment=TA_JUSTIFY,
            firstLineIndent=t.first_line_indent,
            spaceAfter=t.space_after_paragraph,
            hyphenationLang="de_DE",
            embeddedHyphenation=1,
        )
        result = {
            "body": body,
            # ReportLab setzt die erste Grundlinie eines Absatzes nach der
            # groessten Schrift in Zeile 1, rechnet die Absatzhoehe aber mit
            # der normalen Zeilenhoehe. Die Versalie schiebt den Absatz
            # deshalb um genau diese Differenz nach unten - der Ausgleich
            # kommt als spaceAfter zurueck, sonst laeuft der Folgeabsatz in
            # die letzte Zeile hinein.
            "body_first": ParagraphStyle(
                f"body-first-{palette.name}",
                parent=body,
                firstLineIndent=0,
                spaceAfter=self._initial_overshoot(),
            ),
            "quote": ParagraphStyle(
                f"quote-{palette.name}",
                parent=body,
                fontName=self._fonts["italic"],
                fontSize=t.quote_size,
                leading=t.quote_size * t.leading_factor,
                leftIndent=8 * 1.6,
                rightIndent=8 * 1.6,
                firstLineIndent=0,
                alignment=TA_LEFT,
                textColor=self.color(accent),
                spaceBefore=t.body_size * 0.6,
                spaceAfter=t.body_size * 0.6,
            ),
            "list": ParagraphStyle(
                f"list-{palette.name}",
                parent=body,
                firstLineIndent=0,
                leftIndent=12,
                bulletIndent=2,
                alignment=TA_LEFT,
                bulletFontName=self._fonts["regular"],
            ),
            "subheading": ParagraphStyle(
                f"sub-{palette.name}",
                parent=body,
                fontName=self._fonts["bold"],
                fontSize=t.body_size * 1.1,
                leading=t.body_size * 1.4,
                firstLineIndent=0,
                alignment=TA_LEFT,
                textColor=self.color(accent),
                spaceBefore=t.body_size,
                spaceAfter=t.body_size * 0.3,
            ),
            "chapter_number": ParagraphStyle(
                f"chapnum-{palette.name}",
                fontName=self._fonts["regular"],
                fontSize=t.chapter_number_size,
                leading=t.chapter_number_size * 1.6,
                textColor=self.color(accent),
                alignment=TA_CENTER,
            ),
            "chapter_title": ParagraphStyle(
                f"chaptitle-{palette.name}",
                fontName=self._fonts["bold"],
                fontSize=t.chapter_title_size,
                leading=t.chapter_title_size * 1.12,
                textColor=self.color(ink),
                alignment=TA_CENTER,
                spaceBefore=4,
                spaceAfter=6,
            ),
            "chapter_subtitle": ParagraphStyle(
                f"chapsub-{palette.name}",
                fontName=self._fonts["italic"],
                fontSize=t.body_size,
                leading=t.body_size * 1.4,
                textColor=self.color(accent),
                alignment=TA_CENTER,
            ),
            "caption": ParagraphStyle(
                f"caption-{palette.name}",
                fontName=self._fonts["italic"],
                fontSize=t.caption_size,
                leading=t.caption_size * 1.35,
                textColor=self.color(accent),
                alignment=TA_CENTER,
                spaceBefore=3,
            ),
            "cover_title": ParagraphStyle(
                f"covertitle-{palette.name}",
                fontName=self._fonts["bold"],
                fontSize=t.cover_title_size,
                leading=t.cover_title_size * 1.08,
                textColor=self.color(ink),
                alignment=TA_CENTER,
            ),
            "cover_subtitle": ParagraphStyle(
                f"coversub-{palette.name}",
                fontName=self._fonts["italic"],
                fontSize=t.cover_subtitle_size,
                leading=t.cover_subtitle_size * 1.5,
                textColor=self.color(accent),
                alignment=TA_CENTER,
            ),
            "toc_entry": ParagraphStyle(
                f"toc-{palette.name}",
                fontName=self._fonts["regular"],
                fontSize=t.body_size,
                leading=t.body_size * 1.9,
                textColor=self.color(ink),
                firstLineIndent=0,
            ),
        }
        self._styles[palette.name] = result
        return result

    # ---------------------------------------------------------- Seitenvorlagen
    def _crop_marks(self, canvas) -> None:
        """Schnittmarken an den vier Ecken des Endformats."""
        printing = self.config.printing
        if not printing.crop_marks:
            return
        page = self.config.page
        bleed = page.bleed
        length = min(printing.crop_mark_length, max(bleed - printing.crop_mark_offset, 0))
        if length <= 0:
            return
        gap = printing.crop_mark_offset
        palette = self.config.colors.get(None)

        canvas.saveState()
        canvas.setStrokeColor(self.color(palette.ink))
        canvas.setLineWidth(printing.crop_mark_width)
        for x in (bleed, bleed + page.width):
            for y in (bleed, bleed + page.height):
                dx = -1 if x == bleed else 1
                dy = -1 if y == bleed else 1
                canvas.line(x + dx * gap, y, x + dx * (gap + length), y)
                canvas.line(x, y + dy * gap, x, y + dy * (gap + length))
        canvas.restoreState()

    def _draw_full_bleed_image(self, canvas, reference: str, palette: Palette) -> None:
        """Zeichnet ein Bild formatfuellend ueber die ganze Seite inkl. Anschnitt."""
        asset = self.library.resolve(reference)
        cover_tritone = self.config.cover.tritone
        prepared = prepare_image(
            asset.path,
            palette,
            self.cache_dir,
            tritone=(
                self.config.images.tritone if cover_tritone is None else cover_tritone
            ),
            dither=self.config.images.dither,
            color_space=self.config.printing.color_space,
            jpeg_quality=self.config.printing.jpeg_quality,
        )
        media_width, media_height = self.config.page.media_size
        # Formatfuellend: die groessere der beiden Skalierungen gewinnt,
        # der Ueberstand wird beschnitten.
        scale = max(media_width / prepared.width, media_height / prepared.height)
        width = prepared.width * scale
        height = prepared.height * scale
        canvas.saveState()
        path = canvas.beginPath()
        path.rect(0, 0, media_width, media_height)
        canvas.clipPath(path, stroke=0, fill=0)
        canvas.drawImage(
            str(prepared.path),
            (media_width - width) / 2.0,
            (media_height - height) / 2.0,
            width,
            height,
            mask=None,
        )
        canvas.restoreState()
        self._check_dpi(asset.key, prepared, media_width, media_height)

    def _page_furniture(self, palette: Palette, template_id: str, running_head: bool):
        page = self.config.page
        t = self.config.typography
        recorder = self.recorder
        bleed = page.bleed
        media_width, media_height = page.media_size

        def draw(canvas, doc):
            recorder.bind_page(canvas.getPageNumber(), palette.name)
            canvas.saveState()
            # Der Papierton laeuft bis in den Anschnitt, sonst blitzt nach
            # dem Beschnitt ein weisser Rand auf.
            canvas.setFillColor(self.color(palette.paper))
            canvas.rect(0, 0, media_width, media_height, stroke=0, fill=1)

            if template_id == "activity":
                # Die Raetselseite traegt Titel und Aufgabe im Bild; eine
                # Seitenzahl darueber waere nur eine Stoerung.
                canvas.restoreState()
                self._crop_marks(canvas)
                return

            if template_id == "cover":
                cover = self.config.cover
                if cover.full_page_image and self.config.cover_image:
                    self._draw_full_bleed_image(canvas, str(self.config.cover_image), palette)
                if cover.full_page_image and cover.typeset_band:
                    band_height = bleed + page.height * cover.band_height_ratio
                    canvas.setFillColor(self.color(palette.paper))
                    canvas.rect(0, 0, media_width, band_height, stroke=0, fill=1)
                    canvas.setStrokeColor(self.color(palette.accent))
                    canvas.setLineWidth(1.0)
                    canvas.line(0, band_height, media_width, band_height)
                canvas.restoreState()
                self._crop_marks(canvas)
                return

            canvas.translate(bleed, bleed)
            if running_head:
                head = getattr(doc, "running_head", "") or ""
                canvas.setFont(self._fonts["italic"], t.running_head_size)
                canvas.setFillColor(self.color(palette.accent))
                canvas.drawCentredString(
                    page.width / 2,
                    page.height - page.margin_top + t.running_head_size * 1.4,
                    head,
                )
                canvas.setStrokeColor(self.color(palette.accent))
                canvas.setLineWidth(0.4)
                y = page.height - page.margin_top + t.running_head_size * 0.6
                canvas.line(page.margin_left, y, page.width - page.margin_right, y)

            canvas.setFont(self._fonts["regular"], t.folio_size)
            canvas.setFillColor(self.color(palette.ink))
            canvas.drawCentredString(
                page.width / 2,
                page.margin_bottom - t.folio_size * 2.0,
                str(canvas.getPageNumber()),
            )
            canvas.restoreState()
            self._crop_marks(canvas)

        return draw

    def _templates(self) -> list[PageTemplate]:
        page = self.config.page
        bleed = page.bleed
        cover_palette = self.config.colors.get(self.config.cover_palette)

        def frame(name: str, inset: float = 0.0) -> Frame:
            return Frame(
                bleed + page.margin_left + inset,
                bleed + page.margin_bottom + inset,
                page.frame_width - 2 * inset,
                page.frame_height - 2 * inset,
                leftPadding=0,
                rightPadding=0,
                topPadding=0,
                bottomPadding=0,
                id=name,
            )

        # Auf dem Umschlag steht der Text im Titelfeld am unteren Rand.
        cover = self.config.cover
        band_height = page.height * cover.band_height_ratio
        cover_frame = Frame(
            bleed + page.margin_left,
            bleed + cover.band_inset_mm,
            page.frame_width,
            max(band_height - cover.band_inset_mm - page.margin_bottom * 0.5, 10),
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="cover",
        )

        templates = [
            PageTemplate(
                id="cover",
                frames=[cover_frame],
                onPage=self._page_furniture(cover_palette, "cover", running_head=False),
            )
        ]
        for palette in self.config.colors.palettes.values():
            templates.append(
                PageTemplate(
                    id=f"{palette.name}-opener",
                    frames=[frame(f"{palette.name}-opener")],
                    onPage=self._page_furniture(palette, "opener", running_head=False),
                )
            )
            templates.append(
                PageTemplate(
                    id=f"{palette.name}-activity",
                    frames=[frame(f"{palette.name}-activity")],
                    onPage=self._page_furniture(palette, "activity", running_head=False),
                )
            )
            templates.append(
                PageTemplate(
                    id=f"{palette.name}-body",
                    frames=[frame(f"{palette.name}-body")],
                    onPage=self._page_furniture(palette, "body", running_head=True),
                )
            )
        return templates

    # -------------------------------------------------------------- Flowables
    def _image_flowable(
        self,
        reference: str,
        caption: str,
        palette: Palette,
        opener: bool = False,
        height_ratio: float | None = None,
    ) -> list:
        asset = self.library.resolve(reference)
        prepared = prepare_image(
            asset.path,
            palette,
            self.cache_dir,
            tritone=self.config.images.tritone,
            dither=self.config.images.dither,
            color_space=self.config.printing.color_space,
            jpeg_quality=self.config.printing.jpeg_quality,
        )
        cfg = self.config.images
        page = self.config.page
        width_ratio = cfg.opener_width_ratio if opener else cfg.width_ratio
        if height_ratio is None:
            height_ratio = (
                cfg.opener_max_height_ratio if opener else cfg.max_height_ratio
            )
        width, height = fit_size(
            prepared,
            page.frame_width * width_ratio,
            page.frame_height * height_ratio,
        )
        self._check_dpi(asset.key, prepared, width, height)
        image = WideImage(str(prepared.path), width, height)

        parts: list = [Spacer(1, cfg.space_before), image]
        if cfg.captions and caption:
            parts.append(Paragraph(caption, self.styles(palette)["caption"]))
        parts.append(Spacer(1, cfg.space_after))
        return [KeepTogether(parts)]

    def _activity_flowables(self, page: ActivityPage, palette: Palette) -> list:
        """Eine Raetselseite als eigene, randabfallende Seite."""
        config = self.config
        asset = self.activities.resolve(page.image)
        prepared = prepare_image(
            asset.path,
            palette,
            self.cache_dir,
            # Raetselseiten sind von der Drei-Farben-Regel ausgenommen: sie
            # bringen ihre eigene Bildwelt mit und faerben nichts am Satz.
            tritone=config.activities.tritone,
            dither=config.images.dither,
            color_space=config.printing.color_space,
            jpeg_quality=config.printing.jpeg_quality,
        )
        media_width, media_height = config.page.media_size
        self._check_dpi(asset.key, prepared, media_width, media_height)
        origin = (
            config.page.bleed + config.page.margin_left,
            config.page.bleed + config.page.margin_bottom,
        )
        flowable = ActivityImage(
            str(prepared.path),
            (media_width, media_height),
            origin,
            title=page.title if config.activities.in_toc else "",
            key=f"raetsel-{asset.key}",
        )
        return [
            NextPageTemplate(f"{palette.name}-activity"),
            PageBreak(),
            flowable,
        ]

    def _body_flowables(self, chapter: Chapter) -> list:
        styles = self.styles(chapter.palette)
        palette = chapter.palette
        out: list = []
        first_paragraph = True

        for block in chapter.body:
            if block.kind == "paragraph":
                text = block.text
                style = styles["body"]
                if first_paragraph:
                    style = styles["body_first"]
                    if self.config.typography.opening_initial:
                        text = self._raise_initial(text, palette)
                    first_paragraph = False
                out.append(Paragraph(text, style))
            elif block.kind == "heading":
                out.append(Paragraph(block.text, styles["subheading"]))
                first_paragraph = False
            elif block.kind == "quote":
                out.append(Paragraph(block.text, styles["quote"]))
            elif block.kind == "list":
                for item in block.items:
                    out.append(Paragraph(item, styles["list"], bulletText="–"))
            elif block.kind == "image":
                out.extend(
                    self._image_flowable(
                        block.src,
                        block.alt,
                        palette,
                        opener=False,
                        height_ratio=chapter.body_height_ratio,
                    )
                )
            elif block.kind == "break":
                out.append(Spacer(1, self.config.typography.body_size * 0.7))
                out.append(Ornament(self.config.page.frame_width, self.color(palette.accent)))
                out.append(Spacer(1, self.config.typography.body_size * 0.7))
        return out

    def _initial_size(self) -> float:
        t = self.config.typography
        return t.body_size * t.initial_scale

    def _initial_overshoot(self) -> float:
        """Vertikaler Versatz, den eine Versalie im Absatz verursacht."""
        t = self.config.typography
        if not t.opening_initial:
            return t.space_after_paragraph
        return max(t.space_after_paragraph, self._initial_size() - t.body_size)

    def _raise_initial(self, text: str, palette: Palette) -> str:
        """Hebt den ersten Buchstaben als Versalie in der Akzentfarbe hervor."""
        # Ein einleitendes Anfuehrungszeichen bleibt klein - vergroessert
        # wird der erste echte Buchstabe.
        match = re.match(r"\A(?:<[^>]+>)*[„“\"'»«\u2019]?\s*([A-Za-zÄÖÜäöüß])", text)
        if not match:
            return text
        index = match.end() - 1
        letter = text[index]
        versal = (
            f'<font size="{self._initial_size():.2f}" '
            f'color="{palette.accent}">{letter}</font>'
        )
        return text[:index] + versal + text[index + 1:]

    def _cover_flowables(self) -> list:
        """Titelfeld des Umschlags. Das Bild kommt aus der Seitenvorlage."""
        config = self.config
        palette = config.colors.get(config.cover_palette)
        styles = self.styles(palette)
        page = config.page
        if not config.cover.typeset_band:
            # Der Umschlag bringt seine Typografie selbst mit; der Rahmen
            # bekommt nur einen Platzhalter, damit die Seite entsteht.
            return [Spacer(1, 1)]
        out: list = [Spacer(1, page.height * config.cover.band_height_ratio * 0.18)]

        if not config.cover.full_page_image and config.cover_image:
            out.extend(
                self._image_flowable(str(config.cover_image), "", palette, opener=True)
            )
        out.append(Paragraph(config.title, styles["cover_title"]))
        out.append(Spacer(1, 9))
        out.append(Rule(page.frame_width * 0.34, self.color(palette.accent), 1.1))
        if config.subtitle:
            out.append(Spacer(1, 9))
            out.append(Paragraph(config.subtitle, styles["cover_subtitle"]))
        if config.author:
            out.append(Spacer(1, 16))
            out.append(Paragraph(config.author, styles["cover_subtitle"]))
        return out

    def _toc_flowables(self, palette: Palette) -> list:
        styles = self.styles(palette)
        toc = TableOfContents()
        toc.levelStyles = [styles["toc_entry"]]
        toc.dotsMinLevel = -1
        # Die interne Tabelle setzt sonst Schwarz als Zellfarbe - das waere
        # eine vierte Farbe auf der Seite, auch wenn sie nichts einfaerbt.
        toc.tableStyle = TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TEXTCOLOR", (0, 0), (-1, -1), self.color(palette.ink)),
        ])
        return [
            Spacer(1, self.config.page.frame_height * 0.12),
            Paragraph(self.config.toc.title, styles["chapter_title"]),
            Spacer(1, 6),
            Rule(self.config.page.frame_width * 0.3, self.color(palette.accent), 0.8),
            Spacer(1, 22),
            toc,
        ]

    def _chapter_flowables(self, chapter: Chapter) -> list:
        styles = self.styles(chapter.palette)
        page = self.config.page
        label = chapter_label(chapter.number)
        out: list = [
            NextPageTemplate(f"{chapter.palette.name}-opener"),
            PageBreak(),
            Spacer(1, page.frame_height * 0.05),
        ]
        if label:
            out.append(Paragraph(label, styles["chapter_number"]))
        out.append(ChapterTitle(chapter.title, styles["chapter_title"], chapter))
        if chapter.subtitle:
            out.append(Paragraph(chapter.subtitle, styles["chapter_subtitle"]))
        out.append(Spacer(1, 8))
        out.append(Ornament(page.frame_width, self.color(chapter.palette.accent)))
        out.append(Spacer(1, 10))

        if chapter.assets.hero:
            out.extend(
                self._image_flowable(
                    chapter.assets.hero.asset.key,
                    chapter.assets.hero.caption if self.config.images.captions else "",
                    chapter.palette,
                    opener=True,
                    height_ratio=chapter.hero_height_ratio,
                )
            )
        out.append(NextPageTemplate(f"{chapter.palette.name}-body"))
        out.extend(self._body_flowables(chapter))
        return out

    # ------------------------------------------------------------------ Build
    def build(self, chapters: list[Chapter] | None = None) -> BuildResult:
        config = self.config
        chapters = chapters if chapters is not None else load_chapters(config, self.library)

        if not len(self.library):
            # Ein leerer Asset-Ordner baut sonst klaglos ein bildloses Buch.
            self.warnings.append(
                f"Der Asset-Ordner {config.assets_dir} enthaelt kein einziges Bild - "
                "das Buch entsteht ohne Illustrationen."
            )

        for palette in config.colors.palettes.values():
            self.recorder.register_palette(palette.name, palette.as_tuple())

        config.output.parent.mkdir(parents=True, exist_ok=True)
        doc = BookDocTemplate(
            str(config.output),
            recorder=self.recorder,
            pagesize=config.page.media_size,
            title=config.title,
            author=config.author or None,
            subject=config.subtitle or None,
            creator="buchbauer",
            leftMargin=config.page.margin_left,
            rightMargin=config.page.margin_right,
            topMargin=config.page.margin_top,
            bottomMargin=config.page.margin_bottom,
        )
        doc.addPageTemplates(self._templates())

        story: list = self._cover_flowables()
        default_palette = config.colors.get(None)
        if config.toc.enabled:
            story.append(NextPageTemplate(f"{default_palette.name}-opener"))
            story.append(PageBreak())
            story.extend(self._toc_flowables(default_palette))

        activities = config.activities
        about = load_about(config, self.library)

        def extras(anchor: int, palette: Palette) -> None:
            """Autorenseite und Raetselseiten hinter Kapitel ``anchor``."""
            if about is not None and config.about.after == anchor:
                story.extend(self._chapter_flowables(about))
            for page in activities.after(anchor):
                story.extend(self._activity_flowables(page, palette))

        extras(0, default_palette)
        for chapter in chapters:
            story.extend(self._chapter_flowables(chapter))
            extras(chapter.number, chapter.palette)
        # Anker hinter dem letzten Kapitel: die Seite schliesst das Buch ab.
        last = chapters[-1] if chapters else None
        last_number = last.number if last else 0
        if about is not None and config.about.after > last_number:
            story.extend(self._chapter_flowables(about))
        for page in activities.beyond(last_number):
            story.extend(
                self._activity_flowables(page, last.palette if last else default_palette)
            )

        # Der Kolumnentitel folgt dem Kapitel, das auf der Seite beginnt.
        doc.running_head = config.title
        original = doc.handle_flowable

        def handle(flowables):
            flowable = flowables[0] if flowables else None
            if isinstance(flowable, ChapterTitle):
                doc.running_head = flowable.chapter.running_head
            return original(flowables)

        doc.handle_flowable = handle
        doc.multiBuild(story, canvasmaker=make_canvasmaker(self.recorder))

        return BuildResult(
            output=config.output,
            pages=doc.page,
            chapters=chapters,
            recorder=self.recorder,
            warnings=list(self.warnings),
        )


def build_book(config: BookConfig) -> BuildResult:
    return BookBuilder(config).build()
