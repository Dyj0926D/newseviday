import { assertContentSnapshot } from '@newseviday/contracts';
import { describe, expect, it } from 'vitest';

import snapshot from '../public/data/current.json';

describe('published static snapshot', () => {
  it('conforms to the shared runtime contract', () => {
    expect(() => assertContentSnapshot(snapshot)).not.toThrow();
    expect(snapshot.snapshotKind).toBe('production');
    expect(snapshot.sources).toHaveLength(snapshot.sourceCount);
    expect(snapshot.articles).toHaveLength(40);
    expect(snapshot.articles.some((article) => Boolean(article.ai?.whyItMatters))).toBe(true);
  });
});
