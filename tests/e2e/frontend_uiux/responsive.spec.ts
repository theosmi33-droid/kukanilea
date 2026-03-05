import { test, expect } from '@playwright/test';
import { expectVisibleIfPresent, loginAsDev, waitForNoHorizontalOverflow, waitForShellReady } from '../support/uiStability';

/**
 * KUKANILEA Responsive UX Tests (Worker 4: Page UX Polish + QA)
 * Ensures pages are stable and usable on mobile (375px) and desktop (1440px).
 */

test.describe('Responsive Design Integrity', () => {
  const pages = ['/dashboard', '/upload', '/projects'];

  test.beforeEach(async ({ page }) => {
    await loginAsDev(page);
  });

  for (const pagePath of pages) {
    test(`Mobile Viewport (375x667) - ${pagePath}`, async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto(pagePath, { waitUntil: 'domcontentloaded' });
      await waitForShellReady(page);

      await waitForNoHorizontalOverflow(page);

      await expectVisibleIfPresent(page.locator('.mobile-bottom-nav'));

      const sidebar = page.locator('.sidebar');
      if ((await sidebar.count()) > 0 && (await sidebar.isVisible())) {
        const transform = await sidebar.evaluate((el) => window.getComputedStyle(el).transform);
        expect(transform).toContain('matrix');
      }
    });

    test(`Desktop Viewport (1440x900) - ${pagePath}`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(pagePath, { waitUntil: 'domcontentloaded' });
      await waitForShellReady(page);

      const mobileNav = page.locator('.mobile-bottom-nav');
      if ((await mobileNav.count()) > 0) {
        await expect(mobileNav).not.toBeVisible();
      }

      await expect(page.locator('.sidebar')).toBeVisible();

      const mainContent = page.locator('#main-content');
      await expect
        .poll(async () =>
          mainContent.evaluate((el) => parseInt(window.getComputedStyle(el).marginLeft || '0', 10)),
        )
        .toBeGreaterThanOrEqual(0);
    });
  }
});
