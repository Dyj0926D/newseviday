import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { UsageRecord } from './ai/types';
import type { Env } from './config';
import {
  beginGeneration,
  GuardrailError,
  type GuardrailStore,
  verifyTurnstile,
} from './guardrails';

class MemoryGuardrailStore implements GuardrailStore {
  reserveResult: Awaited<ReturnType<GuardrailStore['reserve']>> = 'reserved';
  quotaAllowed = true;
  leaseAllowed = true;
  committedMicros = 0;
  failReserve = false;
  quotaCalls = 0;
  reservedEstimatedMicros: number | null = null;
  reservedTraceId: string | null = null;
  finalizations: Array<{
    requestId: string;
    leaseId: string | null;
    state: string;
    actualMicros: number;
    usage: UsageRecord | null;
  }> = [];

  async reserve(
    input: Parameters<GuardrailStore['reserve']>[0],
  ): Promise<Awaited<ReturnType<GuardrailStore['reserve']>>> {
    if (this.failReserve) throw new Error('d1 unavailable');
    this.reservedEstimatedMicros = input.estimatedMicros;
    this.reservedTraceId = input.traceId;
    return this.reserveResult;
  }

  async consumeQuotas(): Promise<boolean> {
    this.quotaCalls += 1;
    return this.quotaAllowed;
  }

  async acquireLease(): Promise<boolean> {
    return this.leaseAllowed;
  }

  async finalize(
    requestId: string,
    leaseId: string | null,
    state: 'settled' | 'released' | 'denied',
    actualMicros: number,
    _settledAt: string,
    usage: UsageRecord | null = null,
  ): Promise<void> {
    this.finalizations.push({ requestId, leaseId, state, actualMicros, usage });
  }

  async budgetSnapshot(): Promise<{ committedMicros: number }> {
    return { committedMicros: this.committedMicros };
  }
}

const baseEnv: Env = {
  RUNTIME_MODE: 'interview',
  IP_HASH_SECRET: 'test-ip-secret-at-least-16',
  TURNSTILE_ENABLED: 'false',
};

function generationRequest(headers: Record<string, string> = {}): Request {
  return new Request('https://example.com/api/ask', {
    method: 'POST',
    headers: {
      'CF-Connecting-IP': '203.0.113.10',
      'Idempotency-Key': 'test-request-1',
      ...headers,
    },
  });
}

