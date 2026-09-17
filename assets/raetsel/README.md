# Rätselseiten

Hier liegen die **Mitmach-Seiten** des Buches — je eine ganze, randabfallende
Seite, die Kinder selbst bearbeiten. Sie sind keine Illustrationen: sie werden
keinem Kapitel automatisch zugeordnet und tauchen in `[assets.aliases]` nicht
auf. Deshalb ein eigener Ordner.

| Datei | Seite |
| --- | --- |
| `labyrinth_raetsel.png` | „Rotkäppchens Weg“ — Labyrinth vom Start zum Haus der Großmutter |
| `wimmelbild_raetsel.png` | „Wimmelbild“ — zehn Dinge im Wald suchen |
| `zaehl_raetsel.png` | „Zähl mit!“ — acht Motive im Bild zählen |

## Wo sie im Buch stehen

Alles steht in [`book.toml`](../../book.toml). `after` ist die Nummer des
Kapitels, **hinter** dem die Seite erscheint (`0` stellt sie vor das erste
Kapitel, eine Nummer hinter dem letzten Kapitel schließt das Buch ab):

```toml
[activities]
enabled = true
dir     = "assets/raetsel"
tritone = false   # von der Drei-Farben-Regel ausgenommen
in_toc  = true

[[activities.pages]]
image = "labyrinth_raetsel"
after = 4
title = "Rätselseite: Rotkäppchens Weg"
```

Eine neue Rätselseite braucht also zwei Handgriffe: die Bilddatei in diesen
Ordner legen und einen `[[activities.pages]]`-Eintrag ergänzen.

## Anforderungen an die Dateien

Die Seite bringt Überschrift, Aufgabenstellung und Lösung **im Bild** mit —
das Buch setzt nichts darüber, weder Bildunterschrift noch Seitenzahl. Das
Bild wird formatfüllend beschnitten; wichtige Elemente gehören deshalb nicht
an den äußersten Rand.

- Hochformat im Seitenverhältnis des Buches (A5, 1 : 1,414)
- mindestens **300 dpi** im Endformat inklusive Anschnitt, sonst warnt der Bau
  (bei A5 mit 3 mm Anschnitt rund 1830 × 2560 px)
