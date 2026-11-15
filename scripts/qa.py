#!/usr/bin/env python3
"""Render every source icon; report empty/clipped geometry and exact visual duplicates.

Requires rsvg-convert and Pillow. No network or source writes.
Usage: python3 scripts/qa.py [--output qa-output] [--names search save ...]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import build

SIZES = (16, 20, 24, 32)


def render(svg: str) -> bytes:
    result = subprocess.run(['rsvg-convert'], input=svg.encode(), capture_output=True, check=True)
    return result.stdout


def measure(body: str) -> dict:
    from PIL import Image
    # Four pixels of padding expose paths outside the canvas instead of clipping them away.
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="-4 -4 32 32"><g color="#000">{body}</g></svg>'
    alpha = Image.open(io.BytesIO(render(svg))).convert('RGBA').getchannel('A')
    bbox = alpha.getbbox()
    # Ignore alpha below 5/255 when determining ink bounds (antialiasing fringes).
    ink = alpha.point(lambda a: 255 if a > 4 else 0).getbbox()
    bounds = [round((v - 16) / 4, 2) for v in ink] if ink else None
    return {
        'bounds': bounds,
        'empty': bbox is None,
        'clipped': bool(bounds and (min(bounds[:2]) < 0 or max(bounds[2:]) > 24)),
        'inkArea': round(sum(alpha.tobytes()) / 255 / 16, 2),
        'rasterHash': hashlib.sha256(alpha.tobytes()).hexdigest()[:16],
    }


def sheet(items: list[dict], title: str) -> str:
    height = 72 + 72 * len(items)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="{height}">',
           '<rect width="560" height="100%" fill="#f7f5f2"/><rect x="560" width="560" height="100%" fill="#060606"/>']
    for x, fg in ((0, '#141211'), (560, '#f2efe9')):
        out.append(f'<text x="{x+24}" y="30" fill="{fg}" font-family="sans-serif" font-size="15">{html.escape(title)}</text>')
        for k, size in enumerate(SIZES):
            out.append(f'<text x="{x+240+k*76}" y="52" fill="{fg}" font-family="sans-serif" font-size="11">{size} px</text>')
        for row, item in enumerate(items):
            y = 72 + row * 72
            out.append(f'<text x="{x+24}" y="{y+28}" fill="{fg}" font-family="sans-serif" font-size="12">{html.escape(item["name"])}</text>')
            for k, size in enumerate(SIZES):
                out.append(f'<g color="{fg}" transform="translate({x+240+k*76} {y+10}) scale({size/24})">{item["body"]}</g>')
    return ''.join(out) + '</svg>'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('qa-output'))
    parser.add_argument('--names', nargs='+')
    args = parser.parse_args()
    if not shutil.which('rsvg-convert'):
        parser.error('install librsvg (Arch) or librsvg2-bin (Debian/Ubuntu) for rsvg-convert')
    try:
        import PIL  # noqa: F401
    except ImportError:
        parser.error('Pillow is required: python3 -m pip install Pillow (or use a virtual environment)')
    build.errors.clear()
    cfg, families, icons = build.load()
    if build.errors:
        print('\n'.join(build.errors), file=sys.stderr)
        return 1
    if args.names:
        missing = sorted(set(args.names) - icons.keys())
        if missing:
            parser.error('unknown icons: ' + ', '.join(missing))
        icons = {n: icons[n] for n in args.names}
    args.output.mkdir(parents=True, exist_ok=True)
    results, hashes, errors = {}, {}, []
    for name, icon in icons.items():
        try:
            metrics = measure(icon['body'])
        except subprocess.CalledProcessError as exc:
            errors.append(f'{name}: renderer failed: {exc.stderr.decode().strip()}')
            continue
        results[name] = metrics
        hashes.setdefault(metrics['rasterHash'], []).append(name)
        if metrics['empty'] or metrics['clipped']:
            errors.append(f'{name}: {"empty" if metrics["empty"] else "outside 24 × 24"}: {metrics["bounds"]}')
    duplicates = [names for names in hashes.values() if len(names) > 1]
    report = {'version': cfg['version'], 'count': len(icons), 'sizes': SIZES,
              'errors': errors, 'visualDuplicates': duplicates, 'icons': results}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    pages = []
    for family in families:
        items = [i for i in icons.values() if i['family'] == family['id']]
        for start in range(0, len(items), 24):
            name = f'{family["id"]}-{start//24+1}'
            svg = sheet(items[start:start+24], f'{family["title"]} / Kiory {cfg["version"]}')
            (args.output / f'{name}.svg').write_text(svg)
            (args.output / f'{name}.png').write_bytes(render(svg))
            pages.append(f'<section><h2>{html.escape(family["title"])} · {start//24+1}</h2><img src="{name}.png" alt="{html.escape(family["title"])} at 16, 20, 24 and 32 px on light and dark backgrounds"></section>')
    (args.output / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kiory quality sheets</title><style>body{margin:32px;background:#f7f5f2;color:#141211;font:16px system-ui}main{max-width:1120px;margin:auto}img{max-width:100%;height:auto}h2{font-size:18px;margin-top:40px}</style><main><h1>Kiory quality sheets</h1><p>Native 16, 20, 24 and 32 px. Inspect at 100% zoom on a desktop. Smaller screens scale the sheets.</p><p><a href="report.json">Geometry and duplicate report</a>. Duplicates are review candidates, not automatic failures. Geometry checks do not establish recognisability.</p>' + ''.join(pages) + '</main></html>')
    print(f'{len(icons)} icons rendered; {len(errors)} geometry errors; {len(duplicates)} exact duplicate groups')
    for error in errors:
        print('ERROR:', error)
    for names in duplicates:
        print('REVIEW duplicate:', ', '.join(names))
    print(f'Visual sheets: {args.output.resolve() / "index.html"}')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
