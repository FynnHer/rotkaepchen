"""End-to-End: aus zwei Beispielkapiteln entsteht ein PDF."""

import pytest

pypdfium2 = pytest.importorskip("pypdfium2")

from buchbauer.builder import BookBuilder  # noqa: E402
from buchbauer.config import load_config  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory, request):
    from tests.conftest import MINIMAL_TOML  # noqa: F401  (nur zur Doku)


def _build(config):
    return BookBuilder(config).build()


def test_two_chapters_produce_one_pdf(book_config):
    result = _build(book_config)
    assert result.output.exists()
    assert result.output.suffix == ".pdf"
    assert result.pages >= 4              # Umschlag, Inhalt, zwei Kapitel
    assert len(result.chapters) == 2


def test_three_colour_rule_holds_on_every_page(book_config):
    result = _build(book_config)
    assert result.violations == []
    assert result.recorder.pages, "es wurde keine einzige Farbe protokolliert"
    for page, colors in result.recorder.pages.items():
        assert len(colors) <= book_config.colors.max_per_page, page


def test_every_page_uses_only_its_palette(book_config):
    result = _build(book_config)
    for page, colors in result.recorder.pages.items():
        allowed = set(result.recorder.palette_colors[result.recorder.page_palettes[page]])
        assert colors <= allowed, (page, colors - allowed)


def test_chapter_titles_and_assets_land_in_the_document(book_config):
    result = _build(book_config)
    document = pypdfium2.PdfDocument(str(result.output))
    text = "".join(document[i].get_textpage().get_text_range() for i in range(len(document)))
    assert "Testbuch" in text
    assert "Erstes Kapitel" in text
    assert "Zweites Kapitel" in text
    assert "Der Wolf" in text             # Bildunterschrift aus der Konfiguration


def test_page_box_matches_the_media_size(book_config):
    result = _build(book_config)
    document = pypdfium2.PdfDocument(str(result.output))
    width, height = document[0].get_size()
    assert width == pytest.approx(book_config.page.media_size[0], abs=0.5)
    assert height == pytest.approx(book_config.page.media_size[1], abs=0.5)


def test_layout_changes_only_need_the_config(book_dir):
    """Format und Schriftgrad wirken, ohne eine Kapitel-Datei anzufassen."""
    path = book_dir / "book.toml"
    chapters = sorted((book_dir / "chapters").glob("*.md"))
    before = [c.read_text(encoding="utf-8") for c in chapters]

    small_config = load_config(path)
    small = _build(small_config)
    assert small.pages >= 4

    path.write_text(
        path.read_text(encoding="utf-8").replace('format = "A6"', 'format = "A4"')
        + "\n[typography]\nbody_size_pt = 20.0\nleading_factor = 2.0\n",
        encoding="utf-8",
    )
    config = load_config(path)
    large = _build(config)

    # Das Format schlaegt bis in die fertige Datei durch ...
    document = pypdfium2.PdfDocument(str(large.output))
    assert document[0].get_size()[0] == pytest.approx(config.page.media_size[0], abs=0.5)
    assert config.page.media_size[0] > small_config.page.media_size[0]
    assert config.typography.body_leading == pytest.approx(40.0)

    # ... und keine einzige Kapitel-Datei musste dafuer angefasst werden.
    assert [c.read_text(encoding="utf-8") for c in chapters] == before


def test_cmyk_build_stays_within_the_palette(book_dir):
    path = book_dir / "book.toml"
    path.write_text(
        path.read_text(encoding="utf-8") + '\n[print]\ncolor_space = "cmyk"\nbleed_mm = 3.0\n',
        encoding="utf-8",
    )
    result = _build(load_config(path))
    assert result.output.exists()
    assert result.violations == []


def test_missing_asset_reference_is_reported(book_dir):
    from buchbauer.assets import AssetError

    chapter = book_dir / "chapters" / "01-erstes.md"
    chapter.write_text("---\ntitle: X\norder: 1\nhero: einhorn\n---\n\nText.\n", encoding="utf-8")
    with pytest.raises(AssetError, match="einhorn"):
        _build(load_config(book_dir / "book.toml"))
