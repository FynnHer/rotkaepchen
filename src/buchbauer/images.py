"""Bildaufbereitung: Reduktion auf die Seitenpalette.

Damit die Drei-Farben-Regel auch fuer Illustrationen gilt, wird jedes
Bild vor dem Einbetten auf genau die drei Farben seiner Kapitelpalette
quantisiert (Tritone). Transparenz wird zuvor auf den Papierton
aufgezogen. Ergebnisse werden im Build-Cache abgelegt.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .config import Palette, hex_to_rgb

__all__ = ["prepare_image", "PreparedImage", "image_colors", "fit_size"]


@dataclass(frozen=True)
class PreparedImage:
    path: Path
    width: int
    height: int
    colors: tuple[tuple[int, int, int], ...]

    @property
    def aspect(self) -> float:
        return self.height / self.width if self.width else 1.0


def image_colors(path: Path) -> tuple[tuple[int, int, int], ...]:
    """Alle tatsaechlich vorkommenden Farben eines Bildes."""
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        found = rgb.getcolors(maxcolors=1 << 24)
    if found is None:  # pragma: no cover - nur bei extrem bunten Bildern
        return ()
    return tuple(sorted(color for _, color in found))


def _palette_image(colors: tuple[tuple[int, int, int], ...]) -> Image.Image:
    flat: list[int] = []
    for rgb in colors:
        flat.extend(rgb)
    # Restplaetze mit der ersten Farbe auffuellen, damit Pillow nur diese waehlt.
    while len(flat) < 256 * 3:
        flat.extend(colors[0])
    palette = Image.new("P", (1, 1))
    palette.putpalette(flat[: 256 * 3])
    return palette


def prepare_image(
    source: Path,
    palette: Palette,
    cache_dir: Path,
    tritone: bool = True,
    dither: bool = True,
    color_space: str = "rgb",
    jpeg_quality: int = 95,
) -> PreparedImage:
    """Bereitet ein Asset fuer eine Kapitelpalette auf.

    Ohne ``tritone`` bleibt die Bildwelt erhalten (Raetselseiten sind von
    der Drei-Farben-Regel ausgenommen); der Farbraum wird trotzdem auf den
    konfigurierten umgestellt.
    """
    source = Path(source)
    colors = palette.rgb_tuple()

    cmyk = color_space == "cmyk"
    if not tritone and not cmyk:
        # Weder Reduktion noch Farbraumwechsel - die Datei kann so bleiben.
        with Image.open(source) as img:
            return PreparedImage(source, img.width, img.height, image_colors(source))

    stamp = hashlib.sha1(
        f"{source}|{source.stat().st_mtime_ns}|{palette.as_tuple()}"
        f"|{tritone}|{dither}|{color_space}".encode()
    ).hexdigest()[:16]
    cache_dir.mkdir(parents=True, exist_ok=True)
    # CMYK kann PNG nicht - fuer den Druck wird als CMYK-JPEG abgelegt.
    suffix = "jpg" if cmyk else "png"
    target = cache_dir / f"{source.stem}-{palette.name}-{stamp}.{suffix}"

    if not target.exists():
        with Image.open(source) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGBA", img.size, hex_to_rgb(palette.paper) + (255,))
                img = Image.alpha_composite(background, img)
            flat = img.convert("RGB")
            if tritone:
                mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
                flat = flat.quantize(palette=_palette_image(colors), dither=mode)
            if cmyk:
                # Der Druck laeuft in CMYK - auch ein Bild, das von der
                # Drei-Farben-Regel ausgenommen ist, darf kein RGB einschleusen.
                flat.convert("CMYK").save(
                    target, "JPEG", quality=jpeg_quality, subsampling=0
                )
            else:
                flat.convert("RGB").save(target, "PNG", optimize=True)

    with Image.open(target) as img:
        size = (img.width, img.height)
    return PreparedImage(target, size[0], size[1], image_colors(target))


def fit_size(
    prepared: PreparedImage, max_width: float, max_height: float
) -> tuple[float, float]:
    """Skaliert proportional in den erlaubten Rahmen."""
    width = max_width
    height = width * prepared.aspect
    if height > max_height:
        height = max_height
        width = height / prepared.aspect if prepared.aspect else max_width
    return (width, height)
