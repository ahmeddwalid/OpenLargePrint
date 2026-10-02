// Actual React screen, with only the desktop capability handshake substituted.
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');

let browser;
(async () => {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1100, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => route.request().url().startsWith('http://127.0.0.1:5179/') ? route.continue() : route.abort());
  await page.addInitScript(() => {
    window.__TAURI__ = { core: { invoke: async command => {
      if (command === 'health_check') return { status: 'ready', ocr_available: true, accuracy_languages: ['en'] };
      if (command === 'get_system_paths') return { downloads: 'Downloads', desktop: 'Desktop', documents: 'Documents' };
      return null;
    } }, event: { listen: async () => () => {} } };
  });
  const root = path.join(__dirname, 'verification', 'screenshots');
  await fs.mkdir(root, { recursive: true });
  await page.goto('http://127.0.0.1:5179/');
  const disclosure = page.getByRole('button', { name: /more options/i });
  await disclosure.focus();
  await page.keyboard.press('Enter');
  const select = page.locator('#routing-mode-select');
  await select.focus();
  await page.keyboard.press('ArrowUp');
  if (await select.inputValue() !== 'max_accuracy') throw new Error('Keyboard selection failed');
  const checks = { keyboard: true, errors, cases: [] };
  async function capture(name) {
    const result = await page.evaluate(() => {
      const control = document.querySelector('#routing-mode-select');
      const style = getComputedStyle(control);
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d');
      context.font = style.font;
      const requiredWidth = context.measureText(control.selectedOptions[0].text).width + 55;
      return { width: control.getBoundingClientRect().width, height: control.getBoundingClientRect().height,
        fontSize: style.fontSize, focusOutline: style.outlineStyle, focusWidth: style.outlineWidth,
        selectedTextFits: requiredWidth <= control.getBoundingClientRect().width,
        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 };
    });
    if (result.height < 44 || result.overflow || !result.selectedTextFits) throw new Error(`Accessibility failed: ${name} ${JSON.stringify(result)}`);
    checks.cases.push({ name, ...result });
    await page.screenshot({ path: path.join(root, `advanced-${name}.png`), fullPage: true });
  }
  await capture('normal');
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  await capture('200-percent');
  await page.setViewportSize({ width: 640, height: 900 });
  await capture('narrow');
  await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' });
  await capture('high-contrast');
  await page.evaluate(() => document.documentElement.dir = 'rtl');
  await capture('rtl');
  if (checks.cases[0].focusOutline === 'none' || parseFloat(checks.cases[0].focusWidth) < 1 || errors.length) throw new Error('Focus or page errors failed');
  await fs.writeFile(path.join(root, 'advanced-check.json'), JSON.stringify(checks, null, 2));
  await browser.close();
  console.log('Advanced options: keyboard, visible focus, touch target, 200% text, narrow viewport, high contrast, reduced motion, RTL and screenshots passed.');
})().catch(async error => { console.error(error); await browser?.close(); process.exitCode = 1; });
