// Rasterise the Phase 4 figure SVGs to PNG in a real browser (2x), then scripts/teoo_phase4_png.py adds the metadata chunk.
// usage: PLAYWRIGHT_DIR=<dir with node_modules/playwright> CHROME=<chrome-headless-shell> node teoo_phase4_rasterize.cjs FIG_DIR
const { chromium } = require(`${process.env.PLAYWRIGHT_DIR}/node_modules/playwright`);
const fs = require('fs');
const dir = process.argv[2];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME });
  const p = await b.newPage({ viewport: { width: 800, height: 420 }, deviceScaleFactor: 2 });
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith('.svg'))) {
    await p.setContent(`<body style="margin:0;background:#07070a">${fs.readFileSync(`${dir}/${f}`, 'utf8')}</body>`);
    await p.screenshot({ path: `${dir}/${f.replace('.svg', '.raw.png')}`, clip: { x: 0, y: 0, width: 800, height: 420 } });
    console.log(f);
  }
  await b.close();
})();
