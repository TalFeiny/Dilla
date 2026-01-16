import { test, expect } from '@playwright/test';

const appUrl = 'http://localhost:3001'; // frontend dev

test.describe('Theme toggle', () => {
  test('switches day/night and persists', async ({ page }) => {
    await page.goto(appUrl);

    // default -> night
    await expect(page.locator('html')).toHaveAttribute('data-theme', /night|NIGHT/);

    // toggle to day
    await page.getByRole('button', { name: /Switch to Day|Day/i }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'day');

    // localStorage persisted
    const stored = await page.evaluate(() => localStorage.getItem('theme'));
    expect(stored).toBe('day');

    // reload keeps day
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'day');
  });

  test('applies CSS variables to surfaces', async ({ page }) => {
    await page.goto(appUrl);
    // Ensure day for predictable values
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'day');
      localStorage.setItem('theme', 'day');
    });
    await page.reload();

    const surface = page.locator('.surface-3d').first();
    await expect(surface).toBeVisible();

    const styles = await surface.evaluate((el) => {
      const s = getComputedStyle(el as HTMLElement);
      return {
        bg: s.backgroundColor,
        border: s.borderTopColor,
        shadow: s.boxShadow,
      };
    });

    expect(styles.shadow).not.toBe('none');
    expect(styles.border).not.toBe('rgba(0, 0, 0, 0)');
  });
});
