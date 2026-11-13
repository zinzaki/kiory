# Changelog

## 8.2.0 — 2026-11-14

725 icons: one removed, 35 redrawn or replaced.

- `check`, `check-double` and the double chevrons `chevrons-left`, `-right`, `-up`, `-down` were
  close to twice the weight of the rest of the pack, and the double chevrons carried stray dots.
  They are rebuilt from the approved single chevron and the check at the weight of the arrows.
  `unfold` and `unfold-h` are brought up to the same weight.
- Folder badges sit at the optical centre with equal gaps above and below: `folder-up`,
  `folder-plus`, `folder-minus`, `folder-lock`, `folder-ai`, `folder-symlink`. `folder-check` is
  rebuilt on the same base folder as the rest of the family.
- Clearer metaphors: `mount` (a drive being attached instead of an eject symbol), `scratchpad`
  (a floating terminal instead of a floppy disk), `pin-window`, `permission-read`,
  `permission-write`, `dotfiles`, `orthographic`, `drawing-tablet`, `port-in`, `port-out`,
  `proxy`, `tmux-split`, `json-schema`, `chat-archive`, `formatter`, `callback-query`.
- `workspace-next`, `-prev`, `-plus` and `-minus` share the 2 × 2 grid of `workspace`.
- Removed `pkg-aur`: the pack is built for the YHK ecosystem.
- Everything is in English now: section names (Path, Gesture, Frame, Archive, Mechanism, Lock,
  Canvas, Motion, Script, Mind, Workbench, Schema, Voice, Sign, Sound, World), the catalog,
  the README and the build messages.
- The repository is a showcase only: the development archive is gone from git, and the README
  cover is the only generated image.

## 8.1.0 — 2026-11-13

The same 726 icons, regrouped: 16 sections instead of 30 sets.

- Overlapping sets merged; every section has an atelier name and a plain note on what is inside.
  The catalog searches the notes too, so "ryoku", "btrfs" or "sqlite" find their icons.
- Icon names did not change. `family` in `dist/kiory.json` and the folders in `icons/` did.
- The site was rebuilt: the first screen is a field of every icon with a lens under the cursor and
  search; Craft shows one icon up close on the 24 × 24 grid; In use is an app window made of
  Kiory in two themes. Typefaces: Geist and Geist Mono.
- Motion: a scan across the grid swaps the specimen, the photo stage has depth under the cursor,
  a light follows the cursor over the catalog, an ink marks the current section, section titles
  rise as you scroll. Everything is off with reduced motion.
- A README cover in dark and light.

## 8.0.0 — 2026-11-13

726 icons in 30 sets (up from 352 in 13).

- 374 new icons: desktop and tiling, OS slots and the Linux kernel, Btrfs and drives, security,
  design tokens, animation, 3D and shaders, typography, node graphs, AI agents, Git and CI,
  debugging, DevOps and networking, databases, bots, sound and synthesis, weather and widgets.
- About eighty earlier icons refined in weight and proportion: `bookmark`, `attachment`,
  `battery`, `columns`, `kanban`, `wi-fi`, `search` and more.
- Back in the pack: `usb`, `barcode`, `tiling`, `panel-top`, `flip-h`, `flip-v`, `distribute-h`,
  `distribute-v`.
- Catalog: click to copy as SVG, JSX, CSS or name; sets with copy and ZIP; search from anywhere;
  an icon card with PNG, data URI and a link; the Install section.
- The `dist/` package: SVGs, sprite, CSS classes, a typed JS module, a React component and a JSON
  manifest, installable from GitHub.

## 7.0.0 — 2026-11-10

First release: 352 icons in 13 sets.
