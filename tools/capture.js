// Screenshot every project URL and record whether the site still looks alive.
// Usage: node capture.js [--only-missing]
// Output: ../site/shots/<key>.jpg and ../data/sites.json
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { chromium } = require('playwright-core');

const ROOT = path.resolve(__dirname, '..');
const SHOTS = path.join(ROOT, 'site/shots');
const OUT = path.join(ROOT, 'data/sites.json');
fs.mkdirSync(SHOTS, { recursive: true });

const lines = fs.readFileSync(path.join(ROOT, 'data/projects.psv'), 'utf8').trim().split('\n');
const header = lines.shift().split('|');
const urls = [...new Set(lines.map(l => Object.fromEntries(l.split('|').map((v, i) => [header[i], v]))).map(r => r.url).filter(Boolean))];

const keyOf = u => crypto.createHash('sha1').update(u).digest('hex').slice(0, 12);
const prev = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf8')) : {};
const onlyMissing = process.argv.includes('--only-missing');

const DEAD = [
  /domain (name )?(is|may be) for sale/i, /buy this domain/i, /this domain (has expired|is parked)/i,
  /parked (free|domain|by)/i, /hugedomains/i, /sedo\.com|dan\.com|afternic/i, /account (has been )?suspended/i,
  /site (can.t be reached|not found)/i, /there isn.t a github pages site here/i, /deployment (not found|could not be found)/i,
  /herokucdn|no such app/i, /this site is no longer available/i, /domain (registration )?expired/i,
];

async function one(browser, url) {
  const key = keyOf(url);
  const rec = { url, key, checkedAt: new Date().toISOString() };
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'en-US', ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    rec.httpStatus = resp ? resp.status() : null;
    await page.waitForTimeout(3000);
    rec.finalUrl = page.url();
    const info = await page.evaluate(() => {
      const meta = n => document.querySelector(`meta[name="${n}"],meta[property="${n}"]`)?.content || '';
      return {
        title: document.title || '',
        desc: meta('description') || meta('og:description'),
        h1: (document.querySelector('h1')?.innerText || '').trim().slice(0, 200),
        text: (document.body?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 900),
      };
    });
    Object.assign(rec, info);
    await page.screenshot({ path: path.join(SHOTS, key + '.jpg'), type: 'jpeg', quality: 70 });
    rec.shot = `shots/${key}.jpg`;
    const hay = `${info.title} ${info.text}`;
    if (DEAD.some(re => re.test(hay))) rec.status = 'dead';
    else if (rec.httpStatus && rec.httpStatus >= 400) rec.status = rec.httpStatus === 403 || rec.httpStatus === 429 ? 'blocked' : 'dead';
    else if (info.text.length < 40 && !info.title) rec.status = 'unclear';
    else rec.status = 'up';
  } catch (e) {
    rec.error = String(e.message || e).split('\n')[0].slice(0, 200);
    rec.status = /ERR_NAME_NOT_RESOLVED|ERR_CONNECTION_REFUSED|ERR_CERT|ERR_SSL|ERR_ADDRESS_UNREACHABLE/.test(rec.error) ? 'dead' : 'unreachable';
    try { await page.screenshot({ path: path.join(SHOTS, key + '.jpg'), type: 'jpeg', quality: 70 }); rec.shot = `shots/${key}.jpg`; } catch {}
  }
  await ctx.close();
  return rec;
}

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const todo = urls.filter(u => !(onlyMissing && prev[u] && prev[u].status === 'up'));
  const results = { ...prev };
  let i = 0, done = 0;
  async function worker() {
    while (i < todo.length) {
      const u = todo[i++];
      results[u] = await one(browser, u);
      done++;
      if (done % 20 === 0) { fs.writeFileSync(OUT, JSON.stringify(results, null, 1)); console.log(`${done}/${todo.length}`); }
    }
  }
  await Promise.all(Array.from({ length: 6 }, worker));
  fs.writeFileSync(OUT, JSON.stringify(results, null, 1));
  await browser.close();
  const c = {}; Object.values(results).forEach(r => c[r.status] = (c[r.status] || 0) + 1);
  console.log('done', todo.length, c);
})();
