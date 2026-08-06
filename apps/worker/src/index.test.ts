import {
  API_PATHS,
  type ApiError,
  type RuntimeConfigResponse,
  type StatusResponse,
} from '@newseviday/contracts';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { type Env, handleRequest } from './index';

const env: Env = {
  APP_VERSION: '0.1.0-test',
  RUNTIME_MODE: 'archive',
  AI_ENABLED: 'false',
  ALLOWED_ORIGINS: 'http://localhost:5173',
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('worker API', () => {
  it('returns an honest static status when AI is disabled', async () => {
    const response = await handleRequest(
      new Request(`https://example.com${API_PATHS.status}`),
      env,
    );
    const payload = (await response.json()) as StatusResponse;

    expect(response.status).toBe(200);
    expect(response.headers.get('Strict-Transport-Security')).toContain('max-age=31536000');
    expect(response.headers.get('Cross-Origin-Opener-Policy')).toBe('same-origin');
    expect(payload.ok).toBe(true);
    expect(payload.data.mode).toBe('archive');
    expect(payload.data.content.sourceCount).toBe(0);
    expect(payload.data.ai.state).toBe('static-only');
    expect(payload.data.rag.state).toBe('static-only');
    expect(payload.data.protection.persistentGuardrails).toBe('unavailable');
    expect(payload.meta.requestId).toBeTruthy();
    expect(payload.meta.version).toBe('0.1.0-test');
  });

  it('publishes safe runtime switches and limits without secrets', async () => {
    const response = await handleRequest(
      new Request(`https://example.com${API_PATHS.runtimeConfig}`),
      { ...env, DAILY_QUESTIONS_PER_IP: '5', DEEPSEEK_API_KEY: 'server-only-secret' },
    );
    const payload = (await response.json()) as RuntimeConfigResponse;

    expect(payload.data.features.aiSummary).toBe(false);
    expect(payload.data.limits.dailyQuestionsPerIp).toBe(5);
    expect(payload.data.limits.globalDailyGenerations).toBe(20);
    expect(JSON.stringify(payload)).not.toContain('server-only-secret');
  });

  it('does not allow unknown origins in a preflight request', async () => {
    const request = new Request(`https://example.com${API_PATHS.status}`, {
      method: 'OPTIONS',
      headers: { Origin: 'https://untrusted.example' },
    });
    const response = await handleRequest(request, env);
    const payload = (await response.json()) as ApiError;

    expect(response.status).toBe(403);
    expect(payload.error.code).toBe('origin_not_allowed');
  });

  it('returns a structured 405 error and Allow header', async () => {
    const response = await handleRequest(
      new Request(`https://example.com${API_PATHS.status}`, { method: 'POST' }),
      env,
    );
    const payload = (await response.json()) as ApiError;

    expect(response.status).toBe(405);
    expect(response.headers.get('Allow')).toContain('GET');
    expect(payload.error.code).toBe('method_not_allowed');
  });

  it('returns a structured 404 for unknown routes', async () => {
    const response = await handleRequest(new Request('https://example.com/api/missing'), env);
    const payload = (await response.json()) as ApiError;

    expect(response.status).toBe(404);
    expect(payload.error.code).toBe('not_found');
  });

  it('fails closed when a public numeric limit is invalid', async () => {
    const response = await handleRequest(
      new Request(`https://example.com${API_PATHS.runtimeConfig}`),
      { ...env, HARD_BUDGET_CNY: '999' },
    );
    const payload = (await response.json()) as ApiError;

    expect(response.status).toBe(503);
    expect(payload.error.code).toBe('invalid_configuration');
    expect(JSON.stringify(payload.error)).not.toContain('999');
  });

  it('fails closed when soft limits exceed their hard limits', async () => {
    const response = await handleRequest(
      new Request(`https://example.com${API_PATHS.runtimeConfig}`),
      { ...env, MONTHLY_BUDGET_CNY: '40', HARD_BUDGET_CNY: '35' },
    );
    const payload = (await response.json()) as ApiError;

    expect(response.status).toBe(503);
    expect(payload.error.code).toBe('invalid_configuration');
  });

  it('does not call the model when persistent guardrails are unavailable', async () => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const response = await handleRequest(
      new Request(`https://example.com${API_PATHS.profileEnhance}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'CF-Connecting-IP': '203.0.113.10',
        },
        body: JSON.stringify({ role: 'AI 产品经理', work: '', goal: '', description: '' }),
      }),
      {
        ...env,
        AI_ENABLED: 'true',
        DEEPSEEK_API_KEY: 'server-only-secret',
        DEEPSEEK_MODEL: 'test-model',
        DEEPSEEK_INPUT_CNY_PER_MILLION: '1',
        DEEPSEEK_OUTPUT_CNY_PER_MILLION: '1',
        IP_HASH_SECRET: 'test-ip-secret-at-least-16',
      },
    );
    const payload = (await response.json()) as ApiError;

    expect(response.status).toBe(503);
    expect(payload.error.code).toBe('guardrails_unavailable');
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('does not enable AI without explicit current token prices', async () => {
    const response = await handleRequest(new Request(`https://example.com${API_PATHS.status}`), {
      ...env,
      AI_ENABLED: 'true',
      DEEPSEEK_API_KEY: 'server-only-secret',
      DEEPSEEK_MODEL: 'test-model',
    });
    const payload = (await response.json()) as ApiError;

    expect(response.status).toBe(503);
    expect(payload.error.code).toBe('invalid_configuration');
  });
});
