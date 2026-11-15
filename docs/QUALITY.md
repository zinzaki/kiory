# Quality review

Source artwork lives in `icons/`. Keep the 24 × 24 canvas, rounded ends and joins,
approximately 1.8–2 units of visual line weight, deliberate breathing room and `currentColor`.
Preserve existing names when refining a metaphor; consumers use them as an API.

## Checks

```sh
npm ci
python3 scripts/build.py --check
python3 scripts/build.py
npm test
python3 scripts/qa.py
```

The build needs Python 3.11+. Rendering needs `rsvg-convert` (Arch: `librsvg`, Debian/Ubuntu:
`librsvg2-bin`) and Pillow. Install Pillow in a Python environment if it is not already available.
`npm ci` installs the JS test dependencies; consumers do not need them.

`qa-output/index.html` contains the entire pack at 16, 20, 24 and 32 px on light and dark
backgrounds. Use a desktop at 100% zoom to inspect native sizes. The accompanying JSON reports
visible bounds, ink area and exact raster duplicates. A padded render exposes geometry outside
the canvas. Blank or clipped icons fail; duplicates are review candidates, since aliases can be
intentional. The report does not score aesthetics or prove that a metaphor is understood.

To review just a family of changes:

```sh
python3 scripts/qa.py --names light-point light-spot light-sun join-inner join-left join-outer
```

For catalog regression checks, install Chromium once with `npx playwright install chromium`.
Serve the repository in another terminal, then run the checks:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
# In a second terminal:
npm run test:browser
```

`KIORY_URL` selects another server. `CHROMIUM_PATH` selects an already installed browser.
`KIORY_QA_OUTPUT` selects the screenshot/download directory (default: `qa-output`).
Pull requests build the actual source before running the tests, render the whole pack and upload
`quality-review` with the reports, sheets and screenshots. Pages is only deployed from main.

## Visual acceptance

- Inspect the silhouette without its name. Look at neighbouring concepts together: input/output,
  previous/next, on/off, inner/left/outer joins and point/spot/sun lighting.
- At 16 px, internal gaps must remain open; extra dots and tiny badges must carry real information.
  Dense icons such as QR, fingerprints, CPUs and face identification work better at 20–24 px.
- Check actual 16/20/24/32 px rasterisations, not just a magnified vector. Inspect both foreground
  polarities. Compare against the existing search, folder and settings icons for optical weight.
- Test in a toolbar next to text, a file list, an icon-only button with an accessible name, and a
  compact status bar. The button's hit area can be larger than its glyph.
- Check SVG, CSS mask, sprite and React consumers after changing exports. Decorative React icons
  are hidden from assistive technology; a `title` supplies an image label. For icon-only controls,
  put the action label on the button as well.
- Verify keyboard, touch, reduced motion, offline use and downloads in the catalog. Text entry,
  selection and dialog focus should not interfere with one another.

Sizing and interaction references: [Carbon icon guidelines](https://www.carbondesignsystem.com/building-blocks/foundations/icons/guidelines)
and [WAI-ARIA dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
These inform the checks; Kiory keeps its own artwork and visual language.

## Current refinement pass

| Icons | Change |
| --- | --- |
| `light-point`, `light-spot`, `light-sun` | distinct point emitter, cone and sun; removed the key-like sun silhouette |
| `join-inner`, `join-left`, `join-outer` | consistent circles and explicit selected regions; outer includes the centre |
| `chat-mute` | message plus muted speaker, replacing an ambiguous line badge |
| `qr-code` | three finder squares and a simpler data corner with separated modules |
| `save`, `save-as` | shared disk with a separate pencil for saving a named copy |
| `accessibility`, `keyboard-shortcuts` | assistive settings and shortcut discovery |

The initial 725-icon contact sheets were inspected; the 12 changed/new icons received a focused
size review. This is not a claim that all other metaphors have been individually validated in
applications or with users. Continue with the densely badged AI and developer families, and check
whether separate small-size drawings are warranted before promising 16 px for every icon.
