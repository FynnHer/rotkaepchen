#!/usr/bin/env python3
"""Erzeugt Platzhalter-Illustrationen im Scherenschnitt-Stil.

Die Bilder landen in beispiele/bilder/ und sind bewusst schlicht: sie
belegen die Asset-Pipeline end-to-end und werden spaeter durch echte
Illustrationen mit denselben Dateinamen ersetzt. Der Builder reduziert
ohnehin jedes Bild auf die Palette des Kapitels, deshalb reichen hier
zwei Tonwerte.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

# Druckaufloesung: A5 randabfallend bei 300 dpi braucht rund 1800 x 2550 px.
W, H = 1800, 1160
COVER_W, COVER_H = 1860, 2640
SKY = (238, 232, 218)
FAR = (150, 152, 138)
NEAR = (38, 46, 40)
MARK = (168, 30, 45)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "beispiele" / "bilder"


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), SKY)
    return img, ImageDraw.Draw(img)


def fir(draw, x: float, base: float, height: float, width: float, fill) -> None:
    tiers = 4
    for i in range(tiers):
        top = base - height * (1 - i / tiers) - height * 0.12
        spread = width * (0.45 + 0.18 * i)
        y = base - height * (1 - (i + 1) / tiers) * 0.85
        draw.polygon([(x, top), (x - spread, y), (x + spread, y)], fill=fill)
    draw.rectangle([x - width * 0.07, base - height * 0.1, x + width * 0.07, base], fill=fill)


def treeline(draw, base: float, count: int, height: float, fill, seed: int) -> None:
    rng = random.Random(seed)
    for i in range(count):
        x = W * (i + 0.5) / count + rng.uniform(-30, 30)
        scale = rng.uniform(0.75, 1.25)
        fir(draw, x, base, height * scale, 95 * scale, fill)


def ground(draw, y: float, fill) -> None:
    draw.rectangle([0, y, W, H], fill=fill)


def hooded_figure(draw, cx: float, base: float, scale: float, cloak, face) -> None:
    h = 300 * scale
    draw.polygon(
        [(cx, base - h), (cx - h * 0.42, base), (cx + h * 0.42, base)], fill=cloak
    )
    draw.ellipse(
        [cx - h * 0.17, base - h * 1.05, cx + h * 0.17, base - h * 0.72], fill=cloak
    )
    draw.ellipse(
        [cx - h * 0.1, base - h * 0.95, cx + h * 0.1, base - h * 0.76], fill=face
    )


def save(img: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    img.save(path, "PNG", optimize=True)
    print(f"  {path.relative_to(ROOT)}")


def make_wald() -> None:
    img, d = canvas()
    base = H * 0.86
    treeline(d, base - 60, 9, 330, FAR, seed=1)
    ground(d, base, NEAR)
    treeline(d, base + 10, 7, 470, NEAR, seed=2)
    for i in range(5):  # Lichtstrahlen
        x = 220 + i * 230
        d.polygon([(x, 0), (x + 40, 0), (x - 90, base), (x - 150, base)], fill=FAR)
    save(img, "wald")


def make_rotkaeppchen() -> None:
    img, d = canvas()
    base = H * 0.88
    treeline(d, base - 40, 6, 300, FAR, seed=3)
    ground(d, base, NEAR)
    hooded_figure(d, W * 0.46, base + 6, 1.5, MARK, SKY)
    cx, cy = W * 0.63, base - 130   # Korb
    d.rounded_rectangle([cx - 70, cy, cx + 70, cy + 95], radius=14, fill=NEAR)
    d.arc([cx - 70, cy - 70, cx + 70, cy + 70], 180, 360, fill=NEAR, width=14)
    save(img, "rotkaeppchen")


def make_wolf() -> None:
    img, d = canvas()
    base = H * 0.84
    treeline(d, base - 30, 7, 280, FAR, seed=5)
    ground(d, base, NEAR)
    cx, cy = W * 0.5, base - 210
    d.ellipse([cx - 300, cy - 90, cx + 170, cy + 130], fill=NEAR)          # Rumpf
    d.polygon([(cx + 120, cy - 60), (cx + 400, cy - 10), (cx + 130, cy + 80)], fill=NEAR)  # Kopf
    d.polygon([(cx + 150, cy - 70), (cx + 190, cy - 190), (cx + 230, cy - 60)], fill=NEAR)  # Ohr
    d.polygon([(cx + 230, cy - 60), (cx + 270, cy - 175), (cx + 305, cy - 45)], fill=NEAR)
    d.polygon([(cx - 290, cy - 40), (cx - 470, cy - 190), (cx - 250, cy + 40)], fill=NEAR)  # Rute
    for dx in (-230, -130, 60, 140):                                        # Laeufe
        d.rectangle([cx + dx - 26, cy + 90, cx + dx + 26, base + 8], fill=NEAR)
    d.ellipse([cx + 268, cy - 32, cx + 308, cy + 8], fill=MARK)             # Auge
    save(img, "wolf")


def make_grossmutter() -> None:
    img, d = canvas()
    d.rectangle([0, H * 0.82, W, H], fill=NEAR)                             # Boden
    d.rectangle([W * 0.06, H * 0.1, W * 0.34, H * 0.5], fill=FAR)           # Fenster
    d.rectangle([W * 0.195, H * 0.1, W * 0.205, H * 0.5], fill=SKY)
    d.rectangle([W * 0.06, H * 0.295, W * 0.34, H * 0.305], fill=SKY)
    bed = [W * 0.4, H * 0.45, W * 0.95, H * 0.83]                           # Bett
    d.rounded_rectangle(bed, radius=26, fill=NEAR)
    d.rounded_rectangle([W * 0.4, H * 0.3, W * 0.47, H * 0.83], radius=20, fill=NEAR)
    d.ellipse([W * 0.48, H * 0.38, W * 0.63, H * 0.52], fill=SKY)           # Haube
    d.ellipse([W * 0.51, H * 0.42, W * 0.60, H * 0.51], fill=FAR)           # Gesicht
    d.arc([W * 0.46, H * 0.33, W * 0.65, H * 0.52], 180, 360, fill=MARK, width=16)
    save(img, "grossmutter")


def make_titelbild() -> None:
    """Hochformatiges Titelbild, randabfallend ueber die ganze Seite."""
    global W, H
    W, H = COVER_W, COVER_H
    try:
        img, d = canvas()
        base = H * 0.72
        treeline(d, base - 320, 7, 760, FAR, seed=21)
        treeline(d, base - 120, 9, 620, FAR, seed=22)
        ground(d, base, NEAR)
        treeline(d, base + 40, 6, 900, NEAR, seed=23)
        for i in range(4):
            x = 300 + i * 420
            d.polygon([(x, 0), (x + 70, 0), (x - 170, base), (x - 260, base)], fill=FAR)
        hooded_figure(d, W * 0.5, base + 30, 2.4, MARK, SKY)
        save(img, "titelbild")
    finally:
        W, H = 1800, 1160


def make_jaeger() -> None:
    img, d = canvas()
    base = H * 0.88
    treeline(d, base - 50, 8, 320, FAR, seed=9)
    ground(d, base, NEAR)
    cx = W * 0.44
    d.polygon([(cx, base - 380), (cx - 120, base - 40), (cx + 120, base - 40)], fill=NEAR)
    d.rectangle([cx - 60, base - 60, cx + 60, base + 6], fill=NEAR)
    d.ellipse([cx - 52, base - 470, cx + 52, base - 366], fill=NEAR)        # Kopf
    d.ellipse([cx - 130, base - 445, cx + 130, base - 400], fill=NEAR)      # Hutkrempe
    d.polygon([(cx - 55, base - 440), (cx, base - 530), (cx + 55, base - 440)], fill=NEAR)
    d.polygon([(cx + 60, base - 470), (cx + 92, base - 545), (cx + 78, base - 452)], fill=MARK)
    angle = math.radians(28)                                                # Buechse
    x0, y0 = cx + 60, base - 330
    x1, y1 = x0 + 330 * math.cos(angle), y0 - 330 * math.sin(angle)
    d.line([(x0, y0), (x1, y1)], fill=NEAR, width=22)
    save(img, "jaeger")


def main() -> None:
    print("Platzhalter-Illustrationen:")
    make_titelbild()
    make_wald()
    make_rotkaeppchen()
    make_wolf()
    make_grossmutter()
    make_jaeger()


if __name__ == "__main__":
    main()
