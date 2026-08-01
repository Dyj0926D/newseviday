import { describe, expect, it } from 'vitest';

import { HttpInputError, readJsonBody } from './http';

describe('request body guard', () => {
  it('accepts JSON within the configured byte limit', async () => {
    const request = new Request('https://example.com/api/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'hello' }),
    });

    await expect(readJsonBody(request, 1_024)).resolves.toEqual({ question: 'hello' });
  });

  it('rejects a body whose encoded bytes exceed the limit', async () => {
    const request = new Request('https://example.com/api/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: '超'.repeat(100) }),
    });

    try {
      await readJsonBody(request, 64);
      throw new Error('expected rejection');
    } catch (error) {
      expect(error).toBeInstanceOf(HttpInputError);
      expect(error).toMatchObject({ code: 'body_too_large', status: 413 });
    }
  });
});
