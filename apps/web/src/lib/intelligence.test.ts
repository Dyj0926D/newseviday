import type { Article } from '@newseviday/contracts';
import { describe, expect, it } from 'vitest';

import { isChineseDisplayReady, sourceTypeLabel, translationStatus } from './intelligence';

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

  it('keeps untranslated foreign articles out of the default Chinese feed', () => {
    expect(isChineseDisplayReady(article)).toBe(false);
    expect(
      isChineseDisplayReady({
        ...article,
        ai: {
          provider: 'editorial',
          titleZh: '中文标题',
          summaryZh: '这是用于默认信息流展示的中文导读。',
          whyItMatters: '用于测试',
          keyPoints: ['要点一', '要点二'],
          model: '编辑整理',
          promptVersion: 'test',
          generatedAt: '2026-08-10T00:00:00Z',
        },
      }),
    ).toBe(true);
  });

  it('labels source roles without exposing internal evidence codes', () => {
    expect(sourceTypeLabel('official')).toBe('官方一手');
    expect(sourceTypeLabel('research_institute')).toBe('研究机构');
    expect(sourceTypeLabel('professional_media')).toBe('专业媒体');
    expect(sourceTypeLabel('independent_author')).toBe('作者观察');
  });
});
