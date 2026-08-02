import { test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const outputDirectory = fileURLToPath(
  new URL('../../../design/reference/实现回归/P3-完整页面/', import.meta.url),
);

test('capture P3 implementation references', async ({ page }, testInfo) => {
  test.skip(process.env.CAPTURE_P3_REFERENCES !== '1', 'reference capture is opt-in');
  test.skip(testInfo.project.name !== 'desktop-chromium', 'capture once with desktop Chromium');
  test.setTimeout(90_000);
  await mkdir(outputDirectory, { recursive: true });

  const captures = [
    { path: '/product', width: 1440, height: 900, name: '产品介绍-1440.png' },
    { path: '/article/demo-semantic-agent', width: 1440, height: 900, name: '文章详情-1440.png' },
    { path: '/profile', width: 390, height: 844, name: '个人画像-390.png' },
    { path: '/brief', width: 390, height: 844, name: '趋势简报-390.png' },
  ];

  for (const capture of captures) {
    await page.setViewportSize({ width: capture.width, height: capture.height });
    await page.goto(capture.path);
    await page.locator('main').waitFor();
    await page.screenshot({ path: `${outputDirectory}${capture.name}`, fullPage: true });
  }
});
