#!/usr/bin/env python3
"""Сборка Kiory.

    python3 scripts/build.py            # привести иконки к единому виду и собрать всё
    python3 scripts/build.py --check    # только проверить, ничего не пишет

Источник правды — папка `icons/`:

    icons/<семейство>/family.json       {"title": "...", "order": [...]}  — order необязателен
    icons/<семейство>/<имя>.svg         сама иконка (экспорт из Figma подойдёт)
    icons/<семейство>/<имя>.json        паспорт, необязателен: {"tags": ["лупа", "найти"]}

Положил или заменил файл — запустил сборку (или просто запушил: соберёт GitHub Actions).
Сборка приведёт SVG к единому виду, отметит новые и обновлённые иконки, пересоберёт dist/,
каталог index.html и превью. Нужен Python 3.11+; превью рисует `rsvg-convert` (librsvg).
"""
from __future__ import annotations

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


# ── чтение и нормализация ──────────────────────────────────────────────────────

def body_of(paths: list[tuple[str, str]]) -> str:
    return "".join(f'<path fill="currentColor" fill-rule="{r}" d="{d}"/>' for r, d in paths)


def read_icon(p: Path) -> tuple[str, str] | None:
    """(тело из path, канонический текст файла) или None, если иконку не разобрать."""
    rel = p.relative_to(ROOT)
    try:
        root = ET.fromstring(p.read_text())
    except ET.ParseError as e:
        errors.append(f"{rel}: битый XML ({e})")
        return None
    vb = root.get("viewBox")
    if vb is None and root.get("width") in ("24", "24px") and root.get("height") in ("24", "24px"):
        vb = "0 0 24 24"
    try:
        ok = vb is not None and [float(v) for v in vb.replace(",", " ").split()] == [0, 0, 24, 24]
    except ValueError:
        ok = False
    if not ok:
        errors.append(f"{rel}: нужен холст 24 × 24 (viewBox «0 0 24 24»), а тут «{vb}»")
        return None
    paths: list[tuple[str, str]] = []

    def walk(el: ET.Element, rule: str | None) -> None:
        tag = el.tag.replace(NS, "")
        if tag in ("title", "desc", "metadata"):
            return
        if tag == "defs":
            if len(el):
                errors.append(f"{rel}: <defs> с содержимым (маски, градиенты) не поддерживаются")
            return
        if tag not in ("svg", "g", "path"):
            errors.append(f"{rel}: <{tag}> не поддерживается — переведи фигуры в контуры (Outline stroke, Flatten)")
            return
        if el.get("transform"):
            errors.append(f"{rel}: transform у <{tag}> — сделай Flatten перед экспортом")
        if el.get("stroke") not in (None, "none"):
            errors.append(f"{rel}: обводка — переведи её в контур (Outline stroke)")
        if el.get("clip-path") or el.get("mask") or el.get("opacity") or el.get("fill-opacity"):
            errors.append(f"{rel}: маски и прозрачность не поддерживаются")
        rule = el.get("fill-rule") or el.get("clip-rule") or rule
        if tag == "path" and el.get("fill") != "none":
            d = " ".join((el.get("d") or "").split())
            if d:
                paths.append((rule or "nonzero", d))
        for ch in el:
            walk(ch, rule)

    walk(root, None)
    if not paths:
        errors.append(f"{rel}: внутри нет ни одного залитого контура")
        return None
    body = body_of(paths)
    return body, f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">{body}</svg>\n'


def load() -> tuple[dict, list[dict], dict[str, dict]]:
    cfg = json.loads((ROOT / "kiory.json").read_text())
    for p in ICONS.glob("*.svg"):
        errors.append(f"{p.relative_to(ROOT)}: иконка вне семейства — перенеси в icons/<семейство>/")
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
                errors.append(f"icons/{f}/{n}.svg: имя — латиницей в kebab-case, например arrow-left")
                continue
            if n in seen:
                errors.append(f"{n}: одно имя в двух семействах ({seen[n]} и {f})")
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
            families.append({"id": f, "title": meta.get("title", f), "count": count})
    return cfg, families, icons


# ── выходные файлы ─────────────────────────────────────────────────────────────

