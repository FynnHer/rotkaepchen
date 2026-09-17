"""Die Seite ueber die Verfasser und die Umschlag-Schalter."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from buchbauer.assets import AssetLibrary
from buchbauer.chapters import load_about, load_chapters
from buchbauer.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parent.parent

ABOUT_MD = """---
title: Wer waren die Gebrüder Grimm?
subtitle: Von zwei Brüdern
hero: portraet
---

Jacob und Wilhelm Grimm sammelten Märchen und schrieben sie auf.

Bis heute werden ihre Märchen auf der ganzen Welt vorgelesen.
"""

ABOUT_TOML = """
[about]
enabled = true
file    = "seiten/verfasser.md"
after   = 0
"""


@pytest.fixture
def about_book(book_dir: Path) -> Path:
    (book_dir / "seiten").mkdir()
    (book_dir / "seiten" / "verfasser.md").write_text(ABOUT_MD, encoding="utf-8")
    shutil.copy(
        ROOT / "beispiele" / "bilder" / "grossmutter.png",
        book_dir / "assets" / "portraet.png",
    )
    toml = book_dir / "book.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + ABOUT_TOML, encoding="utf-8")
    return book_dir


def test_about_is_a_chapter_without_a_number(about_book: Path):
    config = load_config(about_book / "book.toml")
    about = load_about(config)
    assert about is not None
    assert about.number == 0
    assert about.title == "Wer waren die Gebrüder Grimm?"
    assert about.assets.hero is not None
    assert about.assets.hero.asset.key == "portraet"


def test_without_the_section_there_is_no_page(book_config):
    assert load_about(book_config) is None


def test_missing_file_is_a_config_error(book_dir: Path):
    toml = book_dir / "book.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8")
        + '\n[about]\nenabled = true\nfile = "seiten/fehlt.md"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="nicht gefunden"):
        load_config(toml)


def test_about_does_not_take_part_in_the_keyword_automatic(about_book: Path):
    """Der Text nennt keinen Wolf - ein Bild bekommt die Seite nur explizit."""
    config = load_config(about_book / "book.toml")
    toml = about_book / "seiten" / "verfasser.md"
    toml.write_text(ABOUT_MD.replace("hero: portraet\n", ""), encoding="utf-8")
    about = load_about(config)
    assert about is not None and about.assets.hero is None


def test_chapter_numbers_ignore_the_about_page(about_book: Path):
    config = load_config(about_book / "book.toml")
    assert [c.number for c in load_chapters(config)] == [1, 2]


def test_several_asset_dirs_first_one_wins(book_dir: Path):
    """Ein echtes Bild ersetzt den Platzhalter allein durch seinen Ordner."""
    (book_dir / "echte").mkdir()
    shutil.copy(
        ROOT / "beispiele" / "bilder" / "jaeger.png", book_dir / "echte" / "wolf.png"
    )
    library = AssetLibrary([book_dir / "echte", book_dir / "assets"])
    assert library.resolve("wolf").path == book_dir / "echte" / "wolf.png"
    # Der zweite Ordner steuert weiterhin bei, was der erste nicht hat.
    assert library.resolve("wald").path == book_dir / "assets" / "wald.png"


def test_asset_dirs_can_be_a_list_in_the_config(book_dir: Path):
    toml = book_dir / "book.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace(
            'assets_dir   = "assets"', 'assets_dir   = ["echte", "assets"]'
        ),
        encoding="utf-8",
    )
    (book_dir / "echte").mkdir()
    config = load_config(toml)
    assert [p.name for p in config.assets_dir] == ["echte", "assets"]


class TestBuiltBook:
    @staticmethod
    def _build(config):
        from buchbauer.builder import BookBuilder

        return BookBuilder(config).build()

    def test_the_page_stands_before_the_first_chapter(self, about_book: Path):
        pdfium = pytest.importorskip("pypdfium2")
        result = self._build(load_config(about_book / "book.toml"))
        pdf = pdfium.PdfDocument(str(result.output))
        pages = [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]
        about_page = next(i for i, t in enumerate(pages) if "Jacob und Wilhelm" in t)
        # Der Aufschlag des ersten Kapitels, nicht sein Eintrag im Inhalt.
        first_chapter = next(i for i, t in enumerate(pages) if "Im Wald standen" in t)
        assert about_page < first_chapter
        # Ohne Nummer: eine Zeile "Kapitel 0" gibt es nicht.
        assert "Kapitel 0" not in "\n".join(pages)

    def test_the_title_appears_in_the_table_of_contents(self, about_book: Path):
        pdfium = pytest.importorskip("pypdfium2")
        result = self._build(load_config(about_book / "book.toml"))
        pdf = pdfium.PdfDocument(str(result.output))
        toc = next(
            pdf[i].get_textpage().get_text_range()
            for i in range(len(pdf))
            if "Inhalt" in pdf[i].get_textpage().get_text_range()
        )
        assert "Wer waren die Gebrüder Grimm?" in toc

    def test_cover_without_band_carries_no_typesetting(self, book_dir: Path):
        pdfium = pytest.importorskip("pypdfium2")
        toml = book_dir / "book.toml"
        toml.write_text(
            toml.read_text(encoding="utf-8")
            + "\n[cover]\ntypeset_band = false\ntritone = false\n",
            encoding="utf-8",
        )
        result = self._build(load_config(toml))
        pdf = pdfium.PdfDocument(str(result.output))
        assert pdf[0].get_textpage().get_text_range().strip() == ""

    def test_cover_with_band_still_sets_the_title(self, book_config):
        pdfium = pytest.importorskip("pypdfium2")
        result = self._build(book_config)
        pdf = pdfium.PdfDocument(str(result.output))
        assert "Testbuch" in pdf[0].get_textpage().get_text_range()


def test_body_image_height_ratio_reaches_the_page(about_book: Path):
    """Die Werbe-Umschlaege im Fliesstext bekommen ihre eigene Hoehe."""
    toml = about_book / "book.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8") + "body_image_height_ratio = 0.30\n",
        encoding="utf-8",
    )
    config = load_config(toml)
    assert config.about.body_image_height_ratio == pytest.approx(0.30)
    about = load_about(config)
    assert about is not None
    assert about.body_height_ratio == pytest.approx(0.30)


def test_without_the_setting_body_images_keep_the_usual_height(about_book: Path):
    about = load_about(load_config(about_book / "book.toml"))
    assert about is not None and about.body_height_ratio is None
