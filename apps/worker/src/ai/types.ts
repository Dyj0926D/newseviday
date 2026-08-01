export type ChatRole = 'system' | 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatInput {
  messages: ChatMessage[];
  temperature?: number;
  maxTokens?: number;
  signal?: AbortSignal;
  requestId: string;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface CompletionResult {
  id: string;
  content: string;
  finishReason: string;
  model: string;
  usage: TokenUsage;
}

export interface StreamResult {
  body: ReadableStream<Uint8Array>;
  contentType: 'text/event-stream';
  model: string;
}

export interface UsageRecord {
  requestId: string;
  provider: 'deepseek';
  model: string;
  usage: TokenUsage;
  estimatedCostCny: number | null;
  recordedAt: string;
}

export interface TokenPrice {
  inputCnyPerMillion: number;
  outputCnyPerMillion: number;
}

export function estimateCostCny(usage: TokenUsage, price: TokenPrice | null): number | null {
  if (!price) return null;
  return Number(
    (
      (usage.promptTokens * price.inputCnyPerMillion +
        usage.completionTokens * price.outputCnyPerMillion) /
      1_000_000
    ).toFixed(6),
  );
}

export interface UsageRecorder {
  record(record: UsageRecord): Promise<void>;
}

export interface AiProvider {
  complete(input: ChatInput): Promise<CompletionResult>;
  stream(input: ChatInput): Promise<StreamResult>;
}

export class NoopUsageRecorder implements UsageRecorder {
  async record(_record: UsageRecord): Promise<void> {}
}
