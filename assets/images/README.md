# Bild-Assets

Hier liegen die **echten** Illustrationen des Buches. Vorhanden sind bisher
das Umschlagbild und das Bild der Gebrüder Grimm; alles Übrige kommt noch aus
den Platzhaltern in [`beispiele/bilder/`](../../beispiele/bilder).

## Beide Ordner zugleich

[`book.toml`](../../book.toml) nennt beide, der erste gewinnt:

```toml
[book]
assets_dir = ["assets/images", "beispiele/bilder"]
```

Ein echtes Bild ersetzt seinen Platzhalter also allein dadurch, dass es unter
demselben Dateinamen hier liegt — `wolf.png` hier schlägt `wolf.png` dort.

## Dateinamen sind die Schnittstelle

Der Dateiname (ohne Endung) ist der **Asset-Schlüssel**. Über ihn laufen
die Stichwort-Zuordnung in `[assets.aliases]`, die Bildunterschriften in
`[assets.captions]` und die `hero:`-Angabe im Frontmatter eines Kapitels.
Umlaute und ein Ordnungspräfix sind erlaubt — `03-Großmutter.png` wird zum
Schlüssel `grossmutter`.

Erwartet werden derzeit:

| Datei | Verwendung |
| --- | --- |
| `rotkaepchen_cover.png` | Umschlag, randabfallend über die ganze Seite (vorhanden) |
| `gebruedergrim_infobild.png` | Seite über die Verfasser (vorhanden) |
| `rotkaeppchen.png` | Kapitelbild und Illustration |
| `wolf.png` | Kapitelbild und Illustration |
| `grossmutter.png` | Kapitelbild und Illustration |
| `jaeger.png` | Illustration |
| `wald.png` | Illustration |

## Auflösung

Mindestens **300 dpi** im Endformat, sonst warnt der Bau. Für ein
randabfallendes A5-Titelbild sind das rund 1860 × 2640 px.
