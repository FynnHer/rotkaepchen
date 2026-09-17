# Bild-Assets

Hier liegen die **echten** Illustrationen des Buches. Der Ordner ist noch
leer — bis die Bilder aus Issue #6 vorliegen, baut das Buch mit den
Platzhaltern aus [`beispiele/bilder/`](../../beispiele/bilder).

## Umstellen

Eine Zeile in [`book.toml`](../../book.toml):

```toml
[book]
assets_dir = "assets/images"
```

## Dateinamen sind die Schnittstelle

Der Dateiname (ohne Endung) ist der **Asset-Schlüssel**. Über ihn laufen
die Stichwort-Zuordnung in `[assets.aliases]`, die Bildunterschriften in
`[assets.captions]` und die `hero:`-Angabe im Frontmatter eines Kapitels.
Umlaute und ein Ordnungspräfix sind erlaubt — `03-Großmutter.png` wird zum
Schlüssel `grossmutter`.

Erwartet werden derzeit:

| Datei | Verwendung |
| --- | --- |
| `titelbild.png` | Umschlag, randabfallend über die ganze Seite (Hochformat) |
| `rotkaeppchen.png` | Kapitelbild und Illustration |
| `wolf.png` | Kapitelbild und Illustration |
| `grossmutter.png` | Kapitelbild und Illustration |
| `jaeger.png` | Illustration |
| `wald.png` | Illustration |

## Auflösung

Mindestens **300 dpi** im Endformat, sonst warnt der Bau. Für ein
randabfallendes A5-Titelbild sind das rund 1860 × 2640 px.
