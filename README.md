# Rotkäppchen — Buchbauer

Ein Werkzeug, das aus einzelnen Markdown-Kapiteln ein **druckfertiges,
dreifarbiges PDF-Buch** setzt. Jedes Kapitel ist eine Datei, jedes Bild ein
Asset — Layout, Typografie und Farben stehen an genau einer Stelle:
[`book.toml`](book.toml).

```
chapters/*.md      ──┐
beispiele/bilder/* ──┤
assets/raetsel/*   ──┼──►  buchbauer  ──►  build/rotkaeppchen.pdf
book.toml          ──┘                      + build/rotkaeppchen-farbreport.json
```

## Schnellstart

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/python tools/make_placeholder_assets.py   # Platzhalter-Illustrationen
.venv/bin/buchbauer build                           # PDF bauen
.venv/bin/buchbauer inspect                         # Zuordnung ansehen, nichts bauen
.venv/bin/python -m pytest                          # Tests
```

`build` endet mit Exit-Code 1, wenn eine Seite die Farbregel verletzt.
`--allow-color-violations` meldet die Verstöße, ohne zu scheitern.

## Wie ein Kapitel aussieht

```markdown
---
title: Die fünf Blumen
subtitle: Von einer roten, gelben, blauen, weißen und lila Blume
order: 5
palette: hearth
hero: rotkaeppchen   # optional — sonst sucht der Builder das Bild selbst
---

Neben dem Weg wuchsen bunte **Blumen** im Gras.
Rotkäppchen stellte den Korb ab und pflückte fünf davon.

> Eine rote, eine gelbe, eine blaue, eine weiße und eine lila Blume.

---

![Der Wolf im Dickicht](wolf)
```

Unterstützt werden Überschriften, Absätze, Zitate, Listen, Bilder und `---`
als Szenentrenner. Gerade Anführungszeichen werden zu deutschen
Gänsefüßchen, `--` zu Halbgeviertstrichen. **Kein Kapitel enthält Layout.**

## Wie Bilder ihr Kapitel finden

Drei Stufen, von der stärksten zur schwächsten Quelle — eine spätere
überstimmt eine frühere nie:

1. **Frontmatter** — `hero: wolf`, `images: [wald, jaeger]`
2. **Markdown** — `![Bildunterschrift](wolf)` bleibt an seiner Stelle
3. **Automatik** — die Stichworte aus `[assets.aliases]` werden im Kapitel
   gezählt. Treffer im **Kapiteltitel** wiegen `title_weight`-fach, bereits
   verwendete Bilder werden abgewertet, damit sich die Bildfolge abwechselt.

`buchbauer inspect` zeigt, was der Builder entschieden hat — samt Trefferzahl:

```
[14] Die Rettung   (14-die-rettung.md)
     Kapitelbild: wolf (Quelle: auto, Treffer: 3)
     Illustration: jaeger (Quelle: auto, Treffer: 2)
```

## Mitmach-Seiten

Drei Rätselseiten aus [`assets/raetsel/`](assets/raetsel) liegen zwischen den
Kapiteln — ein Labyrinth, ein Wimmelbild und ein Zählbild. Sie sind **keine
Illustrationen**: eigener Ordner, keine Stichwort-Zuordnung, keine
Bildunterschrift. Jede füllt randabfallend eine ganze Seite und bringt
Überschrift, Aufgabe und Lösung im Bild mit; Kolumnentitel und Seitenzahl
bleiben deshalb weg.

Platz und Reihenfolge stehen in `book.toml`. `after` ist die Nummer des
Kapitels, **hinter** dem die Seite erscheint (`0` = vor dem ersten Kapitel,
eine Nummer hinter dem letzten Kapitel schließt das Buch ab):

```toml
[activities]
enabled = true
dir     = "assets/raetsel"
tritone = false   # von der Drei-Farben-Regel ausgenommen
in_toc  = true    # eigene Zeile im Inhaltsverzeichnis

