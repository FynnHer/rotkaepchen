"""Durchsetzung der Drei-Farben-Regel.

Die Regel wird nicht nur per Konvention eingehalten, sondern gemessen:
``PaletteCanvas`` protokolliert jede Farbe, die waehrend des Zeichnens
gesetzt wird, und zwar pro Seite. Bilder werden separat behandelt - sie
werden vor dem Einbetten auf die Seitenpalette reduziert (siehe
``images.py``), sodass auch Bildpixel keine vierte Farbe einschleppen
koennen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.colors import CMYKColor, Color, HexColor, toColor
from reportlab.pdfgen import canvas

__all__ = ["ColorRecorder", "PaletteCanvas", "ColorViolation", "make_canvasmaker"]


def color_to_hex(value) -> str:
    """Normalisiert eine Farbe auf ihren RGB-Hexwert.

    Auch CMYK-Farben werden zurueckgerechnet, damit das Farbprotokoll
    unabhaengig vom Ausgabefarbraum vergleichbar bleibt.
    """
    if isinstance(value, CMYKColor):
        c, m, y, k = value.cyan, value.magenta, value.yellow, value.black
        rgb = ((1.0 - x) * (1.0 - k) for x in (c, m, y))
        return "#%02x%02x%02x" % tuple(round(v * 255) for v in rgb)
    color = value if isinstance(value, Color) else toColor(value)
    return "#%02x%02x%02x" % (
        round(color.red * 255),
        round(color.green * 255),
        round(color.blue * 255),
    )


def rgb_to_cmyk(value: str) -> tuple[float, float, float, float]:
    """Naive Umrechnung ohne ICC-Profil - fuer ein Sonderfarbenbuch genau genug."""
    color = HexColor(value)
    r, g, b = color.red, color.green, color.blue
    k = 1.0 - max(r, g, b)
    if k >= 1.0:
        return (0.0, 0.0, 0.0, 1.0)
    scale = 1.0 - k
    return ((1.0 - r - k) / scale, (1.0 - g - k) / scale, (1.0 - b - k) / scale, k)


def hex_color(value: str, color_space: str = "rgb") -> Color:
    """Erzeugt eine ReportLab-Farbe im gewuenschten Ausgabefarbraum."""
    if color_space == "cmyk":
        return CMYKColor(*rgb_to_cmyk(value))
    return HexColor(value)


@dataclass
class ColorViolation:
    page: int
    palette: str
    used: list[str]
    allowed: list[str]
    reason: str

    def __str__(self) -> str:
        return (
            f"Seite {self.page} (Palette '{self.palette}'): {self.reason} "
            f"- verwendet {self.used}, erlaubt {self.allowed}"
        )


@dataclass
class ColorRecorder:
    """Sammelt die pro Seite gesetzten Farben waehrend des PDF-Baus."""

    max_per_page: int = 3
    pages: dict[int, set[str]] = field(default_factory=dict)
    page_palettes: dict[int, str] = field(default_factory=dict)
    palette_colors: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def reset(self) -> None:
        self.pages.clear()
        self.page_palettes.clear()

    def register_palette(self, name: str, colors: tuple[str, ...]) -> None:
        self.palette_colors[name] = tuple(c.lower() for c in colors)

    def note(self, page: int, value) -> None:
        self.pages.setdefault(page, set()).add(color_to_hex(value).lower())

    def bind_page(self, page: int, palette_name: str) -> None:
        self.page_palettes[page] = palette_name

    def violations(self) -> list[ColorViolation]:
        found: list[ColorViolation] = []
        for page in sorted(self.pages):
            used = sorted(self.pages[page])
            palette_name = self.page_palettes.get(page, "?")
            allowed = list(self.palette_colors.get(palette_name, ()))
            if len(used) > self.max_per_page:
                found.append(
                    ColorViolation(
                        page, palette_name, used, allowed,
                        f"{len(used)} Farben, erlaubt sind {self.max_per_page}",
                    )
                )
            stray = [c for c in used if allowed and c not in allowed]
            if stray:
                found.append(
                    ColorViolation(
                        page, palette_name, used, allowed,
                        f"Farben ausserhalb der Palette: {stray}",
                    )
                )
        return found

    def report(self) -> dict:
        return {
            "max_per_page": self.max_per_page,
            "pages": [
                {
                    "page": page,
                    "palette": self.page_palettes.get(page, "?"),
                    "colors": sorted(self.pages[page]),
                    "count": len(self.pages[page]),
                }
                for page in sorted(self.pages)
            ],
            "violations": [
                {
                    "page": v.page,
                    "palette": v.palette,
                    "used": v.used,
                    "allowed": v.allowed,
                    "reason": v.reason,
                }
                for v in self.violations()
            ],
        }

    def write_report(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.report(), indent=2, ensure_ascii=False), encoding="utf-8"
        )


class PaletteCanvas(canvas.Canvas):
    """Canvas, das jede gesetzte Fuell- und Linienfarbe protokolliert."""

    recorder: ColorRecorder | None = None

    def _note(self, value) -> None:
        if self.recorder is not None:
            try:
                self.recorder.note(self.getPageNumber(), value)
            except Exception:  # pragma: no cover - Protokoll darf nie den Bau stoppen
                pass

    def setFillColor(self, aColor, alpha=None):
        self._note(aColor)
        return super().setFillColor(aColor, alpha)

    def setStrokeColor(self, aColor, alpha=None):
        self._note(aColor)
        return super().setStrokeColor(aColor, alpha)

    def setFillColorRGB(self, r, g, b, alpha=None):
        self._note(Color(r, g, b))
        return super().setFillColorRGB(r, g, b, alpha)

    def setStrokeColorRGB(self, r, g, b, alpha=None):
        self._note(Color(r, g, b))
        return super().setStrokeColorRGB(r, g, b, alpha)

    def setFillGray(self, gray, alpha=None):
        self._note(Color(gray, gray, gray))
        return super().setFillGray(gray, alpha)

    def setStrokeGray(self, gray, alpha=None):
        self._note(Color(gray, gray, gray))
        return super().setStrokeGray(gray, alpha)


def make_canvasmaker(recorder: ColorRecorder):
    """Erzeugt eine Canvas-Klasse, die an diesen Recorder gebunden ist."""

    class BoundPaletteCanvas(PaletteCanvas):
        pass

    BoundPaletteCanvas.recorder = recorder
    return BoundPaletteCanvas
