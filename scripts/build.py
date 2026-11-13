#!/usr/bin/env python3
"""Kiory build.

    python3 scripts/build.py            # normalize the icons and build everything
    python3 scripts/build.py --check    # check only, writes nothing

The source of truth is the `icons/` folder:

    icons/<section>/family.json         {"title": "Path", "note": "Navigation and arrows", "order": [...]}
    icons/<section>/<name>.svg          the icon itself (a Figma export works)
    icons/<section>/<name>.json         optional passport: {"tags": ["magnifier", "find"]}

Drop in or replace a file and run the build (or just push: GitHub Actions builds it).
The build normalizes the SVGs, marks new and updated icons, and regenerates dist/,
the index.html catalog and the README cover. Needs Python 3.11+; the cover is rendered
with `rsvg-convert` (librsvg).
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "icons"
DIST = ROOT / "dist"
NS = "{http://www.w3.org/2000/svg}"
NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
CHECK = "--check" in sys.argv
TODAY = dt.date.today().isoformat()

errors: list[str] = []
notes: list[str] = []


# ── reading and normalization ──────────────────────────────────────────────────────

def body_of(paths: list[tuple[str, str]]) -> str:
    return "".join(f'<path fill="currentColor" fill-rule="{r}" d="{d}"/>' for r, d in paths)


def read_icon(p: Path) -> tuple[str, str] | None:
    """(body built from paths, canonical file text), or None if the icon cannot be parsed."""
    rel = p.relative_to(ROOT)
    try:
        root = ET.fromstring(p.read_text())
    except ET.ParseError as e:
        errors.append(f"{rel}: broken XML ({e})")
        return None
    vb = root.get("viewBox")
    if vb is None and root.get("width") in ("24", "24px") and root.get("height") in ("24", "24px"):
        vb = "0 0 24 24"
    try:
        ok = vb is not None and [float(v) for v in vb.replace(",", " ").split()] == [0, 0, 24, 24]
    except ValueError:
        ok = False
    if not ok:
        errors.append(f"{rel}: needs a 24 × 24 canvas (viewBox \"0 0 24 24\"), got \"{vb}\"")
        return None
    paths: list[tuple[str, str]] = []

    def walk(el: ET.Element, rule: str | None) -> None:
        tag = el.tag.replace(NS, "")
        if tag in ("title", "desc", "metadata"):
            return
        if tag == "defs":
            if len(el):
                errors.append(f"{rel}: <defs> with content (masks, gradients) is not supported")
            return
        if tag not in ("svg", "g", "path"):
            errors.append(f"{rel}: <{tag}> is not supported; convert shapes to outlines (Outline stroke, Flatten)")
            return
        if el.get("transform"):
            errors.append(f"{rel}: transform on <{tag}>; flatten before exporting")
        if el.get("stroke") not in (None, "none"):
            errors.append(f"{rel}: has a stroke; convert it to an outline (Outline stroke)")
        if el.get("clip-path") or el.get("mask") or el.get("opacity") or el.get("fill-opacity"):
            errors.append(f"{rel}: masks and opacity are not supported")
        rule = el.get("fill-rule") or el.get("clip-rule") or rule
        if tag == "path" and el.get("fill") != "none":
            d = " ".join((el.get("d") or "").split())
            if d:
                paths.append((rule or "nonzero", d))
        for ch in el:
            walk(ch, rule)

    walk(root, None)
    if not paths:
        errors.append(f"{rel}: contains no filled outline")
        return None
    body = body_of(paths)
    return body, f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">{body}</svg>\n'


def load() -> tuple[dict, list[dict], dict[str, dict]]:
    cfg = json.loads((ROOT / "kiory.json").read_text())
    for p in ICONS.glob("*.svg"):
        errors.append(f"{p.relative_to(ROOT)}: icon outside a section; move it to icons/<section>/")
    dirs = {d.name: d for d in ICONS.iterdir() if d.is_dir()}
    order = [f for f in cfg["families"] if f in dirs] + sorted(set(dirs) - set(cfg["families"]))
    families: list[dict] = []
    icons: dict[str, dict] = {}
    seen: dict[str, str] = {}
    for f in order:
        d = dirs[f]
        meta = json.loads((d / "family.json").read_text()) if (d / "family.json").exists() else {}
        files = {p.stem: p for p in d.glob("*.svg")}
        names = [n for n in meta.get("order", []) if n in files] + sorted(set(files) - set(meta.get("order", [])))
        for n in names:
            if not NAME.fullmatch(n):
                errors.append(f"icons/{f}/{n}.svg: name must be lowercase kebab-case, e.g. arrow-left")
                continue
            if n in seen:
                errors.append(f"{n}: same name in two sections ({seen[n]} and {f})")
                continue
            seen[n] = f
            got = read_icon(files[n])
            if not got:
                continue
            passport = d / f"{n}.json"
            tags = json.loads(passport.read_text()).get("tags", []) if passport.exists() else []
            icons[n] = {"name": n, "family": f, "body": got[0], "text": got[1], "file": files[n],
                        "tags": list(dict.fromkeys(n.split("-") + tags))}
        count = sum(1 for n in names if n in icons)
        if count:
            families.append({"id": f, "title": meta.get("title", f), "note": meta.get("note", ""), "count": count})
    return cfg, families, icons


# ── output files ─────────────────────────────────────────────────────────────

def stamp(icons: dict[str, dict], released: str) -> None:
    """Added/updated dates come from the previous build; anything new or changed gets today's date."""
    prev = DIST / "kiory.json"
    old = {i["name"]: i for i in json.loads(prev.read_text())["icons"]} if prev.exists() else {}
    for n, i in icons.items():
        h = hashlib.sha1(i["body"].encode()).hexdigest()[:12]
        o = old.get(n)
        i["hash"] = h
        i["added"] = o["added"] if o else (TODAY if old else released)
        i["updated"] = (o["updated"] if o["hash"] == h else TODAY) if o else i["added"]
    if gone := sorted(set(old) - set(icons)):
        notes.append(f"removed: {', '.join(gone)}")


