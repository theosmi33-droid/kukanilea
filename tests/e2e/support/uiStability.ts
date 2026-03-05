import { expect, type Locator, type Page } from '@playwright/test';

export const DEV_CREDENTIALS = {
  username: 'dev',
  password: 'dev',
} as const;

export async function loginAsDev(page: Page): Promise<void> {
  await page.goto('/login', { waitUntil: 'domcontentloaded' });
  await page.getByRole('textbox', { name: /username/i }).fill(DEV_CREDENTIALS.username);
  await page.getByRole('textbox', { name: /password/i }).fill(DEV_CREDENTIALS.password);
  await Promise.all([
    page.waitForURL(/dashboard|\/$/, { waitUntil: 'networkidle' }),
    page.getByRole('button', { name: /anmelden|login|system betreten|submit/i }).click(),
  ]);
  await waitForShellReady(page);
}

export async function waitForShellReady(page: Page): Promise<void> {
  await expect(page.locator('#main-content')).toBeVisible();
  await expect(page.locator('#main-content')).toHaveAttribute('data-page-ready', '1');
  await expect(page.locator('body')).not.toContainText(/wird geladen|lade quellen/i);
}

export async function navigateViaSidebar(page: Page, route: string): Promise<void> {
  const navLink = page.locator(`a[href="${route}"]`).first();
  await expect(navLink).toBeVisible();
  await Promise.all([
    page.waitForURL(new RegExp(`${route.replace('/', '\\/')}$`), { waitUntil: 'networkidle' }),
    navLink.click(),
  ]);
  await waitForShellReady(page);
}

export async function waitForNoHorizontalOverflow(page: Page): Promise<void> {
  await expect
    .poll(async () =>
      page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
    )
    .toBeTruthy();
}

export async function expectVisibleIfPresent(locator: Locator): Promise<void> {
  if ((await locator.count()) > 0) {
    await expect(locator.first()).toBeVisible();
  }
}
