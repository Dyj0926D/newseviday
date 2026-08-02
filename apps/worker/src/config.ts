import { SCHEMA_VERSION, type RuntimeConfigData, type RuntimeMode } from '@newseviday/contracts';

export interface Env {
  APP_VERSION?: string;
  RUNTIME_MODE?: string;
  AI_ENABLED?: string;
  INGESTION_ENABLED?: string;
  RAG_ENABLED?: string;
  TREND_BRIEF_ENABLED?: string;
  ALLOWED_ORIGINS?: string;
  DAILY_QUESTIONS_PER_IP?: string;
  GLOBAL_DAILY_GENERATIONS?: string;
  SOFT_BUDGET_DAILY_GENERATIONS?: string;
  MAX_CONCURRENT_GENERATIONS?: string;
  MONTHLY_BUDGET_CNY?: string;
  HARD_BUDGET_CNY?: string;
  ASK_RESERVE_CNY?: string;
  PROFILE_RESERVE_CNY?: string;
  GUARDRAIL_LEASE_SECONDS?: string;
  REQUEST_BODY_BYTES?: string;
  UPSTREAM_TIMEOUT_MS?: string;
  DEEPSEEK_MODEL?: string;
  DEEPSEEK_BASE_URL?: string;
  DEEPSEEK_THINKING_ENABLED?: string;
  DEEPSEEK_MAX_RETRIES?: string;
  DEEPSEEK_API_KEY?: string;
  IP_HASH_SECRET?: string;
  CONTENT_UPDATED_AT?: string;
  CONTENT_SOURCE_COUNT?: string;
  SNAPSHOT_ID?: string;
  TRACE_HASH_SECRET?: string;
  TURNSTILE_ENABLED?: string;
  TURNSTILE_SITE_KEY?: string;
  TURNSTILE_SECRET?: string;
  TURNSTILE_HOSTNAMES?: string;
  DEEPSEEK_INPUT_CNY_PER_MILLION?: string;
  DEEPSEEK_OUTPUT_CNY_PER_MILLION?: string;
  RAG_MIN_SCORE?: string;
  RAG_MAX_CONTEXT_CHARS?: string;
  PUBLIC_TOPIC_IDS?: string;
  ASSETS?: { fetch(request: Request): Promise<Response> };
  GUARDRAIL_DB?: D1Database;
}

export class ConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigurationError';
  }
}

function asBoolean(value: string | undefined, fallback = false): boolean {
  if (value === undefined || value === '') return fallback;
  if (value === 'true') return true;
  if (value === 'false') return false;
  throw new ConfigurationError(`Expected true or false, received: ${value}`);
}

function asInteger(
  value: string | undefined,
  fallback: number,
  min: number,
  max: number,
  name: string,
): number {
  if (value === undefined || value === '') return fallback;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new ConfigurationError(`${name} must be an integer between ${min} and ${max}`);
  }
  return parsed;
}

export function runtimeMode(value: string | undefined): RuntimeMode {
  if (!value || value === 'archive') return 'archive';
  if (value === 'warmup' || value === 'interview') return value;
  throw new ConfigurationError(`Unsupported RUNTIME_MODE: ${value}`);
}

export function appVersion(env: Env): string {
  return env.APP_VERSION?.trim() || '0.0.0-local';
}

