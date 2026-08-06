import type { Article } from '@newseviday/contracts';
import { describe, expect, it } from 'vitest';

import { translationStatus } from './intelligence';

const article = {
  language: 'en',
  ai: null,
} as Article;

describe('intelligence presentation', () => {
  it('does not claim that an untranslated source has been organized in Chinese', () => {
    expect(translationStatus(article)).toBe('英文原文待整理');
  });

  it('marks a foreign source ready only when both Chinese fields exist', () => {
    expect(
      translationStatus({
        ...article,
        ai: {
          provider: 'deepseek',
          titleZh: '中文标题',
          summaryZh: '中文导读',
          whyItMatters: '',
          keyPoints: [],
          model: 'test',
          promptVersion: 'test',
          generatedAt: '2026-08-06T00:00:00Z',
        },
      }),
    ).toBe('英文原文已整理');
  });
});
