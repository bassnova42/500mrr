// Render assets/banner.src.html to assets/banner.jpg (1280x640 @2x). Usage: node tools/banner.js
const { chromium } = require('playwright-core');
const path = require('path');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: 2 });
  await page.goto('file://' + path.resolve(__dirname, '../assets/banner.src.html'), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.resolve(__dirname, '../assets/banner.jpg'), type: 'jpeg', quality: 85 });
  await browser.close();
})();
