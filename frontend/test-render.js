const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  
  // Track console logs
  let renderCount = 0;
  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('[EnhancedSpreadsheet]')) {
      renderCount++;
      console.log('Render #' + renderCount + ':', text);
    }
  });
  
  // Navigate to management-accounts page
  console.log('Loading page...');
  await page.goto('http://localhost:3001/management-accounts', {
    waitUntil: 'networkidle2',
    timeout: 15000
  });
  
  // Wait a bit to see if there are continuous re-renders
  await new Promise(resolve => setTimeout(resolve, 5000));
  
  console.log('Total renders after 5 seconds:', renderCount);
  
  if (renderCount > 10) {
    console.log('⚠️  POSSIBLE RENDER LOOP DETECTED');
  } else {
    console.log('✅ No render loop detected');
  }
  
  await browser.close();
})();
