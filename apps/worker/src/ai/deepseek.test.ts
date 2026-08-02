import { describe, expect, it, vi } from 'vitest';

import type { DeepSeekConfig } from '../config';
import { AiProviderError, DeepSeekClient } from './deepseek';
import type { UsageRecord, UsageRecorder } from './types';

const enabledConfig: DeepSeekConfig = {
  enabled: true,
  apiKey: 'test-only-key',
  model: 'provider-model-id',
  baseUrl: 'https://api.deepseek.com',
  thinkingEnabled: false,
  timeoutMs: 1_000,
  maxRetries: 0,
};

class MemoryUsageRecorder implements UsageRecorder {
  records: UsageRecord[] = [];

  async record(record: UsageRecord): Promise<void> {
    this.records.push(record);
  }
}

describe('DeepSeekClient', () => {
  it('does not make a request when AI is disabled or unconfigured', async () => {
    const fetcher = vi.fn();
    const client = new DeepSeekClient({ ...enabledConfig, enabled: false, apiKey: null }, fetcher);

    await expect(
      client.complete({ messages: [{ role: 'user', content: 'hello' }], requestId: 'req-1' }),
    ).rejects.toMatchObject({ code: 'ai_unavailable', retryable: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('maps a completion and records token usage without leaking the key', async () => {
    const recorder = new MemoryUsageRecorder();
    const fetcher = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.headers).toMatchObject({ Authorization: 'Bearer test-only-key' });
      expect(JSON.parse(String(init?.body))).toMatchObject({
        model: 'provider-model-id',
        thinking: { type: 'disabled' },
      });
      return Response.json({
        id: 'chat-1',
        model: 'provider-model-id',
        choices: [{ finish_reason: 'stop', message: { content: 'answer' } }],
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      });
    });
    const client = new DeepSeekClient(enabledConfig, fetcher, recorder);

    const result = await client.complete({
      messages: [{ role: 'user', content: 'hello' }],
      requestId: 'req-2',
    });

    expect(result.content).toBe('answer');
    expect(result.usage.totalTokens).toBe(15);
    expect(recorder.records).toHaveLength(1);
    expect(JSON.stringify(recorder.records)).not.toContain('test-only-key');
  });

  it('explicitly enables thinking mode and omits unsupported temperature', async () => {
    const fetcher = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      expect(body.thinking).toEqual({ type: 'enabled' });
      expect(body).not.toHaveProperty('temperature');
      return Response.json({
        id: 'chat-thinking',
        choices: [{ finish_reason: 'stop', message: { content: 'answer' } }],
      });
    });
    const client = new DeepSeekClient({ ...enabledConfig, thinkingEnabled: true }, fetcher);

    await client.complete({
      messages: [{ role: 'user', content: 'hello' }],
      requestId: 'req-thinking',
      temperature: 0.1,
    });
  });

  it('classifies provider overload as retryable', async () => {
    const client = new DeepSeekClient(
      enabledConfig,
      vi.fn(async () => Response.json({ error: { message: 'overloaded' } }, { status: 503 })),
    );

    try {
      await client.complete({ messages: [{ role: 'user', content: 'hello' }], requestId: 'req-3' });
      throw new Error('expected rejection');
    } catch (error) {
      expect(error).toBeInstanceOf(AiProviderError);
      expect(error).toMatchObject({ code: 'upstream_error', retryable: true, status: 503 });
    }
  });

  it('passes through an upstream event stream', async () => {
    const recorder = new MemoryUsageRecorder();
    const body = new TextEncoder().encode(
      'data: {"choices":[],"usage":{"prompt_tokens":2,"completion_tokens":3,"total_tokens":5}}\n\ndata: [DONE]\n\n',
    );
    const client = new DeepSeekClient(
      enabledConfig,
      vi.fn(async () => new Response(body, { headers: { 'Content-Type': 'text/event-stream' } })),
      recorder,
    );

    const result = await client.stream({
      messages: [{ role: 'user', content: 'hello' }],
      requestId: 'req-stream',
    });
    expect(result.contentType).toBe('text/event-stream');
    expect(await new Response(result.body).text()).toContain('[DONE]');
    expect(recorder.records[0]?.usage.totalTokens).toBe(5);
    expect(recorder.records[0]?.estimatedCostCny).toBeNull();
  });
});
