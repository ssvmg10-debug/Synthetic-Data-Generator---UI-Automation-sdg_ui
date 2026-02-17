
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const browser = await chromium.launch({ headless: false, slowMo: 100 });
    const context = await browser.newContext();
    const page = await context.newPage();
    
    console.log('🌐 Navigating to https://www.lg.com/in...');
    await page.goto('https://www.lg.com/in', { waitUntil: 'networkidle', timeout: 30000 });
    
    console.log('⏳ Waiting for page to fully render...');
    await page.waitForTimeout(5000);

    // Try to accept common cookie / consent banners so forms are visible
    try {
        const cookieSelectors = [
            "button:has-text('Accept')",
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "button:has-text('Agree')",
            "text='Accept all cookies'"
        ];
        for (const sel of cookieSelectors) {
            const btn = await page.$(sel);
            if (btn) {
                console.log('✅ Clicking cookie/consent button:', sel);
                await btn.click().catch(() => {});
                await page.waitForTimeout(1000);
                break;
            }
        }
    } catch (e) {
        console.log('Cookie banner handling skipped:', e.message);
    }

    console.log('📄 Extracting HTML content...');
    const html = await page.content();
    
    const outDir = process.env.OUTPUT_DIR || __dirname;
    fs.writeFileSync(path.join(outDir, 'page_content.html'), html, 'utf-8');
    console.log('✅ HTML extracted and saved successfully');
    console.log('📊 Content length: ' + html.length + ' characters');
    
    await browser.close();
})();
