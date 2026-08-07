import type { Article } from '@newseviday/contracts';
import { describe, expect, it } from 'vitest';

import { diversifyBySource, selectKeySignal } from './feedRanking';

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
  it('selects the highest eligible Key Signal without forcing an ineligible item', () => {
    const items = [article('a', 'arxiv', 0.95), article('b', 'openai', 0.82, true)];
    expect(selectKeySignal(items)?.id).toBe('b');
    expect(selectKeySignal(items.slice(0, 1))).toBeNull();
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
