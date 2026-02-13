
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const browser = await chromium.launch({ headless: true, slowMo: 100 });
    const context = await browser.newContext();
    const page = await context.newPage();
    
    console.log('🌐 Navigating to https://www.lg.com/in...');
    await page.goto('https://www.lg.com/in', { waitUntil: 'networkidle', timeout: 30000 });
    
    console.log('⏳ Waiting for page to fully render...');
    await page.waitForTimeout(2000);

    console.log('📄 Extracting HTML content...');
    const html = await page.content();
    
    const outDir = process.env.OUTPUT_DIR || __dirname;
    fs.writeFileSync(path.join(outDir, 'page_content.html'), html, 'utf-8');
    console.log('✅ HTML extracted and saved successfully');
    console.log('📊 Content length: ' + html.length + ' characters');
    
    await browser.close();
})();