def write(cfg: dict, families: list[dict], icons: dict[str, dict]) -> list[str]:
    order = [n for f in families for n in icons if icons[n]["family"] == f["id"]]
    shutil.rmtree(DIST / "svg", ignore_errors=True)
    (DIST / "svg").mkdir(parents=True)
    for n in order:
        (DIST / "svg" / f"{n}.svg").write_text(icons[n]["text"])

    manifest = {
        "name": cfg["name"], "version": cfg["version"], "released": cfg["released"], "count": len(order),
        "families": families,
        "icons": [{k: icons[n][k] for k in ("name", "family", "tags", "added", "updated", "hash", "body")} for n in order],
    }
    (DIST / "kiory.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")

    sprite = "".join(f'<symbol id="kiory-{n}" viewBox="0 0 24 24">{icons[n]["body"]}</symbol>' for n in order)
    (DIST / "kiory.sprite.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{sprite}</svg>\n')

    def uri(n: str) -> str:
        return "data:image/svg+xml," + quote(icons[n]["text"].strip().replace("currentColor", "#000"), safe=":/=\" ")
    css = [f"/* Kiory {cfg['version']}: <i class=\"ki ki-search\"></i>; size follows font-size, colour follows color */",
           ".ki{display:inline-block;width:1em;height:1em;flex:none;vertical-align:-.125em;background:currentColor;"
           "-webkit-mask:var(--ki) center/contain no-repeat;mask:var(--ki) center/contain no-repeat}"]
    css += [f'.ki-{n}{{--ki:url("{uri(n)}")}}' for n in order]
    (DIST / "kiory.css").write_text("\n".join(css) + "\n")

    js_icons = ",\n".join(f"  {json.dumps(n)}: {json.dumps(icons[n]['body'])}" for n in order)
    (DIST / "kiory.js").write_text(
        f"// Kiory {cfg['version']}: icon bodies and svg(name, {{ size }})\n"
        f"export const version = {json.dumps(cfg['version'])};\n"
        f"export const icons = {{\n{js_icons}\n}};\n"
        "export const names = Object.keys(icons);\n"
        "export function svg(name, { size = 24, ...attrs } = {}) {\n"
        "  const body = icons[name];\n"
        "  if (!body) throw new Error(`Kiory: no icon named \"${name}\"`);\n"
        "  const a = Object.entries(attrs).map(([k, v]) => ` ${k}=\"${v}\"`).join('');\n"
        "  return `<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"${size}\" height=\"${size}\" viewBox=\"0 0 24 24\" fill=\"none\"${a}>${body}</svg>`;\n"
        "}\n"
        "export default icons;\n")
    union = "\n  | ".join(json.dumps(n) for n in order)
    (DIST / "kiory.d.ts").write_text(
        f"export type KioryName =\n  | {union};\n"
        "export declare const version: string;\n"
        "export declare const icons: Record<KioryName, string>;\n"
        "export declare const names: KioryName[];\n"
        "export declare function svg(name: KioryName, opts?: { size?: number | string } & Record<string, string | number>): string;\n"
        "export default icons;\n")
    (DIST / "react.js").write_text(
        "// <KioryIcon name=\"search\" size={20} />: takes the text colour\n"
        "import { createElement } from 'react';\n"
        "import { icons } from './kiory.js';\n"
        "export function KioryIcon({ name, size = 24, title, ...rest }) {\n"
        "  const body = (title ? `<title>${title}</title>` : '') + (icons[name] || '');\n"
        "  return createElement('svg', { xmlns: 'http://www.w3.org/2000/svg', width: size, height: size, viewBox: '0 0 24 24', fill: 'none',\n"
        "    role: title ? 'img' : undefined, 'aria-hidden': title ? undefined : true, ...rest, dangerouslySetInnerHTML: { __html: body } });\n"
        "}\n"
        "export default KioryIcon;\n")
    (DIST / "react.d.ts").write_text(
        "import type { SVGProps, ReactElement } from 'react';\n"
        "import type { KioryName } from './kiory.js';\n"
        "export interface KioryIconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> { name: KioryName; size?: number | string; title?: string }\n"
        "export declare function KioryIcon(props: KioryIconProps): ReactElement;\n"
        "export default KioryIcon;\n")

    pkg_path = ROOT / "package.json"
    pkg = json.loads(pkg_path.read_text())
    if pkg.get("version") != cfg["version"]:
        pkg["version"] = cfg["version"]
        pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n")

    data = {
        "families": families, "version": cfg["version"], "released": cfg["released"], "repo": cfg["repository"],
        "icons": [{"n": n, "f": icons[n]["family"], "b": icons[n]["body"],
                   "t": [t for t in icons[n]["tags"] if t not in n.split("-")],
                   "a": icons[n]["added"], "u": icons[n]["updated"]} for n in order],
        "logo": (ROOT / "brand/kiory.svg").read_text(),
    }
    tpl = (ROOT / "scripts/gallery.html").read_text()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)).replace("__COUNT__", str(len(order)))
    (ROOT / "index.html").write_text(html)
    return order


