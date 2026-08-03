import { expect, test } from '@playwright/test';

const publicPaths = [
  '/',
  '/article/demo-semantic-agent',
  '/ask',
  '/brief',
  '/profile',
  '/eval',
  '/status',
  '/product',
];

test('latest intelligence search and topic filters are reflected in the URL', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: '发现变化，看见脉络' })).toBeVisible();

  await page.getByRole('button', { name: 'RAG 与评测' }).click();
  await expect(page).toHaveURL(/topic=rag-eval/);
  await expect(page.getByRole('heading', { name: 'RAG 评测开始进入持续交付门禁' })).toBeVisible();

  await page.getByPlaceholder('搜索主题、来源或关键信号').fill('GitHub');
  await page.getByRole('button', { name: '搜索', exact: true }).click();
  await expect(page).toHaveURL(/q=GitHub/);
  await expect(page.getByRole('heading', { name: '没有符合条件的情报' })).toBeVisible();
});

test('home, article and original evidence form a working route chain', async ({ page }) => {
  await page.goto('/?topic=rag-eval');
  await page.getByRole('link', { name: 'RAG 评测开始进入持续交付门禁', exact: true }).click();

  await expect(page).toHaveURL(/\/article\/demo-rag-eval$/);
  await expect(
    page.getByRole('heading', { level: 1, name: 'RAG 评测开始进入持续交付门禁' }),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: '查看原始来源' })).toHaveAttribute(
    'target',
    '_blank',
  );
  await expect(page.getByRole('heading', { name: '原始证据' })).toBeVisible();

  await page.goBack();
  await expect(page).toHaveURL(/topic=rag-eval/);
  await expect(page.getByRole('button', { name: 'RAG 与评测' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
});

test('trend brief links every evidence signal back to an article', async ({ page }) => {
  await page.goto('/brief');
  await expect(
    page.getByRole('heading', { level: 1, name: '把分散信号整理成可验证的趋势' }),
  ).toBeVisible();
  await expect(page.getByText('当前为趋势内容预览')).toBeVisible();

  const firstEvidence = page.locator('.trend-evidence a').first();
  await firstEvidence.click();
  await expect(page).toHaveURL(/\/article\/demo-/);
  await expect(page.getByText('AI 整理，请以原始来源为准')).toBeVisible();
});

test('optional profile saves locally and changes the recommendation view', async ({ page }) => {
  await page.goto('/profile');
  await page.getByPlaceholder('例如：AI 产品经理').fill('AI 产品经理');
  await page.getByRole('button', { name: 'Data Agent' }).click();
  await page.getByRole('button', { name: '保存并查看推荐' }).click();

  await expect(page).toHaveURL(/view=recommended/);
  await expect(page.getByRole('button', { name: '为你推荐' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(page.getByText(/与你关注的/).first()).toBeVisible();

  await page.goto('/profile');
  await expect(page.getByPlaceholder('例如：AI 产品经理')).toHaveValue('AI 产品经理');
  await expect(page.getByRole('button', { name: '智能整理暂不可用' })).toBeDisabled();
});

test('evidence question page keeps examples usable while generation is unavailable', async ({
  page,
}) => {
  await page.goto('/ask?article=demo-semantic-agent');
  await expect(
    page.getByRole('heading', { level: 1, name: '基于已收录情报继续追问' }),
  ).toBeVisible();
  await page.getByRole('button', { name: '统一语义层为什么重新受到关注？' }).click();
  await expect(page.locator('textarea')).toHaveValue('统一语义层为什么重新受到关注？');
  await expect(page.getByRole('button', { name: '暂未开放' })).toBeDisabled();
});

test('product narrative connects architecture, evaluation and status pages', async ({ page }) => {
  await page.goto('/product');
  await expect(
    page.getByRole('heading', { level: 1, name: '把信息变成可验证的判断' }),
  ).toBeVisible();
  await page.getByRole('link', { name: '评测' }).first().click();
  await expect(page).toHaveURL(/\/product#evaluation$/);
  await expect(
    page.getByRole('heading', { name: '评测覆盖内容管道、检索、回答和性能' }),
  ).toBeVisible();

  await page.getByRole('link', { name: '查看质量评测' }).click();
  await expect(page).toHaveURL(/\/eval$/);
  await expect(
    page.getByRole('heading', { level: 1, name: '用可复现评测约束检索质量' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: '小规模数据集实测结果' })).toBeVisible();
  await expect(page.getByText('96.15%')).toBeVisible();

  await page.goto('/status');
  await expect(
    page.getByRole('heading', { level: 1, name: '查看内容更新时间与可用能力' }),
  ).toBeVisible();
});

test('unknown path renders an explicit 404 and returns home', async ({ page }) => {
  await page.goto('/this-page-does-not-exist');
  await expect(page.getByRole('heading', { level: 1, name: '页面没有找到' })).toBeVisible();
  await page.getByRole('link', { name: '返回最新情报' }).click();
  await expect(page).toHaveURL(/\/$/);
});

test('six fixed acceptance viewports keep every public route readable', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'run once with the desktop browser');
  test.setTimeout(120_000);
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
    for (const path of publicPaths) {
      await page.goto(path);
      await expect(page.locator('main')).toBeVisible();
      const hasOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
      );
      expect(hasOverflow, `unexpected overflow at ${path} on ${viewport.width}px`).toBe(false);
    }
  }
});

test('mobile navigation opens and changes route', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-chromium', 'mobile interaction only');
  await page.goto('/');
  await page.getByRole('button', { name: '打开导航菜单' }).click();
  const drawer = page.getByRole('complementary', { name: '移动端导航' });
  await expect(drawer).toBeVisible();
  await drawer.getByRole('link', { name: '产品介绍' }).click();
  await expect(page).toHaveURL(/\/product$/);
});

test('worker exposes the safe content snapshot status', async ({ request }) => {
  const response = await request.get('http://127.0.0.1:8787/api/status');
  expect(response.ok()).toBe(true);

  const payload = await response.json();
  expect(payload.ok).toBe(true);
  expect(payload.data.mode).toBe('archive');
  expect(payload.data.content.sourceCount).toBe(6);
  expect(payload.data.ai.state).toBe('static-only');
});
