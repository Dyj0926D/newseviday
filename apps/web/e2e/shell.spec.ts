import { expect, test } from '@playwright/test';

const publicPaths = [
  '/',
  '/article/demo-article',
  '/ask',
  '/brief',
  '/profile',
  '/eval',
  '/status',
  '/product',
];

test('home displays the confirmed product heading', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: '发现变化，看见脉络' })).toBeVisible();
  await expect(page.getByRole('link', { name: '查看趋势简报' })).toBeVisible();
});

test('worker exposes the cost-safe archive status', async ({ request }) => {
  const response = await request.get('http://127.0.0.1:8787/api/status');
  expect(response.ok()).toBe(true);

  const payload = await response.json();
  expect(payload.ok).toBe(true);
  expect(payload.data.mode).toBe('archive');
  expect(payload.data.content.sourceCount).toBe(0);
  expect(payload.data.ai.state).toBe('static-only');
});

for (const path of publicPaths) {
  test(`${path} loads without horizontal page overflow`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('main')).toBeVisible();

    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasOverflow).toBe(false);
  });
}