export function allowedOrigins(env: Env): string[] {
  return (env.ALLOWED_ORIGINS ?? '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function publicRuntimeConfig(env: Env): RuntimeConfigData {
  const aiEnabled = asBoolean(env.AI_ENABLED);
  const turnstileEnabled = asBoolean(env.TURNSTILE_ENABLED);
  const globalDailyGenerations = asInteger(
    env.GLOBAL_DAILY_GENERATIONS,
    20,
    0,
    10_000,
    'GLOBAL_DAILY_GENERATIONS',
  );
  const softBudgetDailyGenerations = asInteger(
    env.SOFT_BUDGET_DAILY_GENERATIONS,
    10,
    0,
    10_000,
    'SOFT_BUDGET_DAILY_GENERATIONS',
  );
  const monthlyBudgetCny = asInteger(env.MONTHLY_BUDGET_CNY, 35, 0, 50, 'MONTHLY_BUDGET_CNY');
  const hardBudgetCny = asInteger(env.HARD_BUDGET_CNY, 50, 0, 50, 'HARD_BUDGET_CNY');
  if (softBudgetDailyGenerations > globalDailyGenerations) {
    throw new ConfigurationError(
      'SOFT_BUDGET_DAILY_GENERATIONS must not exceed GLOBAL_DAILY_GENERATIONS',
    );
  }
  if (monthlyBudgetCny > hardBudgetCny) {
    throw new ConfigurationError('MONTHLY_BUDGET_CNY must not exceed HARD_BUDGET_CNY');
  }
  return {
    schemaVersion: SCHEMA_VERSION,
    mode: runtimeMode(env.RUNTIME_MODE),
    features: {
      ingestion: asBoolean(env.INGESTION_ENABLED),
      aiSummary: aiEnabled,
      rag: asBoolean(env.RAG_ENABLED),
      trendBrief: asBoolean(env.TREND_BRIEF_ENABLED),
      turnstile: turnstileEnabled,
    },
    limits: {
      dailyQuestionsPerIp: asInteger(
        env.DAILY_QUESTIONS_PER_IP,
        3,
        0,
        100,
        'DAILY_QUESTIONS_PER_IP',
      ),
      globalDailyGenerations,
      softBudgetDailyGenerations,
      maxConcurrentGenerations: asInteger(
        env.MAX_CONCURRENT_GENERATIONS,
        2,
        1,
        20,
        'MAX_CONCURRENT_GENERATIONS',
      ),
      monthlyBudgetCny,
      hardBudgetCny,
      requestBodyBytes: asInteger(
        env.REQUEST_BODY_BYTES,
        32_768,
        1_024,
        131_072,
        'REQUEST_BODY_BYTES',
      ),
      upstreamTimeoutMs: asInteger(
        env.UPSTREAM_TIMEOUT_MS,
        20_000,
        1_000,
        60_000,
        'UPSTREAM_TIMEOUT_MS',
      ),
    },
    protection: {
      turnstileSiteKey: turnstileEnabled ? env.TURNSTILE_SITE_KEY?.trim() || null : null,
    },
  };
}

export interface DeepSeekConfig {
  enabled: boolean;
  apiKey: string | null;
  model: string | null;
  baseUrl: string;
  thinkingEnabled: boolean;
  timeoutMs: number;
  maxRetries: number;
}

export interface RagConfig {
  enabled: boolean;
  minimumScore: number;
  maxContextChars: number;
  traceSecret: string | null;
}

export interface GuardrailConfig {
  askReserveCny: number;
  profileReserveCny: number;
  leaseSeconds: number;
  ipHashSecret: string | null;
  turnstileEnabled: boolean;
  turnstileSiteKey: string | null;
  turnstileSecret: string | null;
  turnstileHostnames: string[];
}

export function deepSeekConfig(env: Env): DeepSeekConfig {
  const runtime = publicRuntimeConfig(env);
  if (runtime.features.aiSummary && !tokenPrice(env)) {
    throw new ConfigurationError(
      'DEEPSEEK token prices are required before AI generation can be enabled',
    );
  }
  const baseUrl = env.DEEPSEEK_BASE_URL?.trim() || 'https://api.deepseek.com';
  try {
    const parsed = new URL(baseUrl);
    if (parsed.protocol !== 'https:') {
      throw new ConfigurationError('DEEPSEEK_BASE_URL must use HTTPS');
    }
  } catch {
    if (baseUrl.startsWith('http:')) {
      throw new ConfigurationError('DEEPSEEK_BASE_URL must use HTTPS');
    }
    throw new ConfigurationError('DEEPSEEK_BASE_URL must be an absolute URL');
  }

  return {
    enabled: runtime.features.aiSummary,
    apiKey: env.DEEPSEEK_API_KEY?.trim() || null,
    model: env.DEEPSEEK_MODEL?.trim() || null,
    baseUrl: baseUrl.replace(/\/$/, ''),
    thinkingEnabled: asBoolean(env.DEEPSEEK_THINKING_ENABLED),
    timeoutMs: runtime.limits.upstreamTimeoutMs,
    maxRetries: asInteger(env.DEEPSEEK_MAX_RETRIES, 0, 0, 1, 'DEEPSEEK_MAX_RETRIES'),
  };
}

function asNumber(
  value: string | undefined,
  fallback: number,
  min: number,
  max: number,
  name: string,
): number {
  if (value === undefined || value === '') return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    throw new ConfigurationError(`${name} must be between ${min} and ${max}`);
  }
  return parsed;
}

