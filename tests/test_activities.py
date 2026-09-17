"""Die Mitmach-Seiten: eigener Ordner, eigener Platz im Buch."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from buchbauer.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parent.parent

ACTIVITIES_TOML = """
[activities]
dir = "raetsel"

[[activities.pages]]
image = "zaehl_raetsel"
after = 2
title = "Rätselseite: Zähl mit!"

[[activities.pages]]
image = "labyrinth_raetsel"
after = 1
title = "Rätselseite: Rotkäppchens Weg"
"""


@pytest.fixture
def activity_book(book_dir: Path) -> Path:
    """Das Miniaturbuch, ergaenzt um zwei Raetselseiten."""
    (book_dir / "raetsel").mkdir()
    for name in ("labyrinth_raetsel", "zaehl_raetsel"):
        shutil.copy(
            ROOT / "assets" / "raetsel" / f"{name}.png",
            book_dir / "raetsel" / f"{name}.png",
        )
    toml = book_dir / "book.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + ACTIVITIES_TOML, encoding="utf-8")
    return book_dir


def test_pages_are_read_and_sorted_by_anchor(activity_book: Path):
    config = load_config(activity_book / "book.toml")
    assert config.activities.enabled
    assert config.activities.directory == (activity_book / "raetsel").resolve()
    # Die Reihenfolge im Buch haengt am Anker, nicht an der Konfiguration.
    assert [page.image for page in config.activities.pages] == [
        "labyrinth_raetsel",
        "zaehl_raetsel",
    ]


def test_anchor_selects_the_chapter(activity_book: Path):
    activities = load_config(activity_book / "book.toml").activities
    assert [p.image for p in activities.after(1)] == ["labyrinth_raetsel"]
    assert [p.image for p in activities.after(2)] == ["zaehl_raetsel"]
    assert activities.after(0) == []
    assert [p.image for p in activities.beyond(1)] == ["zaehl_raetsel"]


def test_disabled_activities_place_nothing(activity_book: Path):
    toml = activity_book / "book.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace(
            '[activities]\ndir = "raetsel"', '[activities]\nenabled = false\ndir = "raetsel"'
        ),
        encoding="utf-8",
    )
    activities = load_config(toml).activities
    assert activities.after(1) == []
    assert activities.beyond(0) == []


def test_missing_anchor_is_a_config_error(book_dir: Path):
    toml = book_dir / "book.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8")
        + '\n[[activities.pages]]\nimage = "zaehl_raetsel"\nafter = "spaeter"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="after"):
        load_config(toml)


def test_page_without_image_is_a_config_error(book_dir: Path):
    toml = book_dir / "book.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8") + "\n[[activities.pages]]\nafter = 1\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="image"):
        load_config(toml)


def test_activity_images_stay_out_of_the_chapter_assignment(activity_book: Path):
    from buchbauer.chapters import load_chapters

    config = load_config(activity_book / "book.toml")
    chapters = load_chapters(config)
    used = {m.asset.key for chapter in chapters for m in chapter.assets.all}
    assert not {"labyrinth-raetsel", "zaehl-raetsel"} & used


class TestBuiltBook:
    """Der Bau mit Raetselseiten - braucht pypdfium2 zum Nachlesen."""

    @staticmethod
    def _build(config):
        from buchbauer.builder import BookBuilder

        return BookBuilder(config).build()

    def test_each_page_adds_one_page_to_the_book(self, activity_book: Path):
        from dataclasses import replace

        config = load_config(activity_book / "book.toml")
        without = replace(
            config,
            activities=replace(config.activities, enabled=False),
            output=activity_book / "build" / "ohne-raetsel.pdf",
        )
        assert self._build(config).pages == self._build(without).pages + 2

    def test_three_colour_rule_still_holds(self, activity_book: Path):
        result = self._build(load_config(activity_book / "book.toml"))
        # Das Raetselbild bringt seine eigene Bildwelt mit, faerbt aber
        # nichts am Satz - die Seite bleibt bei Papier und Schnittmarken.
        assert result.violations == []

    def test_titles_appear_in_the_table_of_contents(self, activity_book: Path):
        pdfium = pytest.importorskip("pypdfium2")
        result = self._build(load_config(activity_book / "book.toml"))
        pdf = pdfium.PdfDocument(str(result.output))
        text = "\n".join(
            pdf[i].get_textpage().get_text_range() for i in range(len(pdf))
        )
        assert "Rätselseite: Rotkäppchens Weg" in text
        assert "Rätselseite: Zähl mit!" in text
