import pytest

from buchbauer.assets import AssetError, AssetLibrary, slugify
from buchbauer.chapters import load_chapters


def test_slugify_handles_umlauts():
    assert slugify("Großmutters Hütte") == "grossmutters-huette"
    assert slugify("Jäger") == "jaeger"


def test_library_indexes_by_slug(book_config):
    library = AssetLibrary(book_config.assets_dir, book_config.asset_aliases)
    assert set(library.assets) == {"wald", "wolf"}
    assert "wolf" in library


def test_numbering_prefix_is_not_part_of_the_key(tmp_path):
    (tmp_path / "03-Wölfin.png").write_bytes(b"x")
    library = AssetLibrary(tmp_path)
    assert "woelfin" in library.assets


def test_resolve_accepts_key_and_filename(book_config):
    library = AssetLibrary(book_config.assets_dir)
    assert library.resolve("wolf").key == "wolf"
    assert library.resolve("wolf.png").key == "wolf"
    with pytest.raises(AssetError, match="nicht gefunden"):
        library.resolve("einhorn")


def test_keyword_matching_picks_the_dominant_asset(book_config):
    library = AssetLibrary(book_config.assets_dir, book_config.asset_aliases)
    matched = library.match_chapter(
        "Der Wolf kam aus dem Dickicht. Der Wolf war ein Untier, und der Wolf hatte Hunger.",
        meta={},
    )
    assert matched.hero.asset.key == "wolf"
    assert matched.hero.source == "auto"
    assert matched.hero.score == 4  # 3x Wolf + 1x Untier


def test_frontmatter_beats_keywords(book_config):
    library = AssetLibrary(book_config.assets_dir, book_config.asset_aliases)
    matched = library.match_chapter(
        "Der Wolf, der Wolf, der Wolf.", meta={"hero": "wald"}
    )
    assert matched.hero.asset.key == "wald"
    assert matched.hero.source == "frontmatter"


def test_threshold_and_budget_limit_automatic_illustrations(book_config):
    library = AssetLibrary(book_config.assets_dir, book_config.asset_aliases)
    text = "Wolf Wolf Wolf Wolf. Wald."
    assert library.match_chapter(text, {}, min_score=2).inline == []  # Wald nur 1x
    generous = library.match_chapter(text, {}, min_score=1, max_auto_inline=5)
    assert [m.asset.key for m in generous.inline] == ["wald"]
    assert library.match_chapter(text, {}, min_score=1, max_auto_inline=0).inline == []


def test_an_asset_is_never_used_twice_in_one_chapter(book_config):
    library = AssetLibrary(book_config.assets_dir, book_config.asset_aliases)
    matched = library.match_chapter(
        "Wolf Wolf Wolf", meta={"hero": "wolf", "images": ["wolf"]}, explicit_refs=["wolf"]
    )
    keys = [m.asset.key for m in matched.all]
    assert keys == ["wolf"]


def test_captions_come_from_configuration(book_config):
    library = AssetLibrary(
        book_config.assets_dir, book_config.asset_aliases, book_config.asset_captions
    )
    matched = library.match_chapter("Wolf Wolf", meta={})
    assert matched.hero.caption == "Der Wolf"
    ohne = AssetLibrary(book_config.assets_dir, book_config.asset_aliases)
    assert ohne.match_chapter("Wolf Wolf", meta={}).hero.caption == ""


def test_chapters_do_not_repeat_the_same_illustration(book_config):
    chapters = load_chapters(book_config)
    heroes = [c.assets.hero.asset.key for c in chapters]
    assert heroes == ["wald", "wolf"]
