import {
  API_PATHS,
  type HealthResponse,
  type RuntimeMode,
  type StatusResponse,
} from '@newseviday/contracts';

export interface Env {
  APP_VERSION: string;
  RUNTIME_MODE: RuntimeMode;
  AI_ENABLED: string;
  ALLOWED_ORIGINS: string;
  DEEPSEEK_API_KEY?: string;
}

const BASE_HEADERS: Readonly<Record<string, string>> = {
  'Cache-Control': 'no-store',
  'Content-Type': 'application/json; charset=utf-8',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Content-Type-Options': 'nosniff',
};

function corsHeaders(request: Request, env: Env): Record<string, string> {
  const origin = request.headers.get('Origin');
  if (!origin) return {};

  const allowedOrigins = env.ALLOWED_ORIGINS.split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  if (!allowedOrigins.includes(origin)) return { Vary: 'Origin' };

  return {
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Origin': origin,
    Vary: 'Origin',
  };
}

function json(
  data: unknown,
  init: ResponseInit = {},
  extraHeaders: Record<string, string> = {},
): Response {
  return Response.json(data, {
    ...init,
    headers: {
      ...BASE_HEADERS,
      ...extraHeaders,
      ...init.headers,
    },
  });
}

function normalizeMode(value: string): RuntimeMode {
  if (value === 'warmup' || value === 'interview') return value;
  return 'archive';
}

export async function handleRequest(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const cors = corsHeaders(request, env);

  if (request.method === 'OPTIONS') {
    const origin = request.headers.get('Origin');
    if (origin && !cors['Access-Control-Allow-Origin']) {
      return json({ error: 'origin_not_allowed' }, { status: 403 }, cors);
    }
    return new Response(null, { status: 204, headers: { ...BASE_HEADERS, ...cors } });
  }

  if (request.method !== 'GET') {
    return json({ error: 'method_not_allowed' }, { status: 405 }, cors);
  }

  if (url.pathname === API_PATHS.health) {
    const payload: HealthResponse = {
      ok: true,
      service: 'newseviday-api',
      timestamp: new Date().toISOString(),
    };
    return json(payload, {}, cors);
  }

  if (url.pathname === API_PATHS.status) {
    const aiAvailable = env.AI_ENABLED === 'true' && Boolean(env.DEEPSEEK_API_KEY);
    const payload: StatusResponse = {
      product: 'NewsEviday',
      version: env.APP_VERSION,
      mode: normalizeMode(env.RUNTIME_MODE),
      generatedAt: new Date().toISOString(),
      content: {
        state: 'empty',
        updatedAt: null,
        sourceCount: 0,
      },
      ai: {
        state: aiAvailable ? 'available' : 'static-only',
        model: aiAvailable ? 'deepseek-v4-pro' : null,
      },
    };
    return json(payload, {}, cors);
  }

  return json({ error: 'not_found' }, { status: 404 }, cors);
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    return handleRequest(request, env);
  },
} satisfies ExportedHandler<Env>;
