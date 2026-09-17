import pytest
from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm

from buchbauer.colors import color_to_hex, hex_color
from buchbauer.config import ConfigError, load_config


def _with(book_dir, extra: str):
    path = book_dir / "book.toml"
    path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")
    return load_config(path)


def test_bleed_enlarges_the_media_box(book_dir):
    config = _with(book_dir, "\n[print]\nbleed_mm = 3.0\n")
    trim_w, trim_h = config.page.size
    media_w, media_h = config.page.media_size
    assert media_w == pytest.approx(trim_w + 6 * mm)
    assert media_h == pytest.approx(trim_h + 6 * mm)


def test_without_bleed_media_box_equals_trim(book_config):
    assert book_config.page.media_size == book_config.page.size


def test_crop_marks_require_a_bleed(book_dir):
    with pytest.raises(ConfigError, match="Anschnitt"):
        _with(book_dir, "\n[print]\ncrop_marks = true\nbleed_mm = 0.0\n")


def test_unknown_colour_space_is_rejected(book_dir):
    with pytest.raises(ConfigError, match="color_space"):
        _with(book_dir, '\n[print]\ncolor_space = "lab"\n')


def test_cmyk_colours_survive_the_round_trip():
    for value in ("#a81e2d", "#2a3b2e", "#f4ecdc", "#000000", "#ffffff"):
        assert color_to_hex(hex_color(value, "cmyk")) == value


def test_cmyk_produces_cmyk_colour_objects():
    assert isinstance(hex_color("#a81e2d", "cmyk"), CMYKColor)
    assert not isinstance(hex_color("#a81e2d", "rgb"), CMYKColor)


def test_max_total_limits_the_colours_of_the_whole_book(book_dir):
    path = book_dir / "book.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("max_total = 6", "max_total = 3"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="verschiedene Farben"):
        load_config(path)


def test_max_total_zero_disables_the_check(book_dir):
    path = book_dir / "book.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("max_total = 6", "max_total = 0"),
        encoding="utf-8",
    )
    assert len(load_config(path).colors.palettes) == 2
