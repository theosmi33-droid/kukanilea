import { test, expect } from '@playwright/test';

test.describe('Sovereign navigation', () => {
  const routes = [
    '/dashboard',
    '/upload',
    '/projects',
    '/tasks',
    '/messenger',
    '/email',
    '/calendar',
    '/time',
    '/visualizer',
    '/settings'
  ];

  for (const route of routes) {
    test(`route responds and renders ${route}`, async ({ page }) => {
      const response = await page.goto(route);
      const status = response?.status() ?? 0;
      expect([200, 302]).toContain(status);
      await expect(page.locator('body')).toContainText(/KUKANILEA|Dashboard|Upload|Projekt|Aufgabe|Kalender|Einstellungen|Login|Anmelden/i);
    });
  }
});


test('deep links stay routable', async ({ page }) => {
  const deepLinks = [
    '/dashboard#quick-actions',
    '/dashboard?panel=reminders#reminders',
    '/projects?view=kanban',
  ];

  for (const link of deepLinks) {
    const response = await page.goto(link);
    const status = response?.status() ?? 0;
    expect([200, 302]).toContain(status);
  }
});