def stamp(icons: dict[str, dict], released: str) -> None:
    """Даты появления и обновления берутся из прошлой сборки; новое и изменённое — сегодняшним днём."""
    prev = DIST / "kiory.json"
    old = {i["name"]: i for i in json.loads(prev.read_text())["icons"]} if prev.exists() else {}
    for n, i in icons.items():
        h = hashlib.sha1(i["body"].encode()).hexdigest()[:12]
        o = old.get(n)
        i["hash"] = h
        i["added"] = o["added"] if o else (TODAY if old else released)
        i["updated"] = (o["updated"] if o["hash"] == h else TODAY) if o else i["added"]
    if gone := sorted(set(old) - set(icons)):
        notes.append(f"убраны: {', '.join(gone)}")


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
    css = [f"/* Kiory {cfg['version']}: <i class=\"ki ki-search\"></i> — размер задаёт font-size, цвет — color */",
           ".ki{display:inline-block;width:1em;height:1em;flex:none;vertical-align:-.125em;background:currentColor;"
           "-webkit-mask:var(--ki) center/contain no-repeat;mask:var(--ki) center/contain no-repeat}"]
    css += [f'.ki-{n}{{--ki:url("{uri(n)}")}}' for n in order]
    (DIST / "kiory.css").write_text("\n".join(css) + "\n")

    js_icons = ",\n".join(f"  {json.dumps(n)}: {json.dumps(icons[n]['body'])}" for n in order)
    (DIST / "kiory.js").write_text(
        f"// Kiory {cfg['version']}: тела иконок и svg(name, {{ size }})\n"
        f"export const version = {json.dumps(cfg['version'])};\n"
        f"export const icons = {{\n{js_icons}\n}};\n"
        "export const names = Object.keys(icons);\n"
        "export function svg(name, { size = 24, ...attrs } = {}) {\n"
        "  const body = icons[name];\n"
        "  if (!body) throw new Error(`Kiory: нет иконки «${name}»`);\n"
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
        "// <KioryIcon name=\"search\" size={20} /> — берёт цвет текста\n"
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


# ── превью для README ──────────────────────────────────────────────────────────

def sheet(icons, names, cols, cell, icon, fg, bg, line=None, pad=48, labels=False) -> str:
    rows = -(-len(names) // cols)
    lh = 24 if labels else 0
    w, h = pad * 2 + cols * cell, pad * 2 + rows * (cell + lh)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect width="100%" height="100%" fill="{bg}"/>']
    for i, n in enumerate(names):
        cx, cy = pad + (i % cols) * cell, pad + (i // cols) * (cell + lh)
        if line:
            out.append(f'<rect x="{cx + .5}" y="{cy + .5}" width="{cell}" height="{cell + lh}" fill="none" stroke="{line}"/>')
        x, y = cx + (cell - icon) / 2, cy + (cell - icon) / 2
        out.append(f'<g transform="translate({x:.2f} {y:.2f}) scale({icon / 24:.4f})">'
                   + icons[n]["body"].replace("currentColor", fg) + "</g>")
        if labels:
            out.append(f'<text x="{cx + cell / 2}" y="{cy + cell + 8}" font-family="DejaVu Sans Mono, monospace" font-size="11" '
                       f'fill="{fg}" fill-opacity=".5" text-anchor="middle">{n}</text>')
    out.append("</svg>")
    return "".join(out)


COVER = ["search", "home", "folder", "bell", "heart", "chat", "settings", "mail",
         "microphone", "camera", "cloud", "edit", "ai-spark", "webhook", "mention", "face-id"]


def cover(icons) -> str:
    w, h, fg, bg = 1600, 640, "#f4f4f2", "#000000"
    logo = (ROOT / "brand/kiory.svg").read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', logo)[1].split()]
    inner = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", logo, flags=re.S).replace("currentColor", fg)
    s = 560 / vb[2]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect width="100%" height="100%" fill="{bg}"/>',
           f'<g transform="translate(96 {(h - vb[3] * s) / 2:.1f}) scale({s:.4f})" fill="{fg}">{inner}</g>']
    for i, n in enumerate([c for c in COVER if c in icons][:16]):
        cx, cy = 840 + (i % 4) * 172, 52 + (i // 4) * 134
        out.append(f'<rect x="{cx}.5" y="{cy}.5" width="171" height="133" fill="{bg}" stroke="#2a2a2a"/>')
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
        notes.append("rsvg-convert не найден — превью не обновлены")
        return
    d = ROOT / "docs/previews"
    d.mkdir(parents=True, exist_ok=True)
    # перерисовываем только когда поменялись иконки: PNG от разных версий librsvg отличаются байтами
    key = hashlib.sha1(json.dumps([families, [(n, icons[n]["body"]) for n in order],
                                   Path(__file__).read_text()]).encode()).hexdigest()
    stamp_file = d / ".source"
    if stamp_file.exists() and stamp_file.read_text().strip() == key and (d / "cover.png").exists():
        return
    stamp_file.write_text(key + "\n")
    for old in d.glob("*.png"):
        old.unlink()
    render(cover(icons), d / "cover.png")
    render(sheet(icons, order, 22, 56, 24, "#f4f4f2", "#000000"), d / "all-dark.png")
    render(sheet(icons, order, 22, 56, 24, "#000000", "#ffffff"), d / "all-light.png")
    for f in families:
        ns = [n for n in order if icons[n]["family"] == f["id"]]
        render(sheet(icons, ns, 8, 112, 40, "#f4f4f2", "#000000", "#222222", labels=True), d / f"{f['id']}.png")


# ── запуск ─────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg, families, icons = load()
    if errors:
        for e in errors:
            print("✗", e)
        sys.exit(f"{len(errors)} ошибок — исправь и запусти снова")
    unnormal = [i for i in icons.values() if i["file"].read_text() != i["text"]]
    if CHECK:
        if unnormal:
            print("• будут приведены к единому виду при сборке:", ", ".join(i["name"] for i in unnormal))
        print(f"✓ {len(icons)} иконок, {len(families)} семейств — проверка пройдена")
        return
    for i in unnormal:
        i["file"].write_text(i["text"])
        notes.append(f"приведена к единому виду: {i['file'].relative_to(ROOT)}")
    stamp(icons, cfg["released"])
    order = write(cfg, families, icons)
    previews(families, icons, order)
    for n in notes:
        print("•", n)
    fresh = sum(1 for i in icons.values() if i["updated"] > cfg["released"])
    print(f"✓ {len(icons)} иконок, {len(families)} семейств" + (f", новых и обновлённых после {cfg['version']}: {fresh}" if fresh else ""))
    print("✓ dist/, index.html, docs/previews/")


if __name__ == "__main__":
    main()