describe('generation guardrails', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('fails closed when persistent storage cannot reserve the budget', async () => {
    const store = new MemoryGuardrailStore();
    store.failReserve = true;

    await expect(
      beginGeneration(generationRequest(), baseEnv, 'ask', 'trace-test', store),
    ).rejects.toMatchObject({
      code: 'guardrails_unavailable',
      status: 503,
    });
  });

  it('rejects duplicate idempotency keys before consuming quota', async () => {
    const store = new MemoryGuardrailStore();
    store.reserveResult = 'duplicate';

    await expect(
      beginGeneration(generationRequest(), baseEnv, 'ask', 'trace-test', store),
    ).rejects.toMatchObject({
      code: 'request_conflict',
      status: 409,
    });
    expect(store.quotaCalls).toBe(0);
  });

  it('stops at the hard monthly budget before consuming quota', async () => {
    const store = new MemoryGuardrailStore();
    store.reserveResult = 'budget_exceeded';

    await expect(
      beginGeneration(generationRequest(), baseEnv, 'ask', 'trace-test', store),
    ).rejects.toMatchObject({
      code: 'budget_paused',
      status: 503,
    });
    expect(store.quotaCalls).toBe(0);
  });

  it('does not consume daily quota when concurrency is already full', async () => {
    const store = new MemoryGuardrailStore();
    store.leaseAllowed = false;

    await expect(
      beginGeneration(generationRequest(), baseEnv, 'ask', 'trace-test', store),
    ).rejects.toMatchObject({
      code: 'rate_limited',
      retryAfterSeconds: 10,
    });
    expect(store.quotaCalls).toBe(0);
    expect(store.finalizations[0]).toMatchObject({ state: 'denied', leaseId: null });
  });

  it('releases the lease and reservation when daily quota is exhausted', async () => {
    const store = new MemoryGuardrailStore();
    store.quotaAllowed = false;

    await expect(
      beginGeneration(generationRequest(), baseEnv, 'ask', 'trace-test', store),
    ).rejects.toMatchObject({
      code: 'rate_limited',
    });
    expect(store.quotaCalls).toBe(1);
    expect(store.finalizations[0]?.state).toBe('denied');
    expect(store.finalizations[0]?.leaseId).toBeTruthy();
  });

  it('settles recorded token cost exactly once', async () => {
    const store = new MemoryGuardrailStore();
    const reservation = await beginGeneration(
      generationRequest(),
      baseEnv,
      'ask',
      'trace-test',
      store,
    );
    const usage: UsageRecord = {
      requestId: 'provider-request',
      provider: 'deepseek',
      model: 'test-model',
      usage: { promptTokens: 100, completionTokens: 50, totalTokens: 150 },
      estimatedCostCny: 0.012345,
      recordedAt: new Date().toISOString(),
    };

    await reservation.usageRecorder.record(usage);
    await reservation.finish(true);

    expect(store.finalizations).toHaveLength(1);
    expect(store.finalizations[0]).toMatchObject({
      requestId: 'test-request-1',
      state: 'settled',
      actualMicros: 12_345,
      usage: { model: 'test-model', usage: { promptTokens: 100, completionTokens: 50 } },
    });
    expect(store.reservedTraceId).toBe('trace-test');
  });

  it('charges the conservative reserve when a model call has no usage payload', async () => {
    const store = new MemoryGuardrailStore();
    const reservation = await beginGeneration(
      generationRequest(),
      baseEnv,
      'ask',
      'trace-test',
      store,
    );

    await reservation.finish(true);

    expect(store.finalizations[0]).toMatchObject({ state: 'settled', actualMicros: 100_000 });
  });

  it('raises the reserve when configured token prices imply a higher worst-case cost', async () => {
    const store = new MemoryGuardrailStore();

    await beginGeneration(
      generationRequest(),
      {
        ...baseEnv,
        DEEPSEEK_INPUT_CNY_PER_MILLION: '10',
        DEEPSEEK_OUTPUT_CNY_PER_MILLION: '20',
      },
      'ask',
      'trace-test',
      store,
    );

    expect(store.reservedEstimatedMicros).toBe(430_000);
  });

  it('releases the reserve when retrieval refuses before a model call', async () => {
    const store = new MemoryGuardrailStore();
    const reservation = await beginGeneration(
      generationRequest(),
      baseEnv,
      'ask',
      'trace-test',
      store,
    );

    await reservation.finish(false);

    expect(store.finalizations[0]).toMatchObject({ state: 'released', actualMicros: 0 });
  });
});

describe('Turnstile validation', () => {
  const env: Env = {
    ...baseEnv,
    TURNSTILE_ENABLED: 'true',
    TURNSTILE_SITE_KEY: 'test-site-key',
    TURNSTILE_SECRET: 'test-secret',
    TURNSTILE_HOSTNAMES: 'example.com',
  };

  it('requires a token when verification is enabled', async () => {
    await expect(verifyTurnstile(generationRequest(), env, '203.0.113.10')).rejects.toBeInstanceOf(
      GuardrailError,
    );
  });

  it('accepts only a successful generate action from an allowed hostname', async () => {
    const fetcher = vi.fn(async () =>
      Response.json({ success: true, action: 'generate', hostname: 'example.com' }),
    );

    await expect(
      verifyTurnstile(
        generationRequest({ 'X-Turnstile-Token': 'valid-token' }),
        env,
        '203.0.113.10',
        fetcher,
      ),
    ).resolves.toBeUndefined();
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it('rejects a token issued for a different hostname', async () => {
    const fetcher = vi.fn(async () =>
      Response.json({ success: true, action: 'generate', hostname: 'attacker.example' }),
    );

    await expect(
      verifyTurnstile(
        generationRequest({ 'X-Turnstile-Token': 'wrong-host-token' }),
        env,
        '203.0.113.10',
        fetcher,
      ),
    ).rejects.toMatchObject({ code: 'verification_failed', status: 403 });
  });

  it('treats an invalid Siteverify response as unavailable protection', async () => {
    const fetcher = vi.fn(async () => new Response('gateway error', { status: 502 }));

    await expect(
      verifyTurnstile(
        generationRequest({ 'X-Turnstile-Token': 'valid-shape-token' }),
        env,
        '203.0.113.10',
        fetcher,
      ),
    ).rejects.toMatchObject({ code: 'guardrails_unavailable', status: 503 });
  });
});
