from buchbauer.markdown import inline_to_markup, parse_markdown


def test_frontmatter_is_separated_from_body():
    doc = parse_markdown("---\ntitle: Der Wolf\norder: 2\nhero: wolf\n---\n\nText.\n")
    assert doc.meta == {"title": "Der Wolf", "order": 2, "hero": "wolf"}
    assert [b.kind for b in doc.blocks] == ["paragraph"]


def test_frontmatter_lists_inline_and_dashed():
    inline = parse_markdown("---\nimages: [wolf, wald]\n---\n\nX\n")
    dashed = parse_markdown("---\nimages:\n  - wolf\n  - wald\n---\n\nX\n")
    assert inline.meta["images"] == ["wolf", "wald"]
    assert dashed.meta["images"] == ["wolf", "wald"]


def test_block_kinds():
    doc = parse_markdown(
        "# Titel\n\n## Abschnitt\n\nEin Absatz.\n\n> Ein Zitat.\n\n"
        "- eins\n- zwei\n\n![Ein Wolf](wolf)\n\n---\n\nEnde.\n"
    )
    assert [b.kind for b in doc.blocks] == [
        "heading", "heading", "paragraph", "quote", "list", "image", "break", "paragraph"
    ]
    assert doc.blocks[4].items == ["eins", "zwei"]
    assert (doc.blocks[5].src, doc.blocks[5].alt) == ("wolf", "Ein Wolf")


def test_paragraph_lines_are_joined():
    doc = parse_markdown("Erste Zeile\nzweite Zeile.\n\nNeuer Absatz.\n")
    assert doc.blocks[0].text == "Erste Zeile zweite Zeile."
    assert len(doc.blocks) == 2


def test_inline_emphasis_becomes_reportlab_markup():
    assert inline_to_markup("Der **Wolf** und der *Wald*") == "Der <b>Wolf</b> und der <i>Wald</i>"
    assert inline_to_markup("ein _Wort_") == "ein <i>Wort</i>"
    assert "5 * 3" in inline_to_markup("5 * 3")          # kein falsches Kursiv


def test_xml_special_characters_are_escaped():
    assert inline_to_markup("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_german_quotation_marks():
    assert inline_to_markup('"Guten Tag", sprach er.') == "„Guten Tag“, sprach er."
    assert inline_to_markup('Er sagte: "Komm."') == "Er sagte: „Komm.“"


def test_plain_text_drops_markup():
    doc = parse_markdown("Der **Wolf** im *Wald*.\n\n- ein `Korb`\n")
    assert doc.plain_text == "Der Wolf im Wald.\nein Korb"
