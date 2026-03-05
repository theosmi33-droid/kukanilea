import { test, expect } from '@playwright/test';

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
    // Shared dev login for all navigation tests
    await page.goto('/login');
    await page.fill('input[name="username"]', 'dev');
    await page.fill('input[name="password"]', 'dev');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/dashboard|\/$/);
  });

  for (const route of routes) {
    test(`Navigation to ${route.path} - Integrity Check`, async ({ page }) => {
      await page.goto(route.path);
      
      // 1. URL and Title Check
      await expect(page).toHaveURL(new RegExp(`${route.path.replace('/', '\\/')}$`));
      await expect(page.locator('h1')).toContainText(route.title);

      // 2. UX: Page Ready Signal (Task 156/157)
      await expect(page.locator('#main-content[data-page-ready="1"]')).toBeVisible();
      
      // 3. A11y: Basic Landmarks & Skip Target
      await expect(page.locator(route.landmark)).toBeVisible();
      await expect(page.locator('#main-content')).toBeVisible();

      // 4. UX: No "Loading" fragments visible after settle
      await expect(page.locator('body')).not.toContainText(/wird geladen|Lade Quellen/i);
    });
  }

  test('Skip Link functionality', async ({ page }) => {
    await page.goto('/dashboard');
    await page.keyboard.press('Tab'); // Usually the first element is the skip link
    const skipLink = page.locator('.skip-link');
    await expect(skipLink).toBeFocused();
    await page.keyboard.press('Enter');
    
    // Check if focus moved to main content
    const mainContent = page.locator('#app-main');
    await expect(mainContent).toBeFocused();
  });

  test('Sidebar toggle state persistence', async ({ page }) => {
    await page.goto('/dashboard');
    const sidebar = page.locator('.sidebar'); // Adjust selector if needed
    const toggle = page.locator('#sidebar-toggle'); // Adjust selector if needed
    
    if (await toggle.isVisible()) {
      await toggle.click();
      await page.waitForTimeout(300); // Wait for transition
      
      // Check if localStorage is updated (via JS check or attribute)
      const isCollapsed = await page.evaluate(() => localStorage.getItem('ks_sidebar_collapsed') === '1');
      expect(isCollapsed).toBeTruthy();
      
      await page.reload();
      await expect(page.locator('html')).toHaveClass(/sidebar-collapsed/);
    }
  });
});
