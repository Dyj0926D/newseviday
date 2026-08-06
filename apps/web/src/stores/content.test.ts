// @vitest-environment jsdom
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useContentStore } from './content';

const snapshot = {
  schemaVersion: '1.0.0',
  snapshotId: 'snapshot-demo',
  generatedAt: '2026-08-02T04:00:00Z',
  pipelineRunId: 'pipeline-demo',
  state: 'ready',
  snapshotKind: 'demo',
  sourceCount: 1,
  sources: [],
  topics: [],
  articles: [],
  evidence: [],
  briefs: [],
};

describe('content store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it('loads and identifies the static demo snapshot', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json(snapshot)),
    );
    const store = useContentStore();

    await store.refresh();

    expect(store.state).toBe('ready');
    expect(store.isDemo).toBe(true);
    expect(store.snapshot?.snapshotId).toBe('snapshot-demo');
  });

  it('keeps the page in a safe error state when the snapshot is invalid', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ snapshotId: 'broken' })),
    );
    const store = useContentStore();

    await store.refresh();

    expect(store.state).toBe('error');
    expect(store.snapshot).toBeNull();
  });

  it('loads a historical snapshot through the bounded public archive manifest', async () => {
    const archived = {
      ...snapshot,
      snapshotId: 'snapshot-history',
      articles: [{ id: 'article-history' }],
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/data/current.json')) return Response.json(snapshot);
        if (url.endsWith('/data/archive/manifest.json')) {
          return Response.json({
            schemaVersion: '1.0.0',
            updatedAt: '2026-08-02T04:00:00Z',
            articles: [
              {
                id: 'article-history',
                title: '历史情报',
                originalTitle: 'Archived intelligence',
                sourceId: 'source-test',
                publishedAt: null,
                snapshotPath: 'versions/snapshot-history.json',
              },
            ],
          });
        }
        return Response.json(archived);
      }),
    );
    const store = useContentStore();

    await store.refresh();
    const result = await store.loadArchivedSnapshotForArticle('article-history');

    expect(result?.snapshotId).toBe('snapshot-history');
  });
});
