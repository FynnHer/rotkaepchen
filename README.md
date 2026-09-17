# Rotkäppchen — Buchbauer

Ein Werkzeug, das aus einzelnen Markdown-Kapiteln ein **druckfertiges,
seitenweise dreifarbiges PDF-Buch** setzt — mit drei Papiertönen, die mit dem
Ort der Handlung wechseln. Jedes Kapitel ist eine Datei, jedes Bild ein
Asset — Layout, Typografie und Farben stehen an genau einer Stelle:
[`book.toml`](book.toml).

```
chapters/*.md      ──┐
seiten/*.md        ──┤
assets/images/*    ──┤
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

## Umschlag und Autorenseite

Der Umschlag ist ein fertig gestaltetes Bild: Titel und Verfasser stehen
darin, deshalb setzt das Buch nichts darüber und reduziert es auch nicht auf
die Palette.

```toml
[book]
cover_image = "rotkaepchen_cover"

[cover]
full_page_image = true
typeset_band    = false   # kein Titelfeld - der Umschlag bringt seine Typografie mit
tritone         = false   # in seinen eigenen Farben
```

Vor dem ersten Kapitel steht die Seite über die Verfasser. Ihr Text liegt in
[`seiten/ueber-die-gebrueder-grimm.md`](seiten/ueber-die-gebrueder-grimm.md) —
eine ganz normale Kapitel-Datei mit Frontmatter, nur ohne Nummer: im
Inhaltsverzeichnis steht sie, eine Zeile „Erstes Kapitel“ bekommt sie nicht.

```toml
[about]
enabled = true
file    = "seiten/ueber-die-gebrueder-grimm.md"
after   = 0      # 0 = vor dem ersten Kapitel
image_height_ratio = 0.26        # das Bild im Kopf der Seite
body_image_height_ratio = 0.30   # die Bilder im Fliesstext
```

Hinter dem Text der Seite steht die Werbung für die anderen Bände: zwei
Umschläge als gewöhnliche Markdown-Bilder. `body_image_height_ratio` hält
sie klein genug, dass beide zusammen auf eine Seite passen.

```markdown
## Mehr von den Brüdern Grimm

![Schneewittchen](werbung_schneewittchen)

![Der Wolf und die sieben Geißlein](werbung_wolf)
```

## Mehrere Asset-Ordner

`book.assets_dir` nimmt auch eine Liste. Der **erste Ordner gewinnt**, die
folgenden steuern bei, was er nicht hat — so ersetzen die echten
Illustrationen die Platzhalter Datei für Datei:

```toml
assets_dir = ["assets/images", "beispiele/bilder"]
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
verletzen. Mehrere Paletten dürfen sich unterscheiden — die Drei-Farben-Regel
gilt je Seite, nicht je Buch (siehe [Drei
Seitenhintergründe](#drei-seitenhintergründe)). Zusätzlich gilt:

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

Die Messung zählt gesetzte Farben, keine Bildpixel. Die Illustrationen sind
deshalb von der Regel ausgenommen (`images.tritone = false`) und behalten
ihre eigenen Farben — wie der Umschlag (`cover.tritone`) und die
Rätselseiten (`activities.tritone`). Wer sie doch auf die drei
Palettenfarben reduzieren will, setzt `images.tritone = true`; die
Floyd-Steinberg-Rasterung (`images.dither`) erhält dabei die Mitteltöne.

## Drei Seitenhintergründe

Der Papierton wechselt mit dem Ort der Handlung. Es gibt genau **drei**
Hintergründe; `ink` und `accent` bleiben in allen gleich, sodass eine Seite
nach wie vor nur drei Farben trägt — im ganzen Buch sind es fünf
(`colors.max_total = 5`).

| Palette | `paper` | steht für | Kapitel |
| --- | --- | --- | --- |
| `hearth` | `#F4ECDC` warmes Pergament | Dorf und Zuhause | 1–3, 15 |
| `wald` | `#E4EFD3` helles Blattgrün | der Weg durch den Wald | 4–7 |
| `daemmer` | `#D9E1EA` kühles Dämmerblau | das Haus der Großmutter | 8–14 |

Die Geschichte läuft damit von warm über grün nach kühl und am Schluss
zurück ins Warme: Kapitel 15 steht wieder auf dem Pergamentton des Anfangs.
Alle drei Töne halten gegen `ink` mindestens ein Kontrastverhältnis von 9:1.

Welches Kapitel welche Palette bekommt, steht in seinem Frontmatter —
`palette: wald` — wie schon `hero:`. Ohne Eintrag gilt `colors.rotate`,
sonst `colors.default_palette`. Die Autorenseite und das Inhaltsverzeichnis
stehen auf `hearth`, die Rätselseiten übernehmen die Palette des Kapitels,
hinter dem sie liegen.

Der Hintergrund färbt auch die Bilder: jede Illustration wird auf die
Palette **ihres** Kapitels reduziert, nimmt den Papierton also auf. Ein
Bild, das in zwei Kapiteln mit verschiedenen Paletten steht, wird zweimal
aufbereitet und getrennt zwischengespeichert.

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
die Drei-Farben-Regel je Seite nachweisbar ein und hält alle Layout-Parameter
zentral. Aus den 15 Kapiteln in `chapters/`, der Autorenseite in `seiten/` und den
drei Rätselseiten in `assets/raetsel/` entsteht ein Buch mit 37 Seiten.

Aus Issue #4 sind Anschnitt, Schnittmarken, CMYK und die 300-dpi-Prüfung
vorhanden; Rechtschreibprüfung und Probedruck stehen aus.

In [`assets/images/`](assets/images) liegen das Umschlagbild, das Bild der
Gebrüder Grimm, die beiden Werbe-Umschläge und **je ein Bild pro Kapitel**
(`Kapitel 1.jpeg` … `Kapitel 15.jpeg`). Jedes Kapitel benennt seines im
Frontmatter (`hero: Kapitel 5`); die Stichwort-Automatik ist damit
arbeitslos und `images.max_auto_illustrations = 0` schaltet sie ab. Die
Platzhalter aus `tools/make_placeholder_assets.py` unter `beispiele/bilder/`
stehen weiterhin in `book.assets_dir`, kommen aber nicht mehr ins Buch.

Die Kapitelbilder liegen bei rund 240 px Kantenlänge und damit bei 59–80 dpi
im Endformat — der Bau warnt für jedes einzelne. Für den Druck brauchen sie
Vorlagen in 300 dpi.

Issue #6 nimmt Bilder ausdrücklich von der Drei-Farben-Regel aus: das ist
mit `images.tritone = false` umgesetzt, für die Rätselseiten war es schon
vorher der Standard (`activities.tritone = false`).

Aus Issue #5 sind die spielerischen Aktivitäten eingebaut: drei
Mitmach-Seiten, verteilt über die Geschichte. Ihre Vorlagen liegen bei
1055 × 1491 px und damit bei rund 174 dpi im Endformat — für den Druck
meldet der Bau das als Warnung, die Dateien müssen vor dem Probedruck in
höherer Auflösung nachgeliefert werden.
