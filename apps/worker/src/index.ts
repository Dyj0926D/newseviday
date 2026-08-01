import { API_PATHS, type HealthData, type StatusData } from '@newseviday/contracts';

import {
  ConfigurationError,
  deepSeekConfig,
  publicRuntimeConfig,
  runtimeMode,
  type Env,
} from './config';
import { failure, requestContext, success } from './http';
import { corsHeaders } from './security';

export type { Env } from './config';

function withCors(response: Response, cors: Record<string, string>): Response {
  const headers = new Headers(response.headers);
  Object.entries(cors).forEach(([key, value]) => headers.set(key, value));
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function contentStatus(env: Env): StatusData['content'] {
  const sourceCount = Number(env.CONTENT_SOURCE_COUNT ?? '0');
  const updatedAt = env.CONTENT_UPDATED_AT?.trim() || null;
  return {
    state: updatedAt ? 'ready' : 'empty',
    updatedAt,
    sourceCount: Number.isInteger(sourceCount) && sourceCount >= 0 ? sourceCount : 0,
    snapshotId: env.SNAPSHOT_ID?.trim() || null,
  };
}

export async function handleRequest(request: Request, env: Env): Promise<Response> {
  const context = requestContext(request);
  const url = new URL(request.url);
  const cors = corsHeaders(request, env);

  if (request.method === 'OPTIONS') {
    const origin = request.headers.get('Origin');
    if (origin && !cors['Access-Control-Allow-Origin']) {
      return withCors(
        failure('origin_not_allowed', 'Origin is not allowed', context, env, { status: 403 }),
        cors,
      );
    }
    return new Response(null, { status: 204, headers: cors });
  }

  if (request.method !== 'GET') {
    return withCors(
      failure('method_not_allowed', 'Only GET is available for this endpoint', context, env, {
        status: 405,
        headers: { Allow: 'GET, OPTIONS' },
      }),
      cors,
    );
  }

  try {
    if (url.pathname === API_PATHS.health) {
      const payload: HealthData = { service: 'newseviday-api', status: 'ok' };
      return withCors(success(payload, context, env), cors);
    }

    if (url.pathname === API_PATHS.status) {
      const ai = deepSeekConfig(env);
      const aiAvailable = ai.enabled && Boolean(ai.apiKey) && Boolean(ai.model);
      const payload: StatusData = {
        product: 'NewsEviday',
        mode: runtimeMode(env.RUNTIME_MODE),
        content: contentStatus(env),
        ai: {
          state: aiAvailable ? 'available' : 'static-only',
          provider: aiAvailable ? 'deepseek' : null,
          model: aiAvailable ? ai.model : null,
        },
      };
      return withCors(success(payload, context, env), cors);
    }

    if (url.pathname === API_PATHS.runtimeConfig) {
      return withCors(success(publicRuntimeConfig(env), context, env), cors);
    }

    return withCors(
      failure('not_found', 'API route not found', context, env, { status: 404 }),
      cors,
    );
  } catch (error) {
    if (error instanceof ConfigurationError) {
      return withCors(
        failure('invalid_configuration', 'Server configuration is invalid', context, env, {
          status: 503,
          details: { field: error.message.split(':')[0] ?? 'unknown' },
        }),
        cors,
      );
    }
    return withCors(
      failure('internal_error', 'Unexpected server error', context, env, {
        status: 500,
        retryable: true,
      }),
      cors,
    );
  }
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    return handleRequest(request, env);
  },
} satisfies ExportedHandler<Env>;
