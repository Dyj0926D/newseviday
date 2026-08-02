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
  await expect(page.getByText('当前展示产品演示快照')).toBeVisible();
  await expect(page.getByRole('heading', { level: 3, name: '语义层开始成为 Data Agent 的可信指标入口' })).toBeVisible();
});

test('home search and topic filters are reflected in the URL', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'RAG 与评测' }).click();
  await expect(page).toHaveURL(/topic=rag-eval/);
  await expect(page.getByRole('heading', { name: 'RAG 评测开始进入持续交付门禁' })).toBeVisible();

  await page.getByPlaceholder('搜索主题、来源或关键信号').fill('GitHub');
  await page.getByRole('button', { name: '搜索', exact: true }).click();
  await expect(page).toHaveURL(/q=GitHub/);
  await expect(page.getByRole('heading', { name: '没有符合条件的情报' })).toBeVisible();
});

test('recommended view uses a restorable URL state', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '为你推荐' }).click();
  await expect(page).toHaveURL(/view=recommended/);
  await expect(page.getByRole('button', { name: '为你推荐' })).toHaveAttribute('aria-pressed', 'true');
});

test('six fixed acceptance viewports keep the home readable', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'run once with the desktop browser');
  const viewports = [
    { width: 360, height: 800 },
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1024, height: 768 },
    { width: 1280, height: 800 },
    { width: 1440, height: 900 },
  ];

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1, name: '发现变化，看见脉络' })).toBeVisible();
    await expect(page.locator('.intelligence-feed')).toBeVisible();
    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasOverflow, `unexpected overflow at ${viewport.width}px`).toBe(false);
  }
});

test('mobile navigation opens, traps the workflow and changes route', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-chromium', 'mobile interaction only');
  await page.goto('/');
  await page.getByRole('button', { name: '打开导航菜单' }).click();
  const drawer = page.getByRole('complementary', { name: '移动端导航' });
  await expect(drawer).toBeVisible();
  await drawer.getByRole('link', { name: '产品介绍' }).click();
  await expect(page).toHaveURL(/\/product$/);
});

test('worker exposes the cost-safe archive status', async ({ request }) => {
  const response = await request.get('http://127.0.0.1:8787/api/status');
  expect(response.ok()).toBe(true);

  const payload = await response.json();
  expect(payload.ok).toBe(true);
  expect(payload.data.mode).toBe('archive');
  expect(payload.data.content.sourceCount).toBe(6);
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
