import pytest
from reportlab.lib.units import mm

from buchbauer.config import ConfigError, load_config


def test_defaults_fill_missing_sections(book_config):
    assert book_config.typography.body_size == 11.0       # Default
    assert book_config.images.tritone is True
    assert book_config.toc.title == "Inhalt"


def test_page_format_and_margins(book_config):
    assert round(book_config.page.width) == 298           # A6
    assert book_config.page.margin_top == pytest.approx(18 * mm)
    assert book_config.page.frame_width > 0


def test_layout_parameters_are_central(book_dir):
    """Eine Aenderung an book.toml wirkt, ohne Kapitel anzufassen."""
    toml = (book_dir / "book.toml").read_text(encoding="utf-8")
    toml = toml.replace('format = "A6"', 'format = "A4"\nmargin_left_mm = 30.0')
    toml += '\n[typography]\nbody_size_pt = 14.0\nleading_factor = 2.0\n'
    (book_dir / "book.toml").write_text(toml, encoding="utf-8")

    config = load_config(book_dir / "book.toml")
    assert round(config.page.width) == 595                # A4
    assert config.page.margin_left == pytest.approx(30 * mm)
    assert config.typography.body_size == 14.0
    assert config.typography.body_leading == pytest.approx(28.0)


def test_custom_page_size_in_mm(book_dir):
    toml = (book_dir / "book.toml").read_text(encoding="utf-8")
    (book_dir / "book.toml").write_text(
        toml.replace('format = "A6"', "format = [120.0, 200.0]"), encoding="utf-8"
    )
    config = load_config(book_dir / "book.toml")
    assert config.page.width == pytest.approx(120 * mm)
    assert config.page.height == pytest.approx(200 * mm)


def test_palette_must_have_exactly_three_roles(book_dir):
    toml = (book_dir / "book.toml").read_text(encoding="utf-8")
    (book_dir / "book.toml").write_text(
        toml.replace('accent = "#A81E2D"', 'accent = "#A81E2D"\nextra  = "#123456"', 1),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="unerlaubte Farbrollen"):
        load_config(book_dir / "book.toml")


def test_incomplete_palette_is_rejected(book_dir):
    toml = (book_dir / "book.toml").read_text(encoding="utf-8")
    (book_dir / "book.toml").write_text(
        toml.replace('ink    = "#2A3B2E"\n', "", 1), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="fehlen die Farben"):
        load_config(book_dir / "book.toml")


def test_unknown_palette_reference_is_rejected(book_dir):
    toml = (book_dir / "book.toml").read_text(encoding="utf-8")
    (book_dir / "book.toml").write_text(
        toml.replace('rotate = ["hell", "dunkel"]', 'rotate = ["hell", "gibtsnicht"]'),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Unbekannte Palette"):
        load_config(book_dir / "book.toml")


def test_max_per_page_below_palette_size_is_rejected(book_dir):
    toml = (book_dir / "book.toml").read_text(encoding="utf-8")
    (book_dir / "book.toml").write_text(
        toml.replace("[colors]", "[colors]\nmax_per_page = 2"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="max_per_page"):
        load_config(book_dir / "book.toml")


def test_margins_larger_than_page_are_rejected(book_dir):
    toml = (book_dir / "book.toml").read_text(encoding="utf-8")
    (book_dir / "book.toml").write_text(
        toml.replace('format = "A6"', 'format = "A6"\nmargin_left_mm = 90.0'),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Satzspiegel"):
        load_config(book_dir / "book.toml")


def test_palette_rotation_and_explicit_choice(book_config):
    colors = book_config.colors
    assert colors.for_chapter(0, None).name == "hell"
    assert colors.for_chapter(1, None).name == "dunkel"
    assert colors.for_chapter(2, None).name == "hell"
    assert colors.for_chapter(0, "dunkel").name == "dunkel"
