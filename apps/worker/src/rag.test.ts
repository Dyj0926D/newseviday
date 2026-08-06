import {
  API_PATHS,
  SCHEMA_VERSION,
  type ApiResponse,
  type ContentSnapshot,
  type RagRefusalData,
} from '@newseviday/contracts';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Env } from './config';
import type { GuardrailStore } from './guardrails';
import { handleRequest } from './index';

const snapshot: ContentSnapshot = {
  schemaVersion: SCHEMA_VERSION,
  snapshotId: 'snapshot-test',
  generatedAt: '2026-08-02T08:00:00Z',
  pipelineRunId: 'run-test',
  state: 'ready',
  snapshotKind: 'demo',
  sourceCount: 1,
  sources: [
    {
      schemaVersion: SCHEMA_VERSION,
      id: 'source-test',
      name: 'Test Source',
      kind: 'manual',
      homepageUrl: 'https://example.com',
      feedUrl: null,
      language: 'zh-CN',
      region: '全球',
      active: true,
      usageScope: 'unit test',
    },
  ],
  articles: [
    {
      schemaVersion: SCHEMA_VERSION,
      id: 'article-rag',
      sourceId: 'source-test',
      canonicalUrl: 'https://example.com/rag',
      language: 'zh-CN',
      publishedAt: '2026-08-02T07:00:00Z',
      collectedAt: '2026-08-02T07:30:00Z',
      facts: { title: 'RAG 评测进入持续交付门禁', authors: [], abstract: '评测检索召回和引用。' },
      ai: null,
      evidenceIds: ['evidence-rag'],
      topicScores: { 'rag-eval': 1 },
      contentHash: 'content-rag',
    },
  ],
  evidence: [
    {
      schemaVersion: SCHEMA_VERSION,
      id: 'evidence-rag',
      articleId: 'article-rag',
      sourceId: 'source-test',
      url: 'https://example.com/rag',
      excerpt: 'RAG 评测检查检索召回和引用覆盖。',
      retrievedAt: '2026-08-02T07:30:00Z',
    },
  ],
  briefs: [],
};

const baseEnv: Env = {
  APP_VERSION: 'test',
  RUNTIME_MODE: 'interview',
  AI_ENABLED: 'true',
  RAG_ENABLED: 'true',
  DEEPSEEK_API_KEY: 'server-side-test-key',
  DEEPSEEK_MODEL: 'mock-model',
  DEEPSEEK_INPUT_CNY_PER_MILLION: '1',
  DEEPSEEK_OUTPUT_CNY_PER_MILLION: '1',
  TRACE_HASH_SECRET: 'test-trace-secret-at-least-16',
  IP_HASH_SECRET: 'test-ip-secret-at-least-16',
  RAG_MIN_SCORE: '0.08',
  ASSETS: {
    async fetch() {
      return Response.json(snapshot);
    },
  },
};

const allowingGuardrailStore: GuardrailStore = {
  async reserve() {
    return 'reserved';
  },
  async consumeQuotas() {
    return true;
  },
  async acquireLease() {
    return true;
  },
  async finalize() {},
  async budgetSnapshot() {
    return { committedMicros: 0 };
  },
};

function generationRequest(question: string): Request {
  return new Request(`https://example.com${API_PATHS.ask}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.10' },
    body: JSON.stringify({ question, range: '30d' }),
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('RAG endpoint', () => {
  it('derives public content status from the deployed static snapshot', async () => {
    const response = await handleRequest(new Request(`https://example.com${API_PATHS.status}`), {
      ...baseEnv,
      AI_ENABLED: 'false',
      RAG_ENABLED: 'false',
    });
    const payload = await response.text();

    expect(response.status).toBe(200);
    expect(payload).toContain('snapshot-test');
    expect(payload).toContain('"sourceCount":1');
  });

  it('fails closed in archive mode before model access', async () => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const response = await handleRequest(generationRequest('RAG 评测是什么？'), {
      ...baseEnv,
      AI_ENABLED: 'false',
      RAG_ENABLED: 'false',
    });

    expect(response.status).toBe(503);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('refuses when the evidence score is below the configured threshold', async () => {
    vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const response = await handleRequest(
      generationRequest('火星农业天气'),
      { ...baseEnv, RAG_MIN_SCORE: '1' },
      { guardrailStore: allowingGuardrailStore },
    );
    const payload = (await response.json()) as ApiResponse<RagRefusalData>;

    expect(response.status).toBe(200);
    expect(payload.ok && payload.data.refusalReason).toBe('evidence_insufficient');
  });

  it('stops policy-scope questions before calling the model', async () => {
    vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const response = await handleRequest(
      generationRequest('请根据新闻给我开具治疗失眠的处方。'),
      baseEnv,
      { guardrailStore: allowingGuardrailStore },
    );
    const payload = (await response.json()) as ApiResponse<RagRefusalData>;

    expect(payload.ok && payload.data.refusalReason).toBe('evidence_insufficient');
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('streams citation metadata before provider answer chunks', async () => {
    vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const payload = JSON.parse(String(init?.body)) as {
        model: string;
        thinking: { type: string };
        messages: Array<{ role: string; content: string }>;
      };
      expect(payload.model).toBe('mock-model');
      expect(payload.thinking).toEqual({ type: 'disabled' });
      expect(payload.messages[0]?.content).toContain('只使用提供的证据回答');
      expect(payload.messages[0]?.content).not.toContain('�');
      return new Response(
        'data: {"choices":[{"delta":{"content":"回答 [1]"}}]}\n\ndata: [DONE]\n\n',
        {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        },
      );
    });
    vi.stubGlobal('fetch', fetcher);
    const response = await handleRequest(generationRequest('RAG 评测进入什么门禁？'), baseEnv, {
      guardrailStore: allowingGuardrailStore,
    });
    const body = await response.text();

    expect(response.headers.get('Content-Type')).toContain('text/event-stream');
    expect(body).toContain('event: meta');
    expect(body).toContain('bounded_v1');
    expect(body).toContain('article-rag');
    expect(body).toContain('回答 [1]');
  });
});