# ── README cover ──────────────────────────────────────────────────────────

COVER = ["search", "home", "folder", "bell", "heart", "chat", "settings", "mail",
         "microphone", "camera", "cloud", "edit", "ai-spark", "webhook", "mention", "face-id"]


COVER_THEMES = {
    # photo on the right, a 4 × 3 grid on top; the branch lives above the grid, not inside its cells
    "dark": {"fg": "#f4f4f2", "bg": "#000000", "line": "#262626",
             "art": [("night-branch.jpg", 1100, -8, 500, 233, 1, False)]},
    "light": {"fg": "#000000", "bg": "#ffffff", "line": "#d9d4d1",
              "art": [("paper-stage.jpg", 712, -120, 888, 760, 1, False)]},
}


def art_image(name: str, x: float, y: float, w: float, h: float, opacity: float, fade: bool) -> str:
    path = ROOT / "art/readme" / name
    if not path.exists():
        return ""
    key = name.split(".")[0]
    mask = f' mask="url(#m-{key})"' if fade else ""
    defs = (f'<defs><linearGradient id="g-{key}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".7" stop-color="#fff"/></linearGradient><mask id="m-{key}"><rect x="{x}" y="{y}" width="{w}" '
            f'height="{h}" fill="url(#g-{key})"/></mask></defs>') if fade else ""
    return (defs + f'<image x="{x}" y="{y}" width="{w}" height="{h}" opacity="{opacity}"{mask} preserveAspectRatio="xMidYMid slice" '
            f'href="data:image/jpeg;base64,{base64.b64encode(path.read_bytes()).decode()}"/>')


