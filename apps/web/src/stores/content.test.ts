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
    vi.stubGlobal('fetch', vi.fn(async () => Response.json(snapshot)));
    const store = useContentStore();

    await store.refresh();

    expect(store.state).toBe('ready');
    expect(store.isDemo).toBe(true);
    expect(store.snapshot?.snapshotId).toBe('snapshot-demo');
  });

  it('keeps the page in a safe error state when the snapshot is invalid', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ snapshotId: 'broken' })));
    const store = useContentStore();

    await store.refresh();

    expect(store.state).toBe('error');
    expect(store.snapshot).toBeNull();
  });
});
