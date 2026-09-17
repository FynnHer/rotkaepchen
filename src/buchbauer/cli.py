"""Kommandozeile des Buchbauers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reportlab.lib.units import mm

from .assets import AssetLibrary
from .builder import BookBuilder
from .chapters import load_chapters
from .config import ConfigError, load_config

__all__ = ["main"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="buchbauer",
        description="Baut aus Markdown-Kapiteln ein gesetztes PDF-Buch.",
    )
    parser.add_argument(
        "-c", "--config", default="book.toml", help="Konfigurationsdatei (Default: book.toml)"
    )
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="PDF erzeugen (Default)")
    build.add_argument("-o", "--output", help="Zielpfad, ueberschreibt book.output")
    build.add_argument(
        "--allow-color-violations",
        action="store_true",
        help="Verstoesse gegen die Drei-Farben-Regel nur melden, nicht fehlschlagen",
    )
    build.add_argument(
        "--no-report", action="store_true", help="keinen Farb-Report schreiben"
    )

    sub.add_parser("inspect", help="Kapitel-, Paletten- und Asset-Zuordnung anzeigen")
    return parser


def _inspect(config) -> int:
    library = AssetLibrary(
            config.assets_dir, config.asset_aliases, config.asset_captions
        )
    chapters = load_chapters(config, library)
    print(f"Konfiguration : {config.root}")
    print(f"Kapitel-Ordner: {config.chapters_dir}")
    print(f"Asset-Ordner  : {config.assets_dir}  ({len(library)} Bilder)")
    activities = config.activities
    if activities.enabled and activities.pages:
        print(
            f"Raetselseiten : {activities.directory}  "
            f"({len(activities.pages)} Seiten)"
        )
    if not len(library):
        print("     ! kein einziges Bild - das Buch entstuende ohne Illustrationen")
    print(f"Ausgabe       : {config.output}")
    print()
    for chapter in chapters:
        print(f"[{chapter.number}] {chapter.title}   ({chapter.source.name})")
        print(f"     Palette  : {chapter.palette.name} {list(chapter.palette.as_tuple())}")
        hero = chapter.assets.hero
        print(
            f"     Kapitelbild: {hero.asset.key} "
            f"(Quelle: {hero.source}, Treffer: {hero.score})"
            if hero
            else "     Kapitelbild: -"
        )
        for match in chapter.assets.inline:
            print(
                f"     Illustration: {match.asset.key} "
                f"(Quelle: {match.source}, Treffer: {match.score})"
            )
        for page in config.activities.after(chapter.number):
            print(f"     -> Raetselseite: {page.image}  {page.title}".rstrip())
        print()
    last = chapters[-1].number if chapters else 0
    for page in config.activities.beyond(last):
        print(f"     -> Raetselseite: {page.image}  {page.title}".rstrip())
    return 0


def _build(config, args) -> int:
    builder = BookBuilder(config)
    result = builder.build()

    print(f"PDF geschrieben: {result.output}  ({result.pages} Seiten)")
    for chapter in result.chapters:
        hero = chapter.assets.hero.asset.key if chapter.assets.hero else "-"
        extra = ", ".join(m.asset.key for m in chapter.assets.inline) or "-"
        print(
            f"  [{chapter.number}] {chapter.title}"
            f" | Palette {chapter.palette.name} | Bild {hero} | weitere {extra}"
        )

    for warning in result.warnings:
        print(f"  Warnung: {warning}", file=sys.stderr)

    if not args.no_report:
        report_path = result.output.with_name(f"{result.output.stem}-farbreport.json")
        result.recorder.write_report(report_path)
        print(f"Farb-Report: {report_path}")

    page = config.page
    print(
        f"Endformat {page.width / mm:.0f} x {page.height / mm:.0f} mm, "
        f"Anschnitt {page.bleed / mm:.1f} mm, "
        f"Schnittmarken: {'ja' if config.printing.crop_marks else 'nein'}"
    )
    total = sorted({c for p in config.colors.palettes.values() for c in p.as_tuple()})
    print(f"Farben im Buch: {len(total)} {total}")

    counts = [len(colors) for colors in result.recorder.pages.values()]
    print(
        f"Farben pro Seite: max {max(counts) if counts else 0}, "
        f"Grenze {config.colors.max_per_page}"
    )

    violations = result.violations
    if violations:
        print("\nVerstoesse gegen die Drei-Farben-Regel:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        if not args.allow_color_violations:
            return 1
    else:
        print("Drei-Farben-Regel eingehalten.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    command = args.command or "build"
    if command == "build":
        for name, default in (("output", None), ("allow_color_violations", False), ("no_report", False)):
            if not hasattr(args, name):
                setattr(args, name, default)

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Konfigurationsfehler: {error}", file=sys.stderr)
        return 2

    if command == "build" and args.output:
        config = type(config)(**{**config.__dict__, "output": Path(args.output).resolve()})

    try:
        if command == "inspect":
            return _inspect(config)
        return _build(config, args)
    except (FileNotFoundError, ConfigError, ValueError) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
