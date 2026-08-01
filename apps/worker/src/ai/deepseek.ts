import type { DeepSeekConfig } from '../config';
import {
  type AiProvider,
  type ChatInput,
  type CompletionResult,
  NoopUsageRecorder,
  type StreamResult,
  estimateCostCny,
  type TokenPrice,
  type TokenUsage,
  type UsageRecorder,
} from './types';

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

interface DeepSeekResponse {
  id?: string;
  model?: string;
  choices?: Array<{
    finish_reason?: string;
    message?: { content?: string };
  }>;
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
  error?: { message?: string };
}

export class AiProviderError extends Error {
  constructor(
    readonly code: 'ai_unavailable' | 'upstream_timeout' | 'upstream_error',
    message: string,
    readonly retryable: boolean,
    readonly status: number,
  ) {
    super(message);
    this.name = 'AiProviderError';
  }
}

function tokenUsage(value: DeepSeekResponse['usage']): TokenUsage {
  return {
    promptTokens: value?.prompt_tokens ?? 0,
    completionTokens: value?.completion_tokens ?? 0,
    totalTokens: value?.total_tokens ?? 0,
  };
}

function retryableStatus(status: number): boolean {
  return status === 429 || status === 500 || status === 503;
}

export class DeepSeekClient implements AiProvider {
  constructor(
    private readonly config: DeepSeekConfig,
    private readonly fetcher: Fetcher = fetch,
    private readonly usageRecorder: UsageRecorder = new NoopUsageRecorder(),
    private readonly tokenPrice: TokenPrice | null = null,
  ) {}

  private async recordUsage(requestId: string, model: string, usage: TokenUsage): Promise<void> {
    await this.usageRecorder.record({
      requestId,
      provider: 'deepseek',
      model,
      usage,
      estimatedCostCny: estimateCostCny(usage, this.tokenPrice),
      recordedAt: new Date().toISOString(),
    });
  }

  private availableConfig(): DeepSeekConfig & { apiKey: string; model: string } {
    if (!this.config.enabled || !this.config.apiKey || !this.config.model) {
      throw new AiProviderError(
        'ai_unavailable',
        'AI is disabled or its server-side configuration is incomplete',
        false,
        503,
      );
    }
    return { ...this.config, apiKey: this.config.apiKey, model: this.config.model };
  }

  private async request(input: ChatInput, stream: boolean): Promise<Response> {
    const config = this.availableConfig();
    const attempts = config.maxRetries + 1;

    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const controller = new AbortController();
      const onAbort = (): void => controller.abort(input.signal?.reason);
      input.signal?.addEventListener('abort', onAbort, { once: true });
      const timer = setTimeout(() => controller.abort('upstream_timeout'), config.timeoutMs);

      try {
        const response = await this.fetcher(`${config.baseUrl}/chat/completions`, {
          method: 'POST',
          headers: {
            Accept: stream ? 'text/event-stream' : 'application/json',
            Authorization: `Bearer ${config.apiKey}`,
            'Content-Type': 'application/json',
            'X-Request-Id': input.requestId,
          },
          body: JSON.stringify({
            model: config.model,
            messages: input.messages,
            stream,
            ...(stream ? { stream_options: { include_usage: true } } : {}),
            ...(input.temperature === undefined ? {} : { temperature: input.temperature }),
            ...(input.maxTokens === undefined ? {} : { max_tokens: input.maxTokens }),
          }),
          signal: controller.signal,
        });

        if (response.ok) return response;
        const error = (await response.json().catch(() => ({}))) as DeepSeekResponse;
        const retryable = retryableStatus(response.status);
        if (retryable && attempt + 1 < attempts) continue;
        throw new AiProviderError(
          'upstream_error',
          error.error?.message || `DeepSeek returned HTTP ${response.status}`,
          retryable,
          response.status,
        );
      } catch (error) {
        if (error instanceof AiProviderError) throw error;
        if (controller.signal.aborted) {
          throw new AiProviderError('upstream_timeout', 'DeepSeek request timed out', true, 504);
        }
        throw new AiProviderError('upstream_error', 'DeepSeek request failed', true, 502);
      } finally {
        clearTimeout(timer);
        input.signal?.removeEventListener('abort', onAbort);
      }
    }

    throw new AiProviderError('upstream_error', 'DeepSeek request failed', true, 502);
  }

  async complete(input: ChatInput): Promise<CompletionResult> {
    const response = await this.request(input, false);
    const payload = (await response.json()) as DeepSeekResponse;
    const choice = payload.choices?.[0];
    if (!payload.id || !choice?.message?.content) {
      throw new AiProviderError(
        'upstream_error',
        'DeepSeek returned an invalid payload',
        false,
        502,
      );
    }

    const usage = tokenUsage(payload.usage);
    await this.recordUsage(input.requestId, payload.model || this.config.model || 'unknown', usage);
    return {
      id: payload.id,
      content: choice.message.content,
      finishReason: choice.finish_reason || 'unknown',
      model: payload.model || this.config.model || 'unknown',
      usage,
    };
  }

  async stream(input: ChatInput): Promise<StreamResult> {
    const response = await this.request(input, true);
    if (!response.body) {
      throw new AiProviderError('upstream_error', 'DeepSeek returned an empty stream', false, 502);
    }
    let buffer = '';
    let finalUsage: TokenUsage | null = null;
    const decoder = new TextDecoder();
    const model = this.config.model || 'unknown';
    const recordUsage = async (usage: TokenUsage): Promise<void> =>
      this.recordUsage(input.requestId, model, usage);
    const body = response.body.pipeThrough(
      new TransformStream<Uint8Array, Uint8Array>({
        transform(chunk, controller) {
          controller.enqueue(chunk);
          buffer += decoder.decode(chunk, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            if (!line.startsWith('data: ') || line === 'data: [DONE]') continue;
            try {
              const payload = JSON.parse(line.slice(6)) as DeepSeekResponse;
              if (payload.usage) finalUsage = tokenUsage(payload.usage);
            } catch {
              // Preserve malformed upstream bytes for the caller; only accounting is skipped.
            }
          }
        },
        async flush() {
          if (finalUsage) await recordUsage(finalUsage);
        },
      }),
    );
    return {
      body,
      contentType: 'text/event-stream',
      model,
    };
  }
}
