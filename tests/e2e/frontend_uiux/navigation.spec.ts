import { test, expect } from '@playwright/test';
import { loginAsDev, waitForShellReady } from '../support/uiStability';

/**
 * KUKANILEA E2E Navigation Tests (Worker 4: Page UX Polish + QA)
 * Ensures consistent navigation, landmarks, and page-ready signals.
 */

test.describe('Core Page Navigation & UX Integrity', () => {
  const routes = [
    { path: '/dashboard', title: /Dashboard/i, landmark: 'main' },
    { path: '/upload', title: /Upload/i, landmark: 'main' },
    { path: '/projects', title: /Projekt/i, landmark: 'main' },
  ];

  test.beforeEach(async ({ page }) => {
    await loginAsDev(page);
  });

  for (const route of routes) {
    test(`Navigation to ${route.path} - Integrity Check`, async ({ page }) => {
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });

      await expect(page).toHaveURL(new RegExp(`${route.path.replace('/', '\\/')}$`));
      await expect(page.locator('h1')).toContainText(route.title);

      await waitForShellReady(page);

      await expect(page.locator(route.landmark)).toBeVisible();
      await expect(page.locator('#main-content')).toBeVisible();
    });
  }

  test('Skip Link functionality', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.keyboard.press('Tab');
    const skipLink = page.locator('.skip-link');
    await expect(skipLink).toBeFocused();
    await page.keyboard.press('Enter');

    const mainContent = page.locator('#app-main');
    await expect(mainContent).toBeFocused();
  });

  test('Sidebar toggle state persistence', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    const toggle = page.locator('#sidebar-toggle');

    if ((await toggle.count()) === 0) {
      test.info().annotations.push({ type: 'skip', description: 'Sidebar toggle unavailable in shell mode' });
      return;
    }

    await expect(toggle).toBeVisible();
    await toggle.click();

    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem('ks_sidebar_collapsed')))
      .toBe('1');

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('html')).toHaveClass(/sidebar-collapsed/);
  });
});
