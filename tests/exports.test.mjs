import test from 'node:test';
import assert from 'node:assert/strict';
import { svg } from '../dist/kiory.js';

test('attribute values cannot terminate their XML attribute', () => {
  const result = svg('search', { 'aria-label': 'Find "A&B" <now>', size: '24" data-extra="yes' });
  assert.ok(result.includes('aria-label="Find &quot;A&amp;B&quot; &lt;now&gt;"'));
  assert.ok(!result.includes(' data-extra="yes'));
});
test('event handlers and malformed attribute names are rejected', () => {
  for (const attrs of [{onload:'alert(1)'}, {'x" data-extra':'yes'}]) {
    assert.throws(() => svg('search', attrs), /attribute/i);
  }
});
test('inherited object properties are not icon names', () => {
  for (const name of ['constructor', '__proto__', 'toString', 'missing-icon']) {
    assert.throws(() => svg(name), /no icon named/);
  }
});
test('valid consumer attributes and size survive', () => {
  const result = svg('search', {size:20, role:'img', 'aria-label':'Search', class:'toolbar-icon'});
  assert.ok(result.includes('width="20"'));
  assert.ok(result.includes('role="img"'));
  assert.ok(result.includes('class="toolbar-icon"'));
});

test('React titles remain text, even when they contain markup', async () => {
  const { createElement } = await import('react');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const { KioryIcon } = await import('../dist/react.js');
  const html = renderToStaticMarkup(createElement(KioryIcon, {name:'search', title:'</title><script>alert(1)</script>&'}));
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('&lt;/title&gt;&lt;script&gt;alert(1)&lt;/script&gt;&amp;'));
  assert.ok(html.includes('role="img"'));
});
test('React rejects unknown icons instead of silently rendering an empty button', async () => {
  const { KioryIcon } = await import('../dist/react.js');
  assert.throws(() => KioryIcon({name:'constructor'}), /no icon named/);
});

test('all delivery formats contain the same source icon set', async () => {
  const { readFile, readdir } = await import('node:fs/promises');
  const { icons, names } = await import('../dist/kiory.js');
  const root = new URL('../', import.meta.url);
  const source=[];
  for (const family of await readdir(new URL('icons/',root), {withFileTypes:true})) {
    if (!family.isDirectory()) continue;
    for (const file of await readdir(new URL(`icons/${family.name}/`,root))) {
      if (file.endsWith('.svg')) source.push(file.slice(0,-4));
    }
  }
  source.sort();
  const manifest=JSON.parse(await readFile(new URL('dist/kiory.json',root),'utf8'));
  const sprite=await readFile(new URL('dist/kiory.sprite.svg',root),'utf8');
  const css=await readFile(new URL('dist/kiory.css',root),'utf8');
  assert.deepEqual([...names].sort(),source);
  assert.deepEqual(Object.keys(icons).sort(),source);
  assert.deepEqual(manifest.icons.map(i=>i.name).sort(),source);
  assert.deepEqual([...sprite.matchAll(/<symbol id="kiory-([^"]+)"/g)].map(m=>m[1]).sort(),source);
  assert.deepEqual([...css.matchAll(/^\.ki-([^\{]+)\{/gm)].map(m=>m[1]).sort(),source);
  assert.deepEqual((await readdir(new URL('dist/svg/',root))).map(n=>n.slice(0,-4)).sort(),source);
  for (const icon of manifest.icons) assert.equal(icons[icon.name],icon.body);
});

test('explicit dimensions replace defaults instead of duplicating XML attributes', () => {
  const result=svg('search',{size:24,width:32,height:20,fill:'currentColor'});
  assert.equal([...result.matchAll(/\bwidth="/g)].length,1);
  assert.equal([...result.matchAll(/\bheight="/g)].length,1);
  assert.ok(result.includes('width="32"'));
  assert.ok(result.includes('height="20"'));
});
