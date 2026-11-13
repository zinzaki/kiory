# Adding or replacing an icon

Everything is built for you. The only folder you edit by hand is `icons/`.

```
icons/
  navigation/
    family.json        section title, note and icon order
    search.svg         the icon
    search.json        passport, optional
```

## A new icon

1. Draw it on a 24 × 24 canvas, convert strokes to outlines (Outline stroke) and flatten.
2. Export the SVG into the section folder: `icons/<section>/<name>.svg`.
   Names are lowercase kebab-case: `arrow-left`, `ai-spark`.
3. Push to `main`. GitHub Actions normalizes the file (colour becomes `currentColor`, extra
   attributes go), rebuilds `dist/`, the catalog and the README cover, and publishes the site.

Locally it is the same: `python3 scripts/build.py` (Python 3.11+, plus `rsvg-convert` for the
cover). To check without writing anything, run `python3 scripts/build.py --check`.

If something is wrong with a file, the build says exactly what: "has a stroke; convert it to an
outline", "needs a 24 × 24 canvas" and so on.

## Replacing an icon

Put the new file over the old one with the same name. The catalog marks it **UPD**, new icons get
**NEW**; the marks stay until the next release.

## Passport

An optional `<name>.json` next to the icon lists extra words the catalog search should match:

```json
{ "tags": ["magnifier", "find", "zoom"] }
```

## Sections and order

`family.json` in the section folder:

```json
{ "title": "Path", "note": "Navigation and arrows", "order": ["home", "search", "back"] }
```

The title is one atelier word; `note` says in plain words what is inside. The catalog searches
both. Icons missing from `order` go to the end in alphabetical order. A new section is a new
folder; `kiory.json` sets the order of sections on the page.

## Release

Bump `version` and `released` in `kiory.json` and add an entry to `CHANGELOG.md`. The NEW and UPD
marks reset with it.
