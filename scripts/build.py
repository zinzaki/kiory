#!/usr/bin/env python3
"""Сборка Kiory: проверка SVG, manifest.json, спрайт, офлайн-каталог и превью.

    python3 scripts/build.py            # всё
    python3 scripts/build.py --check    # только проверка, ничего не пишет

Нужен только Python 3.11+; превью рендерит `rsvg-convert` (librsvg), если он есть.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "icons"
NS = "{http://www.w3.org/2000/svg}"
VERSION = "7.0.0"

FAMILY_TITLES = {
    "navigation": "Навигация",
    "actions-controls": "Действия",
    "charts-data": "Графики и данные",
    "commerce": "Коммерция",
    "design-editing": "Дизайн и графика",
    "windows-layout": "Окна и сетки",
    "files-documents": "Файлы и папки",
    "system-devices": "Система и устройства",
    "communication-status": "Общение и статус",
    "reactions-feedback": "Реакции",
    "development-ai": "Разработка и ИИ",
    "media-audio": "Медиа и звук",
    "general-utilities": "Общее",
}


def load_families() -> dict[str, list[str]]:
    return json.loads((ROOT / "families.json").read_text())


def check(families: dict[str, list[str]]) -> tuple[list[str], dict[str, str]]:
    """Возвращает (ошибки, {имя: тело svg})."""
    errors: list[str] = []
    bodies: dict[str, str] = {}
    files = {p.stem: p for p in ICONS.glob("*.svg")}
    listed = [n for ns in families.values() for n in ns]
    if unknown := set(families) - set(FAMILY_TITLES):
        errors.append(f"families.json: неизвестные семейства {sorted(unknown)}")
    dup = {n for n in listed if listed.count(n) > 1}
    if dup:
        errors.append(f"families.json: дубли {sorted(dup)}")
    for n in sorted(set(listed) - set(files)):
        errors.append(f"{n}: есть в families.json, нет файла")
    for n in sorted(set(files) - set(listed)):
        errors.append(f"{n}.svg: файла нет в families.json")
    for name, p in sorted(files.items()):
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            errors.append(f"{name}.svg: имя не в kebab-case")
        text = p.read_text()
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            errors.append(f"{name}.svg: битый XML ({e})")
            continue
        if root.get("viewBox") != "0 0 24 24":
            errors.append(f"{name}.svg: viewBox не 0 0 24 24")
        if re.search(r"<(image|text|filter|linearGradient|radialGradient|use|style)\b", text):
            errors.append(f"{name}.svg: недопустимый элемент")
        if re.search(r'stroke="(?!none)', text):
            errors.append(f"{name}.svg: обводка вместо контура")
        paths = list(root.iter(NS + "path"))
        if not paths:
            errors.append(f"{name}.svg: нет path")
        body = ""
        for el in paths:
            if el.get("transform"):
                errors.append(f"{name}.svg: transform у path")
            if el.get("fill") not in ("currentColor", None):
                errors.append(f"{name}.svg: цвет не currentColor")
            rule = el.get("fill-rule") or "nonzero"
            body += f'<path fill="currentColor" fill-rule="{rule}" d="{el.get("d")}"/>'
        bodies[name] = body
    return errors, bodies


def svg_icon(body: str) -> str:
    return f'<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">{body}</svg>'


def write_outputs(families: dict[str, list[str]], bodies: dict[str, str]) -> None:
    icons = [
        {"name": n, "family": f, "file": f"icons/{n}.svg", "tags": n.split("-")}
        for f, ns in families.items() for n in ns
    ]
    manifest = {
        "name": "Kiory", "version": VERSION, "grid": 24, "count": len(icons),
        "families": [{"id": f, "title": FAMILY_TITLES[f], "count": len(ns)} for f, ns in families.items()],
        "icons": icons,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    sprite = "".join(
        f'<symbol id="kiory-{n}" viewBox="0 0 24 24">{bodies[n]}</symbol>' for n in sorted(bodies)
    )
    (ROOT / "kiory.sprite.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{sprite}</svg>\n')

    data = {
        "families": manifest["families"],
        "icons": [{"n": i["name"], "f": i["family"], "b": bodies[i["name"]]} for i in icons],
        "logo": (ROOT / "brand/kiory.svg").read_text(),
        "version": VERSION,
    }
    tpl = (ROOT / "scripts/gallery.html").read_text()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)).replace("__COUNT__", str(len(icons)))
    (ROOT / "index.html").write_text(html)


def sheet(names: list[str], cols: int, cell: int, icon: int, fg: str, bg: str, pad: int = 48,
          labels: bool = False) -> str:
    rows = -(-len(names) // cols)
    lh = 22 if labels else 0
    w, h = pad * 2 + cols * cell, pad * 2 + rows * (cell + lh)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect width="100%" height="100%" fill="{bg}"/>']
    for i, n in enumerate(names):
        x = pad + (i % cols) * cell + (cell - icon) / 2
        y = pad + (i // cols) * (cell + lh) + (cell - icon) / 2
        s = icon / 24
        out.append(f'<g transform="translate({x:.2f} {y:.2f}) scale({s:.4f})" color="{fg}" fill="{fg}">'
                   + BODIES[n].replace("currentColor", fg) + "</g>")
        if labels:
            tx = pad + (i % cols) * cell + cell / 2
            ty = pad + (i // cols) * (cell + lh) + cell + 6
            out.append(f'<text x="{tx}" y="{ty}" font-family="Geologica, DejaVu Sans, sans-serif" font-size="12" '
                       f'fill="{fg}" fill-opacity=".5" text-anchor="middle">{n}</text>')
    out.append("</svg>")
    return "".join(out)


COVER = ["search", "home", "folder", "bell", "heart", "chat", "settings", "mail",
         "microphone", "camera", "cloud", "edit", "ai-spark", "webhook", "mention", "face-id"]


def cover() -> str:
    """Обложка README: логотип слева, 16 узнаваемых иконок справа."""
    w, h, fg, bg, plate, lily = 1600, 640, "#f4f4f2", "#000000", "#000000", "#f4f4f2"
    logo = (ROOT / "brand/kiory.svg").read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', logo)[1].split()]
    inner = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", logo, flags=re.S).replace("currentColor", fg)
    lw = 560
    s = lw / vb[2]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect width="100%" height="100%" fill="{bg}"/>',
           f'<g transform="translate(96 150) scale({s:.4f})" fill="{fg}">{inner}</g>',
           f'<text x="98" y="420" font-family="Geologica, DejaVu Sans, sans-serif" font-size="30" fill="{fg}">'
           f'{len(BODIES)} иконок · сетка 24 × 24 · залитые SVG</text>',
           f'<text x="98" y="466" font-family="Geologica, DejaVu Sans, sans-serif" font-size="22" fill="{fg}" '
           f'fill-opacity=".55">Мягкая плотная линия. Разрыв с каплей там, где он нужен.</text>']
    for i, n in enumerate(COVER):
        cx, cy = 840 + (i % 4) * 172, 64 + (i // 4) * 134
        col = lily if n == "search" else fg
        out.append(f'<rect x="{cx}.5" y="{cy}.5" width="171" height="133" fill="{plate}" stroke="#2a2a2a"/>')
        out.append(f'<g transform="translate({cx + 62} {cy + 43}) scale({48 / 24})">'
                   + BODIES[n].replace("currentColor", col) + "</g>")
    out.append("</svg>")
    return "".join(out)


def render(svg: str, out: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as t:
        t.write(svg)
    subprocess.run(["rsvg-convert", t.name, "-o", str(out)], check=True)
    Path(t.name).unlink()


def previews(families: dict[str, list[str]]) -> None:
    if not shutil.which("rsvg-convert"):
        print("rsvg-convert не найден — превью пропущены")
        return
    d = ROOT / "docs/previews"
    d.mkdir(parents=True, exist_ok=True)
    allnames = [n for ns in families.values() for n in ns]
    render(sheet(allnames, 22, 56, 24, "#f4f4f2", "#000000"), d / "all-24-dark.png")
    render(sheet(allnames, 22, 56, 24, "#000000", "#ffffff"), d / "all-24-light.png")
    render(sheet(allnames, 32, 32, 16, "#f4f4f2", "#000000", pad=24), d / "all-16-dark.png")
    render(cover(), d / "cover.png")
    for f, ns in families.items():
        render(sheet(ns, 8, 112, 48, "#f4f4f2", "#000000", labels=True), d / f"{f}.png")


BODIES: dict[str, str] = {}

if __name__ == "__main__":
    fam = load_families()
    errs, BODIES = check(fam)
    for e in errs:
        print("✗", e)
    total = sum(len(v) for v in fam.values())
    if errs:
        sys.exit(f"{len(errs)} ошибок")
    print(f"✓ {total} иконок, {len(fam)} семейств — проверка пройдена")
    if "--check" in sys.argv:
        sys.exit(0)
    write_outputs(fam, BODIES)
    previews(fam)
    print("✓ manifest.json, kiory.sprite.svg, index.html, docs/previews/")
