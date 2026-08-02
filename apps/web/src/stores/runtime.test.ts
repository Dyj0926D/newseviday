// @vitest-environment jsdom
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useRuntimeStore } from './runtime';

const snapshot = {
  schemaVersion: '1.0.0',
  snapshotId: 'snapshot-test',
  generatedAt: '2026-08-01T00:00:00Z',
  pipelineRunId: 'pipeline-test',
  state: 'ready',
  sourceCount: 2,
  articles: [],
  evidence: [],
  briefs: [],
};

describe('runtime store degradation', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it('uses the Worker response envelope when the API is available', async () => {
    const meta = {
      requestId: 'req',
      generatedAt: '2026-08-01T00:00:00Z',
      version: 'test',
      durationMs: 1,
    };
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({
            ok: true,
            data: {
              product: 'NewsEviday',
              mode: 'warmup',
              content: { state: 'ready', updatedAt: null, sourceCount: 3, snapshotId: 'live' },
              ai: { state: 'static-only', provider: null, model: null },
              rag: { state: 'static-only', retrievalMode: null, corpusSnapshotId: null },
              protection: { persistentGuardrails: 'available', turnstile: 'enabled' },
            },
            meta,
          }),
        )
        .mockResolvedValueOnce(
          Response.json({
            ok: true,
            data: {
              schemaVersion: '1.0.0',
              mode: 'warmup',
              features: {
                ingestion: false,
                aiSummary: false,
                rag: false,
                trendBrief: false,
                turnstile: true,
              },
              limits: {
                dailyQuestionsPerIp: 3,
                globalDailyGenerations: 20,
                softBudgetDailyGenerations: 10,
                maxConcurrentGenerations: 2,
                monthlyBudgetCny: 35,
                hardBudgetCny: 50,
                requestBodyBytes: 32768,
                upstreamTimeoutMs: 20000,
              },
              protection: { turnstileSiteKey: 'public-site-key' },
            },
            meta,
          }),
        ),
    );
    const store = useRuntimeStore();

    await store.refresh();

    expect(store.requestState).toBe('success');
    expect(store.status?.content.sourceCount).toBe(3);
    expect(store.config?.features.turnstile).toBe(true);
  });

  it('falls back to the last static snapshot when the Worker is unavailable', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(Response.json(snapshot));
    vi.stubGlobal('fetch', fetchMock);
    const store = useRuntimeStore();

    await store.refresh();

    expect(store.requestState).toBe('static');
    expect(store.status?.content.snapshotId).toBe('snapshot-test');
    expect(store.status?.content.sourceCount).toBe(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('keeps online status when only the public runtime config is unavailable', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          ok: true,
          data: {
            product: 'NewsEviday',
            mode: 'archive',
            content: { state: 'ready', updatedAt: null, sourceCount: 2, snapshotId: 'live' },
            ai: { state: 'static-only', provider: null, model: null },
            rag: { state: 'static-only', retrievalMode: null, corpusSnapshotId: null },
            protection: { persistentGuardrails: 'available', turnstile: 'enabled' },
          },
          meta: {
            requestId: 'req',
            generatedAt: '2026-08-01T00:00:00Z',
            version: 'test',
            durationMs: 1,
          },
        }),
      )
      .mockRejectedValueOnce(new Error('runtime config unavailable'));
    vi.stubGlobal('fetch', fetchMock);
    const store = useRuntimeStore();

    await store.refresh();

    expect(store.requestState).toBe('success');
    expect(store.status?.content.snapshotId).toBe('live');
    expect(store.config).toBeNull();
  });
});
