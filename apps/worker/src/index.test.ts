import { API_PATHS, type StatusResponse } from '@newseviday/contracts';
import { describe, expect, it } from 'vitest';

import { type Env, handleRequest } from './index';

const env: Env = {
  APP_VERSION: '0.1.0-test',
  RUNTIME_MODE: 'archive',
  AI_ENABLED: 'false',
  ALLOWED_ORIGINS: 'http://localhost:5173',
};

describe('worker API', () => {
  it('returns an honest static status when AI is disabled', async () => {
    const response = await handleRequest(
      new Request(`https://example.com${API_PATHS.status}`),
      env,
    );
    const payload = (await response.json()) as StatusResponse;

    expect(response.status).toBe(200);
    expect(payload.mode).toBe('archive');
    expect(payload.content.sourceCount).toBe(0);
    expect(payload.ai.state).toBe('static-only');
  });

  it('does not allow unknown origins in a preflight request', async () => {
    const request = new Request(`https://example.com${API_PATHS.status}`, {
      method: 'OPTIONS',
      headers: { Origin: 'https://untrusted.example' },
    });
    const response = await handleRequest(request, env);

    expect(response.status).toBe(403);
  });

  it('returns 404 for unknown routes', async () => {
    const response = await handleRequest(new Request('https://example.com/api/missing'), env);
    expect(response.status).toBe(404);
  });
});
