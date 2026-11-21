// Optional: requires Playwright and a running Companion using ManualSave-661.
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {}),
    args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const url = new URL(process.env.COMPANION_URL || 'http://127.0.0.1:8765'); url.searchParams.set('lang','pl'); await page.goto(url.href);
    await page.waitForSelector('#hero .big');
    await page.click('[data-tab="iconic"]');
    assert.equal(await page.locator('#iconic-rows tr').count(), 20);
    assert.match(await page.locator('#iconic-count').innerText(), /112 z 112/);
    await page.selectOption('#iconic-status', 'stash');
    assert.equal(await page.locator('#iconic-rows tr').count(), 20);
    assert.match(await page.locator('#iconic-count').innerText(), /58 z 112/);
    await page.fill('#iconic-search', 'Byakko');
    assert.equal(await page.locator('#iconic-rows tr').count(), 1);
    assert.match(await page.locator('#iconic-rows').innerText(), /SCHOWEK/);
    await page.locator('details[data-guide-id="byakko"] summary').click();
    assert.match(await page.locator('#iconic-rows').innerText(), /Professional Widow/);
    await page.click('#refresh');
    await page.waitForFunction(() => !document.querySelector('#refresh').disabled);
    assert.deepEqual(await page.locator('.tab-panel:visible').evaluateAll(xs=>xs.map(x=>x.id)), ['iconic']);
    assert.equal(await page.locator('#iconic-search').inputValue(), 'Byakko');
    assert.equal(await page.locator('details[data-guide-id="byakko"]').getAttribute('open'), '');
    await page.fill('#iconic-search', '');
    await page.selectOption('#iconic-status', 'equipped');
    assert.equal(await page.locator('#iconic-rows tr').count(), 2);
    assert.match(await page.locator('#iconic-rows').innerText(), /SKIPPY/);
    await page.selectOption('#iconic-game', 'phantom_liberty');
    assert.match(await page.locator('#iconic-rows').innerText(), /Brak wyników/);
    await page.selectOption('#iconic-game', '');
    await page.selectOption('#iconic-status', '');
    await page.selectOption('#iconic-guide-filter', 'needs_verification');
    assert.equal(await page.locator('#iconic-rows tr[class]').count(), 0);
    assert.match(await page.locator('#iconic-rows').innerText(), /Brak wyników/);
    await page.selectOption('#iconic-guide-filter', '');
    if (process.env.COMPANION_SCREENSHOT) await page.screenshot({path:process.env.COMPANION_SCREENSHOT,fullPage:true});
    assert.deepEqual(errors, []);
    console.log('PASS: 112 models, pagination, 58 stash, Byakko guide, persistent details, empty pending-guide results, filters, no JS errors');
  } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exit(1);});
