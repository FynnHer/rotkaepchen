from buchbauer.chapters import load_chapters, place_images
from buchbauer.markdown import Block, parse_markdown


def test_all_markdown_files_of_the_folder_are_read(book_config):
    chapters = load_chapters(book_config)
    assert [c.source.name for c in chapters] == ["01-erstes.md", "02-zweites.md"]
    assert [c.number for c in chapters] == [1, 2]


def test_order_from_frontmatter_beats_filename(book_dir):
    from buchbauer.config import load_config

    (book_dir / "chapters" / "01-erstes.md").write_text(
        "---\ntitle: Spaeter\norder: 9\n---\n\nText.\n", encoding="utf-8"
    )
    chapters = load_chapters(load_config(book_dir / "book.toml"))
    assert [c.title for c in chapters] == ["Zweites Kapitel", "Spaeter"]


def test_title_falls_back_to_heading_then_filename(book_dir):
    from buchbauer.config import load_config

    (book_dir / "chapters" / "01-erstes.md").write_text("# Aus der Ueberschrift\n\nText.\n", encoding="utf-8")
    (book_dir / "chapters" / "02-zweites.md").write_text("Nur Text.\n", encoding="utf-8")
    titles = [c.title for c in load_chapters(load_config(book_dir / "book.toml"))]
    assert titles == ["Aus der Ueberschrift", "Zweites"]


def test_level_one_heading_is_not_repeated_in_the_body(book_dir):
    from buchbauer.config import load_config

    (book_dir / "chapters" / "01-erstes.md").write_text(
        "---\norder: 1\n---\n\n# Titel\n\nText.\n", encoding="utf-8"
    )
    chapter = load_chapters(load_config(book_dir / "book.toml"))[0]
    assert chapter.title == "Titel"
    assert all(not (b.kind == "heading" and b.level == 1) for b in chapter.body)


def test_every_chapter_gets_a_palette(book_config):
    assert {c.palette.name for c in load_chapters(book_config)} == {"hell", "dunkel"}


def _assets(*keys):
    from buchbauer.assets import Asset, AssetMatch, ChapterAssets
    from pathlib import Path

    return ChapterAssets(
        inline=[AssetMatch(asset=Asset(key=k, path=Path(k)), source="auto") for k in keys]
    )


def test_images_replace_scene_breaks_first():
    blocks = [Block("paragraph", "a"), Block("break"), Block("paragraph", "b")]
    result = place_images(blocks, _assets("wolf"))
    assert [b.kind for b in result] == ["paragraph", "image", "paragraph"]
    assert result[1].src == "wolf"


def test_images_are_distributed_between_paragraphs():
    blocks = [Block("paragraph", str(i)) for i in range(6)]
    result = place_images(blocks, _assets("wolf", "wald"))
    assert [b.kind for b in result].count("image") == 2
    assert result[0].kind == "paragraph"      # nie vor dem ersten Absatz
    assert result[-1].kind == "paragraph"     # nie nach dem letzten


def test_explicit_markdown_images_keep_their_position(book_config):
    from buchbauer.assets import AssetLibrary

    doc = parse_markdown("Eins.\n\n![Der Wolf](wolf)\n\nZwei.\n")
    library = AssetLibrary(book_config.assets_dir, book_config.asset_aliases)
    matched = library.match_chapter("Eins. Zwei.", meta={}, explicit_refs=["wolf"])
    result = place_images(doc.blocks, matched)
    assert [b.kind for b in result] == ["paragraph", "image", "paragraph"]


def test_placement_without_assets_changes_nothing():
    from buchbauer.assets import ChapterAssets

    blocks = [Block("paragraph", "a"), Block("break")]
    assert place_images(blocks, ChapterAssets()) == blocks
