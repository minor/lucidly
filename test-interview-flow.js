const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Create screenshots directory
  const screenshotsDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir);
  }

  try {
    console.log('Step 1: Navigating to http://localhost:3000/interview/create');
    await page.goto('http://localhost:3000/interview/create');
    await page.waitForLoadState('networkidle');
    
    console.log('Taking screenshot 1: Initial page');
    await page.screenshot({ path: path.join(screenshotsDir, '1-initial-page.png'), fullPage: true });

    console.log('Step 2: Filling in the "Interview Title" field');
    const titleInput = page.locator('input[placeholder*="Senior Frontend"]');
    await titleInput.fill('Two Sum Test');
    await page.waitForTimeout(500);

    console.log('Step 3: Clicking "Next: Add Challenges" button');
    const nextButton = page.locator('button:has-text("Next: Add Challenges")');
    await nextButton.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    console.log('Taking screenshot 2: Challenges step');
    await page.screenshot({ path: path.join(screenshotsDir, '2-challenges-step.png'), fullPage: true });

    console.log('Step 4: Filling in challenge Title');
    const challengeTitleInput = page.locator('input[placeholder*="title" i], input[name*="title" i]').first();
    await challengeTitleInput.fill('Two Sum');
    await page.waitForTimeout(500);

    console.log('Step 5: Filling in Description');
    const descriptionInput = page.locator('textarea[placeholder*="description" i], textarea[name*="description" i], input[placeholder*="description" i]').first();
    await descriptionInput.fill('Implement two sum');
    await page.waitForTimeout(500);

    console.log('Taking screenshot 3: Filled form');
    await page.screenshot({ path: path.join(screenshotsDir, '3-filled-form.png'), fullPage: true });

    console.log('\nAll screenshots saved to:', screenshotsDir);
    console.log('✓ 1-initial-page.png');
    console.log('✓ 2-challenges-step.png');
    console.log('✓ 3-filled-form.png');

  } catch (error) {
    console.error('Error during test:', error);
    await page.screenshot({ path: path.join(screenshotsDir, 'error.png'), fullPage: true });
  } finally {
    await browser.close();
  }
})();