[[activities.pages]]
image = "labyrinth_raetsel"
after = 4
title = "Rätselseite: Rotkäppchens Weg"
```

| Seite | steht hinter | passt dort, weil |
| --- | --- | --- |
| Rotkäppchens Weg (Labyrinth) | 4 — Der helle Wald | der Weg zur Großmutter liegt vor ihr |
| Wimmelbild | 9 — Der Streich | Wald, Bach und Haus, kurz vor der Ankunft |
| Zähl mit! | 15 — Alle sind wieder froh | zum Nachzählen, wenn alles überstanden ist |

`buchbauer inspect` zeigt die Seiten an ihrem Platz in der Kapitelfolge.
Die Bilder bringen ihre eigene Bildwelt mit und werden nicht auf die
Palette reduziert — gefärbt wird am Satz nichts, die Drei-Farben-Regel
gilt auf diesen Seiten weiterhin für Papier und Schnittmarken.

## Das Farbsystem

Eine Palette hat **genau drei Rollen** — `paper`, `ink`, `accent`. Mehr sieht
die Konfiguration nicht vor, deshalb kann eine Seite die Regel gar nicht erst
verletzen. Zusätzlich gilt:

| Regel | Schlüssel | Wirkung |
| --- | --- | --- |
| Farben je Seite | `colors.max_per_page` | nach dem Bau gemessen |
| Farben im ganzen Buch | `colors.max_total` | beim Laden geprüft |

Die Prüfung ist keine Konvention, sondern eine Messung: ein eigenes
Canvas protokolliert **jede** gesetzte Füll- und Linienfarbe pro Seite.
Das Ergebnis landet in `build/rotkaeppchen-farbreport.json`:

```json
{ "page": 5, "palette": "buch", "colors": ["#2a3b2e", "#a81e2d", "#f4ecdc"], "count": 3 }
```

Illustrationen bringen keine vierte Farbe mit: solange `images.tritone`
aktiv ist, wird jedes Bild vor dem Einbetten auf die drei Palettenfarben
reduziert (Floyd-Steinberg-Rasterung erhält dabei die Mitteltöne).

## Druckvorstufe

| Schlüssel | Bedeutung |
| --- | --- |
| `print.bleed_mm` | Anschnitt; Papierton und Titelbild laufen hinein |
| `print.crop_marks` | Schnittmarken an den Ecken des Endformats |
| `print.color_space` | `"cmyk"` für den Druck, `"rgb"` für den Bildschirm |
| `print.min_image_dpi` | darunter warnt der Bau (Standard 300 dpi) |

Die PDF-Seite ist damit **Endformat + 2 × Anschnitt** groß. Die
CMYK-Umrechnung arbeitet ohne ICC-Profil — für ein Buch aus drei
definierten Farben ist das ausreichend, für Farbfotos wäre es das nicht.

## Zentrale Layout-Parameter

Alles in `book.toml`, mit Kommentar an jedem Schlüssel:

- `[page]` — Format (`A4`/`A5`/… oder `[breite_mm, höhe_mm]`) und Ränder
- `[typography]` — Schriften, Grade, Zeilenabstand, Einzug, Versalie
- `[images]` — Bildbreiten (Werte über `1.0` laufen in die Ränder), Höhen,
  Rasterung, Schwellwert und Obergrenze der Automatik
- `[colors]`, `[print]`, `[cover]`, `[toc]`, `[assets]`

## Aufbau

| Datei | Aufgabe |
| --- | --- |
| `src/buchbauer/config.py` | `book.toml` laden, prüfen, mit Defaults füllen |
| `src/buchbauer/markdown.py` | Frontmatter und Blöcke lesen |
| `src/buchbauer/assets.py` | Bilder den Kapiteln zuordnen |
| `src/buchbauer/chapters.py` | Kapitel bauen, Illustrationen verteilen |
| `src/buchbauer/images.py` | Reduktion auf die Palette, CMYK, Cache |
| `src/buchbauer/colors.py` | Farbprotokoll und Regelprüfung |
| `src/buchbauer/builder.py` | Seitenvorlagen, Satz, PDF |
| `src/buchbauer/cli.py` | `buchbauer build` / `buchbauer inspect` |

## Stand

Issue #1 (Sprint 1) ist erfüllt: der Builder liest alle Kapitel eines
Ordners, ordnet die Assets automatisch zu, erzeugt **eine** PDF-Datei, hält
die Drei-Farben-Regel nachweisbar ein und hält alle Layout-Parameter
zentral. Aus den 15 Kapiteln in `chapters/` und den drei Rätselseiten in
`assets/raetsel/` entsteht ein Buch mit 36 Seiten; 69 Tests decken die
Bausteine ab.

Aus Issue #4 sind Anschnitt, Schnittmarken, CMYK und die 300-dpi-Prüfung
vorhanden; Rechtschreibprüfung und Probedruck stehen aus.

Die Illustrationen unter `beispiele/bilder/` sind **Platzhalter** aus
`tools/make_placeholder_assets.py`. Die echten Bilder aus Issue #6 gehören
nach [`assets/images/`](assets/images) — dort steht, welche Dateinamen und
welche Auflösung erwartet werden. Danach zeigt `book.assets_dir` in
`book.toml` dorthin; das ist eine Zeile, sonst ändert sich nichts.

Issue #6 nimmt Bilder ausdrücklich von der Drei-Farben-Regel aus — dafür
genügt `images.tritone = false`; für die Rätselseiten ist das bereits der
Standard (`activities.tritone = false`).

Aus Issue #5 sind die spielerischen Aktivitäten eingebaut: drei
Mitmach-Seiten, verteilt über die Geschichte. Ihre Vorlagen liegen bei
1055 × 1491 px und damit bei rund 174 dpi im Endformat — für den Druck
meldet der Bau das als Warnung, die Dateien müssen vor dem Probedruck in
höherer Auflösung nachgeliefert werden.
