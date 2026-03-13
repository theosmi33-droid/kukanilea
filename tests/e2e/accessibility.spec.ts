import { test, expect } from '@playwright/test';
import { loginAsDev, waitForShellReady } from './support/uiStability';

test.describe('WCAG 2.1 AA accessibility checks', () => {
  test('keyboard navigation, focus visibility, aria labels, and contrast baseline', async ({ page }) => {
    await loginAsDev(page);
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await waitForShellReady(page);

    await page.keyboard.press('Tab');
    const skipLink = page.locator('.skip-link');
    await expect(skipLink).toBeFocused();
    await expect(skipLink).toBeVisible();

    await page.keyboard.press('Enter');
    await expect(page.locator('#app-main')).toBeFocused();

    const focusOutlineVisible = await page.evaluate(() => {
      const button = document.querySelector('#sidebar-toggle');
      if (!(button instanceof HTMLElement)) return false;
      button.focus();
      const style = window.getComputedStyle(button);
      const width = parseFloat(style.outlineWidth || '0');
      return width >= 2 && style.outlineStyle !== 'none';
    });
    expect(focusOutlineVisible).toBeTruthy();

    const missingAriaLabels = await page.evaluate(() => {
      const selectors = 'button, a, input:not([type="hidden"]), select, textarea, [role="button"]';
      const elements = Array.from(document.querySelectorAll(selectors));
      return elements
        .filter((el) => {
          if (el.getAttribute('aria-hidden') === 'true') return false;
          const label = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || (el.textContent || '').trim();
          return !label;
        })
        .slice(0, 5)
        .map((el) => el.tagName.toLowerCase());
    });
    expect(missingAriaLabels).toEqual([]);

    const contrastFailures = await page.evaluate(() => {
      const luminance = (v: number) => {
        const srgb = v / 255;
        return srgb <= 0.03928 ? srgb / 12.92 : Math.pow((srgb + 0.055) / 1.055, 2.4);
      };
      const parseRgb = (value: string) => {
        const m = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
        if (!m) return null;
        return [Number(m[1]), Number(m[2]), Number(m[3])] as const;
      };
      const ratio = (fg: readonly number[], bg: readonly number[]) => {
        const lf = 0.2126 * luminance(fg[0]) + 0.7152 * luminance(fg[1]) + 0.0722 * luminance(fg[2]);
        const lb = 0.2126 * luminance(bg[0]) + 0.7152 * luminance(bg[1]) + 0.0722 * luminance(bg[2]);
        const [light, dark] = lf > lb ? [lf, lb] : [lb, lf];
        return (light + 0.05) / (dark + 0.05);
      };

      const targets = ['body', '.nav-link', '.topbar-search-input', '.btn-primary', '.btn-secondary'];
      const failures: string[] = [];
      for (const selector of targets) {
        const el = document.querySelector(selector);
        if (!(el instanceof HTMLElement)) continue;
        const style = window.getComputedStyle(el);
        const fg = parseRgb(style.color);
        const bg = parseRgb(style.backgroundColor === 'rgba(0, 0, 0, 0)' ? window.getComputedStyle(document.body).backgroundColor : style.backgroundColor);
        if (!fg || !bg) continue;
        if (ratio(fg, bg) < 4.5) failures.push(selector);
      }
      return failures;
    });
    expect(contrastFailures).toEqual([]);
  });

  test('accessible dialogs and disclosure dropdown keyboard behavior', async ({ page }) => {
    await loginAsDev(page);

    await page.goto('/settings', { waitUntil: 'domcontentloaded' });
    await waitForShellReady(page);

    await page.evaluate(() => {
      const confirmFn = (window as { confirmUX?: (title: string, message: string) => void }).confirmUX;
      if (typeof confirmFn === 'function') {
        confirmFn('Bestätigung erforderlich', 'Dialogtest');
      }
    });

    const dialog = page.locator('#confirm-dialog-backdrop [role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute('aria-modal', 'true');

    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();

    const disclosure = page.locator('[data-disclosure-toggle]').first();
    await disclosure.focus();
    await page.keyboard.press('Enter');
    await expect(disclosure).toHaveAttribute('aria-expanded', 'false');
    await page.keyboard.press(' ');
    await expect(disclosure).toHaveAttribute('aria-expanded', 'true');
  });

  test('screen reader landmarks exist', async ({ page }) => {
    await loginAsDev(page);
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('main', { name: /seiteninhalt/i })).toBeVisible();
    await expect(page.getByRole('navigation', { name: /hauptnavigation/i })).toBeVisible();
    await expect(page.getByRole('banner', { name: /seitenkopf/i })).toBeVisible();
  });
});
