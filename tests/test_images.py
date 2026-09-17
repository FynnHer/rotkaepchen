from PIL import Image

from buchbauer.config import Palette, hex_to_rgb
from buchbauer.images import fit_size, image_colors, prepare_image

PALETTE = Palette(name="p", paper="#F4ECDC", ink="#2A3B2E", accent="#A81E2D")


def _source(tmp_path, mode="RGB"):
    path = tmp_path / "bunt.png"
    img = Image.new(mode, (40, 20))
    for x in range(40):
        for y in range(20):
            img.putpixel((x, y), (x * 6 % 256, y * 12 % 256, 90) + ((255,) if mode == "RGBA" else ()))
    img.save(path)
    return path


def test_tritone_reduces_to_exactly_the_palette(tmp_path):
    prepared = prepare_image(_source(tmp_path), PALETTE, tmp_path / "cache")
    allowed = set(PALETTE.rgb_tuple())
    assert set(prepared.colors) <= allowed
    assert len(set(prepared.colors)) > 1          # es bleibt ein Bild, kein Block


def test_transparency_is_composited_onto_the_paper_tone(tmp_path):
    path = tmp_path / "transparent.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
    prepared = prepare_image(path, PALETTE, tmp_path / "cache")
    assert set(prepared.colors) == {hex_to_rgb(PALETTE.paper)}


def test_result_is_cached_and_reused(tmp_path):
    cache = tmp_path / "cache"
    source = _source(tmp_path)
    first = prepare_image(source, PALETTE, cache)
    stamp = first.path.stat().st_mtime_ns
    second = prepare_image(source, PALETTE, cache)
    assert second.path == first.path
    assert second.path.stat().st_mtime_ns == stamp


def test_different_palettes_produce_different_files(tmp_path):
    other = Palette(name="q", paper="#FFFFFF", ink="#000000", accent="#FF0000")
    source = _source(tmp_path)
    a = prepare_image(source, PALETTE, tmp_path / "cache")
    b = prepare_image(source, other, tmp_path / "cache")
    assert a.path != b.path


def test_tritone_can_be_switched_off(tmp_path):
    source = _source(tmp_path)
    prepared = prepare_image(source, PALETTE, tmp_path / "cache", tritone=False)
    assert prepared.path == source
    assert len(set(image_colors(source))) > 3


def test_fit_size_keeps_the_aspect_ratio(tmp_path):
    prepared = prepare_image(_source(tmp_path), PALETTE, tmp_path / "cache")  # 40x20
    assert fit_size(prepared, 200, 500) == (200, 100)
    assert fit_size(prepared, 200, 50) == (100, 50)
