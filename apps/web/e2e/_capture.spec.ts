import { test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const outputDirectory = fileURLToPath(
  new URL('../../../design/reference/实现回归/P6.5-文案与架构优化/', import.meta.url),
);

test('capture approved implementation references', async ({ page }, testInfo) => {
  test.skip(
    process.env.CAPTURE_IMPLEMENTATION_REFERENCES !== '1',
    'reference capture is opt-in',
  );
  test.skip(testInfo.project.name !== 'desktop-chromium', 'capture once with desktop Chromium');
  test.setTimeout(90_000);
  await mkdir(outputDirectory, { recursive: true });

  const captures = [
    { path: '/', width: 1440, height: 900, name: '首页-1440.png' },
    { path: '/product', width: 1440, height: 900, name: '产品与技术-1440.png' },
    { path: '/article/demo-semantic-agent', width: 1440, height: 900, name: '情报详情-1440.png' },
    { path: '/profile', width: 390, height: 844, name: '关注偏好-390.png' },
    { path: '/brief', width: 390, height: 844, name: '趋势简报-390.png' },
  ];

  for (const capture of captures) {
    await page.setViewportSize({ width: capture.width, height: capture.height });
    await page.goto(capture.path);
    await page.locator('main').waitFor();
    await page.screenshot({ path: `${outputDirectory}${capture.name}`, fullPage: true });
  }
});