def cover(icons, theme: str = "dark") -> str:
    t = COVER_THEMES[theme]
    w, h, fg, bg = 1600, 640, t["fg"], t["bg"]
    logo = (ROOT / "brand/kiory.svg").read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', logo)[1].split()]
    inner = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", logo, flags=re.S).replace("currentColor", fg)
    s = 560 / vb[2]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect width="100%" height="100%" fill="{bg}"/>']
    out += [art_image(*a) for a in t["art"]]
    out.append(f'<g transform="translate(96 {(h - vb[3] * s) / 2:.1f}) scale({s:.4f})" fill="{fg}">{inner}</g>')
    for i, n in enumerate([c for c in COVER if c in icons][:12]):
        cx, cy = 840 + (i % 4) * 172, 186 + (i // 4) * 134
        out.append(f'<rect x="{cx}.5" y="{cy}.5" width="171" height="133" fill="none" stroke="{t["line"]}"/>')
        out.append(f'<g transform="translate({cx + 62} {cy + 43}) scale(2)">' + icons[n]["body"].replace("currentColor", fg) + "</g>")
    out.append("</svg>")
    return "".join(out)


def render(svg: str, out: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as t:
        t.write(svg)
    subprocess.run(["rsvg-convert", t.name, "-o", str(out)], check=True)
    Path(t.name).unlink()


def previews(families, icons, order) -> None:
    if not shutil.which("rsvg-convert"):
        notes.append("rsvg-convert not found; the README cover was not updated")
        return
    d = ROOT / "docs"
    d.mkdir(parents=True, exist_ok=True)
    # re-render only when the inputs change: PNGs from different librsvg versions differ byte for byte
    art = sorted((p.name, hashlib.sha1(p.read_bytes()).hexdigest()) for p in (ROOT / "art/readme").glob("*"))
    key = hashlib.sha1(json.dumps([[(n, icons[n]["body"]) for n in COVER if n in icons],
                                   Path(__file__).read_text(), art]).encode()).hexdigest()
    stamp_file = d / ".cover-source"
    if stamp_file.exists() and stamp_file.read_text().strip() == key and (d / "cover-dark.png").exists():
        return
    stamp_file.write_text(key + "\n")
    render(cover(icons, "dark"), d / "cover-dark.png")
    render(cover(icons, "light"), d / "cover-light.png")


# ── entry point ─────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg, families, icons = load()
    if errors:
        for e in errors:
            print("✗", e)
        sys.exit(f"{len(errors)} errors; fix them and run again")
    unnormal = [i for i in icons.values() if i["file"].read_text() != i["text"]]
    if CHECK:
        if unnormal:
            print("• will be normalized by the build:", ", ".join(i["name"] for i in unnormal))
        print(f"✓ {len(icons)} icons, {len(families)} sections: check passed")
        return
    for i in unnormal:
        i["file"].write_text(i["text"])
        notes.append(f"normalized: {i['file'].relative_to(ROOT)}")
    stamp(icons, cfg["released"])
    order = write(cfg, families, icons)
    previews(families, icons, order)
    for n in notes:
        print("•", n)
    fresh = sum(1 for i in icons.values() if i["updated"] > cfg["released"])
    print(f"✓ {len(icons)} icons, {len(families)} sections" + (f", new or updated since {cfg['version']}: {fresh}" if fresh else ""))
    print("✓ dist/, index.html, docs/")


if __name__ == "__main__":
    main()
