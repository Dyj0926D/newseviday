import type { Article } from '@newseviday/contracts';
import { describe, expect, it } from 'vitest';

import {
  diversifyBySource,
  isWithinPublishedWindow,
  selectKeySignal,
  sortLatestArticles,
  summarizeVisibleFreshness,
} from './feedRanking';

function article(id: string, sourceId: string, score: number, eligible = false): Article {
  return {
    schemaVersion: '1.0.0',
    id,
    sourceId,
    canonicalUrl: `https://example.com/${id}`,
    language: 'en',
    collectedAt: '2026-08-06T00:00:00Z',
    publishedAt: '2026-08-06T00:00:00Z',
    facts: { title: id, authors: [], abstract: null },
    ai: null,
    evidenceIds: [],
    topicScores: {},
    contentScore: score,
    keySignal: {
      eligible,
      score,
      userValue: score,
      changeMagnitude: score,
      actionability: score,
      generality: score,
      freshness: score,
      reasons: [],
      gateFailures: [],
    },
    contentHash: id.padEnd(16, '0'),
  };
}

describe('feed ranking', () => {
  it('orders the latest feed by publication time before content score', () => {
    const older = article('older', 'openai', 0.99);
    older.publishedAt = '2026-07-10T00:00:00Z';
    const newer = article('newer', 'github', 0.4);
    newer.publishedAt = '2026-08-08T00:00:00Z';

    expect(sortLatestArticles([older, newer]).map((item) => item.id)).toEqual(['newer', 'older']);
  });

  it('uses the snapshot time as the recency window anchor', () => {
    const recent = article('recent', 'openai', 0.8);
    recent.publishedAt = '2026-08-08T00:00:00Z';
    const stale = article('stale', 'github', 0.8);
    stale.publishedAt = '2026-07-01T00:00:00Z';

    expect(isWithinPublishedWindow(recent, '2026-08-10T00:00:00Z', 30)).toBe(true);
    expect(isWithinPublishedWindow(stale, '2026-08-10T00:00:00Z', 30)).toBe(false);
  });

  it('reports freshness from the same Chinese-ready inventory shown in the default feed', () => {
    const untranslatedNewer = article('untranslated', 'mit', 0.8);
    untranslatedNewer.publishedAt = '2026-08-19T10:00:00Z';
    const translatedOlder = article('translated', 'github', 0.7);
    translatedOlder.publishedAt = '2026-08-18T01:00:00Z';
    translatedOlder.ai = {
      titleZh: '已整理标题',
      summaryZh: '这是一段已经完成中文整理并可在默认信息流展示的摘要内容。',
      whyItMatters: '用于验证默认信息流的时效口径。',
      keyPoints: ['口径一致', '只统计可见内容'],
      provider: 'editorial',
      model: 'editorial-v1',
      promptVersion: 'editorial-v1',
      generatedAt: '2026-08-19T10:00:00Z',
    };

    expect(
      summarizeVisibleFreshness([untranslatedNewer, translatedOlder], '2026-08-20T10:00:00Z'),
    ).toEqual({
      visibleCount: 1,
      recent24HourCount: 0,
      latestPublishedAt: translatedOlder.publishedAt,
    });
  });

  it('selects the highest eligible Key Signal without forcing an ineligible item', () => {
    const items = [article('a', 'arxiv', 0.95), article('b', 'openai', 0.82, true)];
    expect(selectKeySignal(items, '2026-08-06T12:00:00Z')?.id).toBe('b');
    expect(selectKeySignal(items.slice(0, 1), '2026-08-06T12:00:00Z')).toBeNull();
  });

  it('replaces an older Key Signal as soon as a newer article becomes eligible', () => {
    const older = article('older-signal', 'openai', 0.95, true);
    older.publishedAt = '2026-08-22T09:00:00Z';
    const newer = article('newer-signal', 'github', 0.68, true);
    newer.publishedAt = '2026-08-25T09:00:00Z';

    expect(selectKeySignal([older, newer], '2026-08-25T12:00:00Z')?.id).toBe('newer-signal');
  });

  it('does not retain a Key Signal after the five-day observation window', () => {
    const stale = article('stale-signal', 'openai', 0.95, true);
    stale.publishedAt = '2026-08-20T08:59:59Z';

    expect(selectKeySignal([stale], '2026-08-25T09:00:00Z')).toBeNull();
  });

  it('limits a source to three items on the first screen and avoids triples', () => {
    const items = [
      article('a1', 'arxiv', 0.9),
      article('a2', 'arxiv', 0.89),
      article('a3', 'arxiv', 0.88),
      article('a4', 'arxiv', 0.87),
      article('o1', 'openai', 0.8),
      article('o2', 'openai', 0.79),
      article('d1', 'databricks', 0.78),
      article('q1', 'qwen', 0.77),
      article('g1', 'github', 0.76),
    ];

    const ordered = diversifyBySource(items);
    expect(ordered.slice(0, 8).filter((item) => item.sourceId === 'arxiv')).toHaveLength(3);
    expect(
      ordered.some(
        (item, index) =>
          index >= 2 &&
          item.sourceId === ordered[index - 1]?.sourceId &&
          item.sourceId === ordered[index - 2]?.sourceId,
      ),
    ).toBe(false);
    expect(ordered.slice(0, 2).map((item) => item.sourceId)).toEqual(['arxiv', 'arxiv']);
  });

  it('counts the Key Signal source as part of the first screen quota', () => {
    const ordered = diversifyBySource(
      [
        article('a1', 'arxiv', 0.9),
        article('a2', 'arxiv', 0.89),
        article('a3', 'arxiv', 0.88),
        article('o1', 'openai', 0.8),
        article('d1', 'databricks', 0.79),
        article('q1', 'qwen', 0.78),
        article('g1', 'github', 0.77),
        article('h1', 'huggingface', 0.76),
      ],
      { leadingSourceIds: ['arxiv'] },
    );
    expect(ordered.slice(0, 7).filter((item) => item.sourceId === 'arxiv')).toHaveLength(2);
  });

  it('does not strand three articles from one source at the end of the full feed', () => {
    const ordered = diversifyBySource([
      article('a1', 'arxiv', 0.99),
      article('b1', 'github', 0.98),
      article('c1', 'qwen', 0.97),
      article('a2', 'arxiv', 0.96),
      article('a3', 'arxiv', 0.95),
      article('b2', 'github', 0.94),
      article('c2', 'qwen', 0.93),
      article('d1', 'databricks', 0.92),
      article('b3', 'github', 0.91),
      article('a4', 'arxiv', 0.9),
      article('a5', 'arxiv', 0.89),
      article('a6', 'arxiv', 0.88),
    ]);

    expect(
      ordered.some(
        (item, index) =>
          index >= 2 &&
          item.sourceId === ordered[index - 1]?.sourceId &&
          item.sourceId === ordered[index - 2]?.sourceId,
      ),
    ).toBe(false);
  });
});
