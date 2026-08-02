import {
  type ApiError,
  type ApiErrorCode,
  type ApiMeta,
  type ApiSuccess,
} from '@newseviday/contracts';

import { appVersion, type Env } from './config';

const SECURITY_HEADERS: Readonly<Record<string, string>> = {
  'Cache-Control': 'no-store',
  'Content-Type': 'application/json; charset=utf-8',
  'Cross-Origin-Resource-Policy': 'same-site',
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
};

export interface RequestContext {
  requestId: string;
  startedAt: number;
}

function safeRequestId(value: string | null): string {
  const normalized = value?.trim().slice(0, 64) ?? '';
  return /^[a-zA-Z0-9._-]+$/.test(normalized) ? normalized : crypto.randomUUID();
}

export function requestContext(request: Request): RequestContext {
  return {
    requestId: safeRequestId(request.headers.get('cf-ray') ?? request.headers.get('x-request-id')),
    startedAt: performance.now(),
  };
}

function meta(context: RequestContext, env: Env): ApiMeta {
  return {
    requestId: context.requestId,
    generatedAt: new Date().toISOString(),
    version: appVersion(env),
    durationMs: Math.max(0, Math.round(performance.now() - context.startedAt)),
  };
}

function responseHeaders(extra: HeadersInit = {}): Headers {
  const headers = new Headers(SECURITY_HEADERS);
  new Headers(extra).forEach((value, key) => headers.set(key, value));
  return headers;
}

export function success<T>(
  data: T,
  context: RequestContext,
  env: Env,
  init: ResponseInit = {},
): Response {
  const payload: ApiSuccess<T> = { ok: true, data, meta: meta(context, env) };
  return Response.json(payload, { ...init, headers: responseHeaders(init.headers) });
}

export function failure(
  code: ApiErrorCode,
  message: string,
  context: RequestContext,
  env: Env,
  init: ResponseInit & {
    retryable?: boolean;
    details?: ApiError['error']['details'];
  } = {},
): Response {
  const { retryable = false, details, ...responseInit } = init;
  const payload: ApiError = {
    ok: false,
    error: { code, message, retryable, ...(details ? { details } : {}) },
    meta: meta(context, env),
  };
  return Response.json(payload, {
    ...responseInit,
    headers: responseHeaders(responseInit.headers),
  });
}

export async function readJsonBody<T>(request: Request, maxBytes: number): Promise<T> {
  const contentType = request.headers.get('content-type') ?? '';
  if (!contentType.toLowerCase().startsWith('application/json')) {
    throw new HttpInputError('bad_request', 'Content-Type must be application/json', 415);
  }

  const declaredLength = Number(request.headers.get('content-length') ?? '0');
  if (Number.isFinite(declaredLength) && declaredLength > maxBytes) {
    throw new HttpInputError('body_too_large', 'Request body exceeds the configured limit', 413);
  }

  const body = await request.text();
  if (new TextEncoder().encode(body).byteLength > maxBytes) {
    throw new HttpInputError('body_too_large', 'Request body exceeds the configured limit', 413);
  }

  try {
    return JSON.parse(body) as T;
  } catch {
    throw new HttpInputError('bad_request', 'Request body is not valid JSON', 400);
  }
}

export class HttpInputError extends Error {
  constructor(
    readonly code: Extract<ApiErrorCode, 'bad_request' | 'body_too_large'>,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'HttpInputError';
  }
}
