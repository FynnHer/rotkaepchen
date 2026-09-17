from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from buchbauer.config import load_config  # noqa: E402

MINIMAL_TOML = """
[book]
title        = "Testbuch"
subtitle     = "Zwei Kapitel"
author       = "Testlauf"
chapters_dir = "chapters"
assets_dir   = "assets"
output       = "build/test.pdf"
cover_image  = "wald"
cover_palette = "hell"

[page]
format = "A6"

[colors]
max_total = 6        # die Fixture prueft den Paletten-Wechsel
default_palette = "hell"
rotate = ["hell", "dunkel"]

[colors.palettes.hell]
paper  = "#F4ECDC"
ink    = "#2A3B2E"
accent = "#A81E2D"

[colors.palettes.dunkel]
paper  = "#E8E5D3"
ink    = "#1F2E24"
accent = "#8A1C26"

[assets.aliases]
wolf = ["Wolf", "Untier"]
wald = ["Wald", "Bäume"]

[assets.captions]
wolf = "Der Wolf"
"""

CHAPTER_ONE = """---
title: Erstes Kapitel
order: 1
---

Im **Wald** standen die Bäume dicht. Der Wald war still, und im Wald sang kein Vogel.

Am Rand des Waldes blieb das Kind stehen und sah in den Wald hinein.
"""

CHAPTER_TWO = """---
title: Zweites Kapitel
order: 2
---

Der Wolf kam aus dem Dickicht. Der Wolf war ein Untier, und der Wolf hatte Hunger.

> Guten Tag, sagte der Wolf.

Das Untier trat näher.
"""


@pytest.fixture
def book_dir(tmp_path: Path) -> Path:
    """Ein vollstaendiges Miniaturbuch mit zwei Kapiteln und zwei Assets."""
    (tmp_path / "chapters").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "book.toml").write_text(MINIMAL_TOML, encoding="utf-8")
    (tmp_path / "chapters" / "01-erstes.md").write_text(CHAPTER_ONE, encoding="utf-8")
    (tmp_path / "chapters" / "02-zweites.md").write_text(CHAPTER_TWO, encoding="utf-8")
    for name in ("wald", "wolf"):
        shutil.copy(
            ROOT / "beispiele" / "bilder" / f"{name}.png",
            tmp_path / "assets" / f"{name}.png",
        )
    return tmp_path


@pytest.fixture
def book_config(book_dir: Path):
    return load_config(book_dir / "book.toml")


@pytest.fixture(scope="session")
def project_config():
    return load_config(ROOT / "book.toml")