export function guardrailConfig(env: Env): GuardrailConfig {
  const runtime = publicRuntimeConfig(env);
  const ipHashSecret = env.IP_HASH_SECRET?.trim() || null;
  const turnstileSiteKey = env.TURNSTILE_SITE_KEY?.trim() || null;
  const turnstileSecret = env.TURNSTILE_SECRET?.trim() || null;
  if (ipHashSecret && ipHashSecret.length < 16) {
    throw new ConfigurationError('IP_HASH_SECRET must contain at least 16 characters');
  }
  if (runtime.features.turnstile && (!turnstileSiteKey || !turnstileSecret)) {
    throw new ConfigurationError('TURNSTILE configuration is incomplete');
  }
  return {
    askReserveCny: asNumber(env.ASK_RESERVE_CNY, 0.1, 0.001, 10, 'ASK_RESERVE_CNY'),
    profileReserveCny: asNumber(env.PROFILE_RESERVE_CNY, 0.05, 0.001, 10, 'PROFILE_RESERVE_CNY'),
    leaseSeconds: asInteger(env.GUARDRAIL_LEASE_SECONDS, 120, 30, 600, 'GUARDRAIL_LEASE_SECONDS'),
    ipHashSecret,
    turnstileEnabled: runtime.features.turnstile,
    turnstileSiteKey,
    turnstileSecret,
    turnstileHostnames: (env.TURNSTILE_HOSTNAMES ?? '')
      .split(',')
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean),
  };
}

export function tokenPrice(
  env: Env,
): { inputCnyPerMillion: number; outputCnyPerMillion: number } | null {
  const input = env.DEEPSEEK_INPUT_CNY_PER_MILLION?.trim();
  const output = env.DEEPSEEK_OUTPUT_CNY_PER_MILLION?.trim();
  if (!input && !output) return null;
  if (!input || !output) {
    throw new ConfigurationError('Both DeepSeek token price variables are required');
  }
  return {
    inputCnyPerMillion: asNumber(input, 0, 0, 100_000, 'DEEPSEEK_INPUT_CNY_PER_MILLION'),
    outputCnyPerMillion: asNumber(output, 0, 0, 100_000, 'DEEPSEEK_OUTPUT_CNY_PER_MILLION'),
  };
}

export function ragConfig(env: Env): RagConfig {
  const runtime = publicRuntimeConfig(env);
  const traceSecret = env.TRACE_HASH_SECRET?.trim() || env.IP_HASH_SECRET?.trim() || null;
  if (traceSecret && traceSecret.length < 16) {
    throw new ConfigurationError('TRACE_HASH_SECRET must contain at least 16 characters');
  }
  return {
    enabled: runtime.features.rag,
    minimumScore: asNumber(env.RAG_MIN_SCORE, 0.08, 0, 1, 'RAG_MIN_SCORE'),
    maxContextChars: asInteger(
      env.RAG_MAX_CONTEXT_CHARS,
      8_000,
      1_000,
      20_000,
      'RAG_MAX_CONTEXT_CHARS',
    ),
    traceSecret,
  };
}

export function publicTopicIds(env: Env): string[] {
  return (
    env.PUBLIC_TOPIC_IDS ??
    'data-agent,semantic-layer,data-platform,intelligent-lakehouse,rag-eval,metadata-governance'
  )
    .split(',')
    .map((item) => item.trim())
    .filter((item) => /^[a-z0-9-]+$/.test(item));
}
