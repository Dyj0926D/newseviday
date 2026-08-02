import {
  API_PATHS,
  assertContentSnapshot,
  type AskRequest,
  type HealthData,
  type ProfileEnhanceRequest,
  type StatusData,
} from '@newseviday/contracts';

import { AiProviderError } from './ai/deepseek';
import { enhanceProfile, validateProfileRequest } from './ai/profile';
import {
  ConfigurationError,
  deepSeekConfig,
  publicRuntimeConfig,
  ragConfig,
  runtimeMode,
  type Env,
} from './config';
import { failure, HttpInputError, readJsonBody, requestContext, success } from './http';
import { prepareRagResponse, RagUnavailableError, validateAskRequest } from './rag';
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

async function contentStatus(request: Request, env: Env): Promise<StatusData['content']> {
  if (env.ASSETS) {
    try {
      const response = await env.ASSETS.fetch(
        new Request(new URL('/data/current.json', request.url), {
          headers: { Accept: 'application/json' },
        }),
      );
      if (response.ok) {
        const snapshot: unknown = await response.json();
        assertContentSnapshot(snapshot);
        return {
          state: snapshot.state,
          updatedAt: snapshot.generatedAt,
          sourceCount: snapshot.sourceCount,
          snapshotId: snapshot.snapshotId,
        };
      }
    } catch {
      // Standalone API fallback and transient asset errors use explicit environment metadata.
    }
  }
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

  try {
    if (url.pathname === API_PATHS.health && request.method === 'GET') {
      const payload: HealthData = { service: 'newseviday-api', status: 'ok' };
      return withCors(success(payload, context, env), cors);
    }

    if (url.pathname === API_PATHS.status && request.method === 'GET') {
      const ai = deepSeekConfig(env);
      const rag = ragConfig(env);
      const content = await contentStatus(request, env);
      const aiAvailable = ai.enabled && Boolean(ai.apiKey) && Boolean(ai.model);
      const ragAvailable =
        rag.enabled && aiAvailable && Boolean(env.ASSETS) && Boolean(rag.traceSecret);
      const payload: StatusData = {
        product: 'NewsEviday',
        mode: runtimeMode(env.RUNTIME_MODE),
        content,
        ai: {
          state: aiAvailable ? 'available' : 'static-only',
          provider: aiAvailable ? 'deepseek' : null,
          model: aiAvailable ? ai.model : null,
        },
        rag: {
          state: ragAvailable ? 'available' : 'static-only',
          retrievalMode: ragAvailable ? 'article_dense' : null,
          corpusSnapshotId: ragAvailable ? content.snapshotId : null,
        },
      };
      return withCors(success(payload, context, env), cors);
    }

    if (url.pathname === API_PATHS.runtimeConfig && request.method === 'GET') {
      return withCors(success(publicRuntimeConfig(env), context, env), cors);
    }

    if (url.pathname === API_PATHS.profileEnhance && request.method === 'POST') {
      const runtime = publicRuntimeConfig(env);
      const raw = await readJsonBody<ProfileEnhanceRequest>(
        request,
        runtime.limits.requestBodyBytes,
      );
      const input = validateProfileRequest(raw);
      const result = await enhanceProfile(input, env, context.requestId, request.signal);
      return withCors(success(result, context, env), cors);
    }

    if (url.pathname === API_PATHS.ask && request.method === 'POST') {
      const runtime = publicRuntimeConfig(env);
      const raw = await readJsonBody<AskRequest>(request, runtime.limits.requestBodyBytes);
      const input = validateAskRequest(raw);
      const result = await prepareRagResponse(request, input, env, context.requestId);
      return withCors(
        result.kind === 'stream' ? result.response : success(result.data, context, env),
        cors,
      );
    }

    const knownRoute = Object.values(API_PATHS).includes(
      url.pathname as (typeof API_PATHS)[keyof typeof API_PATHS],
    );
    if (knownRoute) {
      const allow =
        url.pathname === API_PATHS.profileEnhance || url.pathname === API_PATHS.ask
          ? 'POST, OPTIONS'
          : 'GET, OPTIONS';
      return withCors(
        failure(
          'method_not_allowed',
          'HTTP method is not available for this endpoint',
          context,
          env,
          {
            status: 405,
            headers: { Allow: allow },
          },
        ),
        cors,
      );
    }

    return withCors(
      failure('not_found', 'API route not found', context, env, { status: 404 }),
      cors,
    );
  } catch (error) {
    if (error instanceof HttpInputError) {
      return withCors(
        failure(error.code, error.message, context, env, { status: error.status }),
        cors,
      );
    }
    if (error instanceof AiProviderError) {
      return withCors(
        failure(error.code, 'AI provider is temporarily unavailable', context, env, {
          status: error.status,
          retryable: error.retryable,
        }),
        cors,
      );
    }
    if (error instanceof RagUnavailableError) {
      return withCors(
        failure('rag_unavailable', 'Evidence-grounded Q&A is currently unavailable', context, env, {
          status: 503,
        }),
        cors,
      );
    }
    if (error instanceof Error && error.message === 'invalid_model_output') {
      return withCors(
        failure('invalid_model_output', 'AI returned an invalid structured profile', context, env, {
          status: 502,
        }),
        cors,
      );
    }
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
