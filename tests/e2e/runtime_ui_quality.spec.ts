import { test, expect, type Page } from '@playwright/test';

const mainTabs = [
  '/dashboard',
  '/upload',
  '/projects',
  '/tasks',
  '/messenger',
  '/email',
  '/calendar',
  '/time',
  '/visualizer',
  '/settings',
];

async function loginAsDev(page: Page) {
  await page.goto('/login');
  await page.fill('input[name="username"]', 'dev');
  await page.fill('input[name="password"]', 'dev');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/dashboard|\/$/);
}

test.describe('runtime-ui enterprise UX quality', () => {
  test('main navigation smoke keeps semantic consistency on all main tabs', async ({ page }) => {
    await loginAsDev(page);

    for (const route of mainTabs) {
      await page.click(`a[href="${route}"]`);
      await expect(page).toHaveURL(new RegExp(`${route.replace('/', '\\/')}$`));

      const activeLink = page.locator(`.nav-link[data-route="${route}"]`);
      await expect(activeLink).toHaveAttribute('aria-current', 'page');
      await expect(activeLink).toHaveAttribute('data-nav-active', '1');
      await expect(page.locator('#main-content[data-page-ready="1"]')).toBeVisible();
    }
  });

  test('no endless loading copy on dashboard, upload and visualizer', async ({ page }) => {
    await loginAsDev(page);

    for (const route of ['/dashboard', '/upload', '/visualizer']) {
      await page.goto(route);
      await expect(page.locator('#main-content[data-page-ready="1"]')).toBeVisible();
      await expect(page.locator('body')).not.toContainText(/Lade\s+Quellen\.\.\.|wird geladen\.\.\./i);
    }
  });

  test('page ready selector is present after each tab navigation', async ({ page }) => {
    await loginAsDev(page);

    for (const route of mainTabs) {
      await page.goto(route);
      await expect(page.locator('#main-content')).toHaveAttribute('data-page-ready', '1');
    }
  });

  test('white mode remains enforced after navigation changes', async ({ page }) => {
    await loginAsDev(page);
    for (const route of ['/dashboard', '/settings', '/visualizer']) {
      await page.goto(route);
      await expect(page.locator('html')).toHaveClass(/light/);
    }
  });

  test('zero-cdn asset policy from runtime shell', async ({ page }) => {
    await loginAsDev(page);
    const srcs = await page.locator('script[src],link[href]').evaluateAll((nodes) =>
      nodes.map((n) => n.getAttribute('src') || n.getAttribute('href') || ''),
    );
    for (const source of srcs) {
      expect(source).not.toMatch(/^https?:\/\//i);
      expect(source.toLowerCase()).not.toContain('cdn.');
    }
  });

  test('visual baseline desktop dashboard', async ({ page }) => {
    await loginAsDev(page);
    await page.goto('/dashboard');
    await expect(page.locator('#main-content')).toHaveScreenshot('runtime-ui-dashboard-desktop.png', {
      maxDiffPixelRatio: 0.02,
    });
  });

  test('visual baseline mobile dashboard', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    await loginAsDev(page);
    await page.goto('/dashboard');
    await expect(page.locator('#main-content')).toHaveScreenshot('runtime-ui-dashboard-mobile.png', {
      maxDiffPixelRatio: 0.03,
    });
    await context.close();
  });

  test('visualizer recovers from source errors without endless skeleton copy', async ({ page }) => {
    await loginAsDev(page);
    await page.route('**/api/visualizer/sources', async (route) => {
      await route.abort('failed');
    });
    await page.goto('/visualizer');
    await expect(page.locator('#vz-stage')).toContainText(/Quellen konnten nicht geladen werden/i);
    await expect(page.locator('#vz-stage')).not.toContainText(/Lade Quellen/i);
  });
});
