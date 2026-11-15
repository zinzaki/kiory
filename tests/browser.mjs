// Run against a built catalog served by: python3 -m http.server 8766 --bind 127.0.0.1
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
const url = process.env.KIORY_URL || 'http://127.0.0.1:8766';
const output = process.env.KIORY_QA_OUTPUT || 'qa-output';
await mkdir(output, {recursive:true});
const browser = await chromium.launch({headless:true, ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {})});
const failures=[];
async function check(name, fn) { try { await fn(); console.log(`PASS ${name}`); } catch(e) {failures.push(name);console.error(`FAIL ${name}: ${e.message}`);} }
const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',colorScheme:'dark'});
const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await check('queries ignore spaces, hyphens, case and word order', async()=>{
  await page.goto(url);
  for (const term of ['arrow left','LEFT ARROW','arrow-left']) {
    await page.locator('#q').fill(term);
    assert.ok(await page.locator('.t[data-n="arrow-left"]:visible').count(),term);
    assert.equal(await page.locator('.t[data-n="arrow-right"]:visible').count(),0,term);
  }
  await page.locator('#hq').fill('left arrow');
  assert.ok(await page.locator('#field i[data-n="arrow-left"].hit').count());
});
await check('typing from the page does not throw on a search input', async()=>{
  await page.goto(url);await page.locator('body').click({position:{x:4,y:180}});
  await page.keyboard.type('sun');
  assert.equal(await page.locator('#hq').inputValue(),'sun');
  assert.deepEqual(errors,[]);
});
await check('keyboard opens details, traps focus and restores the opener', async()=>{
  await page.goto(url+'/#catalog');await page.locator('#q').fill('light-sun');
  const tile=page.locator('.t[data-n="light-sun"] .hit');await tile.focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('#card').getAttribute('aria-hidden'),'false');
  assert.equal(await page.locator('#card').getAttribute('role'),'dialog');
  await page.locator('#c-next').focus();await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'c-close');
  await page.keyboard.press('Shift+Tab');assert.equal(await page.evaluate(()=>document.activeElement.id),'c-next');
  await page.keyboard.press('Escape');assert.equal(await tile.evaluate(el=>el===document.activeElement),true);
});
await check('set survives reload and ignores removed names', async()=>{
  await page.goto(url+'/#catalog');await page.locator('#q').fill('search');
  await page.locator('.t[data-n="search"] .hit').click({modifiers:['Control']});
  await page.reload();assert.equal(await page.locator('.t[data-n="search"] .pick').getAttribute('aria-pressed'),'true');
  await page.evaluate(()=>localStorage.setItem('kiory-set',JSON.stringify(['search','removed-icon','__proto__',12])));await page.reload();assert.equal(await page.locator('.t.sel').count(),1);
  await page.locator('#t-clear').click();await page.reload();assert.equal(await page.locator('.t.sel').count(),0);
});
await check('shift selection does not include unrelated items when its anchor is filtered out', async()=>{
  await page.goto(url+'/#catalog');await page.locator('#q').fill('home');
  await page.locator('.t[data-n="home"] .hit').click({modifiers:['Control']});
  await page.locator('#q').fill('arrow');
  await page.locator('.t[data-n="arrow-right"] .hit').click({modifiers:['Shift']});
  assert.equal(await page.locator('.t.sel').count(),2);
  await page.locator('#t-clear').click();
});
await check('icon links respond to hash changes on an already open catalog', async()=>{
  await page.goto(url);await page.evaluate(()=>{location.hash='light-sun';});
  await page.waitForFunction(()=>document.querySelector('#card').getAttribute('aria-hidden')==='false', null, {timeout:2000});
  assert.equal(await page.locator('#c-name').textContent(),'light-sun');
  await page.evaluate(()=>{location.hash='catalog';});
  await page.waitForFunction(()=>document.querySelector('#card').getAttribute('aria-hidden')==='true', null, {timeout:2000});
});
await check('downloaded set contains usable SVGs, sprite, manifest and full licence', async()=>{
  await page.goto(url+'/#catalog');await page.locator('#q').fill('save');
  await page.locator('.t[data-n="save"] .hit').click({modifiers:['Control']});
  const pending=page.waitForEvent('download');await page.locator('#t-zip').click();
  const download=await pending;const target=`${output}/set.zip`;await download.saveAs(target);
  execFileSync('python3',['-c',`import zipfile,sys,json,xml.etree.ElementTree as ET
with zipfile.ZipFile(sys.argv[1]) as z:
 assert z.testzip() is None
 assert 'kiory/LICENSE' in z.namelist(), 'full licence missing'
 assert 'PolyForm' in z.read('kiory/LICENSE').decode()
 ET.fromstring(z.read('kiory/svg/save.svg'))
 ET.fromstring(z.read('kiory/kiory.sprite.svg'))
 assert [i['name'] for i in json.loads(z.read('kiory/kiory.json'))] == ['save']`,target]);
});
await check('desktop and mobile, both themes: no horizontal overflow', async()=>{
  for (const width of [1440,390]) for (const theme of ['dark','light']) {
    await page.setViewportSize({width,height:width===390?844:1000});
    await page.goto(url);await page.evaluate(t=>{document.documentElement.dataset.theme=t;},theme);
    await page.screenshot({path:`${output}/${width}-${theme}.png`});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${width} ${theme}`);
    await page.locator('#q').fill('light');await page.locator('#catalog').scrollIntoViewIfNeeded();
    await page.screenshot({path:`${output}/${width}-${theme}-catalog.png`});
    await page.goto(url+'/#light-sun');await page.waitForFunction(()=>document.querySelector('#card').getAttribute('aria-hidden')==='false');await page.screenshot({path:`${output}/${width}-${theme}-card.png`});
  }
});
await check('standalone file works with storage denied', async()=>{
  const offline=await browser.newContext({reducedMotion:'reduce'});
  const p=await offline.newPage();const localErrors=[];p.on('pageerror',e=>localErrors.push(e.message));
  await p.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw new Error('Storage disabled');}});});
  await p.goto(new URL('../index.html',import.meta.url).href);
  await p.locator('#q').fill('save as');assert.equal(await p.locator('.t[data-n="save-as"]:visible').count(),1);
  await p.locator('.t[data-n="save-as"] .hit').focus();await p.keyboard.press('Enter');
  assert.equal(await p.locator('#c-name').textContent(),'save-as');
  const pending=p.waitForEvent('download');await p.locator('#c-dl').click();
  const download=await pending;await download.saveAs(`${output}/offline-save-as.svg`);
  assert.ok((await readFile(`${output}/offline-save-as.svg`,'utf8')).startsWith('<svg'));
  assert.deepEqual(localErrors,[]);await offline.close();
});
await check('touch opens details and exports a transparent PNG', async()=>{
  const mobile=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,reducedMotion:'reduce'});
  const p=await mobile.newPage();await p.goto(url+'/#catalog');await p.locator('#q').fill('save');
  await p.locator('.t[data-n="save"] .hit').tap();
  assert.equal(await p.locator('#c-name').textContent(),'save');
  const pending=p.waitForEvent('download');await p.locator('[data-png="64"]').tap();
  const download=await pending;const target=`${output}/save-64.png`;await download.saveAs(target);
  execFileSync('python3',['-c',`from PIL import Image
import sys
im=Image.open(sys.argv[1]).convert('RGBA')
assert im.size == (64,64)
a=im.getchannel('A')
assert a.getextrema() == (0,255)
assert a.getbbox() is not None`,target]);
  await mobile.close();
});
await check('SVG geometry stays inside the canvas, including distant stray paths', async()=>{
  const manifest=JSON.parse(await readFile(new URL('../dist/kiory.json',import.meta.url),'utf8'));
  const bad=await page.evaluate(items=>{
    const host=document.createElementNS('http://www.w3.org/2000/svg','svg');document.body.append(host);
    const bad=[];
    for(const i of items){host.innerHTML=i.body;const b=host.getBBox();if(b.width<=0||b.height<=0||b.x<-.01||b.y<-.01||b.x+b.width>24.01||b.y+b.height>24.01)bad.push(i.name);}
    host.remove();return bad;
  },manifest.icons);
  assert.deepEqual(bad,[]);
});
await check('no page exceptions',async()=>assert.deepEqual(errors,[]));
await browser.close();if(failures.length)process.exitCode=1;
