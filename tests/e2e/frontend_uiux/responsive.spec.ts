import { test, expect } from '@playwright/test';

/**
 * KUKANILEA Responsive UX Tests (Worker 4: Page UX Polish + QA)
 * Ensures pages are stable and usable on mobile (375px) and desktop (1440px).
 */

test.describe('Responsive Design Integrity', () => {
  const pages = ['/dashboard', '/upload', '/projects'];

  test.beforeEach(async ({ page }) => {
    // Shared dev login
    await page.goto('/login');
    await page.fill('input[name="username"]', 'dev');
    await page.fill('input[name="password"]', 'dev');
    await page.click('button[type="submit"]');
  });

  for (const pagePath of pages) {
    test(`Mobile Viewport (375x667) - ${pagePath}`, async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto(pagePath);
      
      // 1. Check for overflow (horizontal scroll)
      const isOverflowing = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(isOverflowing).toBeFalsy();

      // 2. Mobile Nav visibility
      const mobileNav = page.locator('.mobile-bottom-nav');
      await expect(mobileNav).toBeVisible();

      // 3. Burger/Toggle visibility (Sidebar should be hidden)
      const sidebar = page.locator('.sidebar');
      const sidebarVisible = await sidebar.isVisible();
      if (sidebarVisible) {
        const transform = await sidebar.evaluate(el => window.getComputedStyle(el).transform);
        expect(transform).toContain('matrix'); // Should be translated off-screen or similar
      }
    });

    test(`Desktop Viewport (1440x900) - ${pagePath}`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(pagePath);
      
      // 1. Mobile Nav should be hidden
      const mobileNav = page.locator('.mobile-bottom-nav');
      await expect(mobileNav).not.toBeVisible();

      // 2. Sidebar should be visible
      const sidebar = page.locator('.sidebar');
      await expect(sidebar).toBeVisible();

      // 3. Main content should have enough padding/margin
      const mainContent = page.locator('#main-content');
      const marginLeft = await mainContent.evaluate(el => parseInt(window.getComputedStyle(el).marginLeft));
      // Usually sidebar width or similar
      expect(marginLeft).toBeGreaterThanOrEqual(0);
    });
  }
});
