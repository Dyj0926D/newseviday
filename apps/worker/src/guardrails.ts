import type { CapabilityState } from '@newseviday/contracts';

import type { UsageRecord, UsageRecorder } from './ai/types';
import { guardrailConfig, publicRuntimeConfig, tokenPrice, type Env } from './config';
import { anonymizeIp, clientIp } from './security';

export type GenerationEndpoint = 'ask' | 'profile';
type RequestState = 'settled' | 'released' | 'denied';

interface ReservationInput {
  requestId: string;
  traceId: string;
  endpoint: GenerationEndpoint;
  clientHash: string;
  dayKey: string;
  monthKey: string;
  estimatedMicros: number;
  hardLimitMicros: number;
  createdAt: string;
  expiresAt: number;
}

interface QuotaInput {
  clientHash: string;
  dayKey: string;
  perIpLimit: number;
  globalLimit: number;
  updatedAt: string;
}

interface BudgetSnapshot {
  committedMicros: number;
}

export interface GuardrailStore {
  reserve(input: ReservationInput): Promise<'reserved' | 'duplicate' | 'budget_exceeded'>;
  consumeQuotas(input: QuotaInput): Promise<boolean>;
  acquireLease(
    requestId: string,
    leaseId: string,
    expiresAt: number,
    maximumConcurrent: number,
    createdAt: string,
  ): Promise<boolean>;
  finalize(
    requestId: string,
    leaseId: string | null,
    state: RequestState,
    actualMicros: number,
    settledAt: string,
    usage?: UsageRecord | null,
  ): Promise<void>;
  budgetSnapshot(monthKey: string, nowEpochSeconds: number): Promise<BudgetSnapshot>;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
}

export class D1GuardrailStore implements GuardrailStore {
  constructor(private readonly db: D1Database) {}

  async reserve(input: ReservationInput): Promise<'reserved' | 'duplicate' | 'budget_exceeded'> {
    try {
      await this.db
        .prepare(
          `INSERT INTO generation_requests (
            request_id, trace_id, endpoint, client_hash, day_key, month_key, state,
            estimated_micros, actual_micros, hard_limit_micros,
            created_at, expires_at, settled_at
          ) VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?, NULL, ?, ?, ?, NULL)`,
        )
        .bind(
          input.requestId,
          input.traceId,
          input.endpoint,
          input.clientHash,
          input.dayKey,
          input.monthKey,
          input.estimatedMicros,
          input.hardLimitMicros,
          input.createdAt,
          input.expiresAt,
        )
        .run();
      return 'reserved';
    } catch (error) {
      const message = errorMessage(error);
      if (message.includes('budget_exceeded')) return 'budget_exceeded';
      if (message.includes('unique') || message.includes('primary key')) return 'duplicate';
      throw error;
    }
  }

  async consumeQuotas(input: QuotaInput): Promise<boolean> {
    const statement = `INSERT INTO quota_counters (
        scope, counter_key, window_start, count, limit_value, updated_at
      ) VALUES (?, ?, ?, 1, ?, ?)
      ON CONFLICT(scope, counter_key, window_start) DO UPDATE SET
        count = quota_counters.count + 1,
        limit_value = excluded.limit_value,
        updated_at = excluded.updated_at`;
    try {
      await this.db.batch([
        this.db
          .prepare(statement)
          .bind('ip_day', input.clientHash, input.dayKey, input.perIpLimit, input.updatedAt),
        this.db
          .prepare(statement)
          .bind('global_day', 'all', input.dayKey, input.globalLimit, input.updatedAt),
      ]);
      return true;
    } catch (error) {
      if (errorMessage(error).includes('quota_exceeded')) return false;
      throw error;
    }
  }

  async acquireLease(
    requestId: string,
    leaseId: string,
    expiresAt: number,
    maximumConcurrent: number,
    createdAt: string,
  ): Promise<boolean> {
    const now = Math.floor(Date.now() / 1_000);
    await this.db.prepare('DELETE FROM generation_leases WHERE expires_at <= ?').bind(now).run();
    const row = await this.db
      .prepare(
        `INSERT INTO generation_leases (lease_id, request_id, expires_at, created_at)
         SELECT ?, ?, ?, ?
         WHERE (SELECT COUNT(*) FROM generation_leases WHERE expires_at > ?) < ?
         RETURNING lease_id`,
      )
      .bind(leaseId, requestId, expiresAt, createdAt, now, maximumConcurrent)
      .first<{ lease_id: string }>();
    return Boolean(row?.lease_id);
  }

  async finalize(
    requestId: string,
    leaseId: string | null,
    state: RequestState,
    actualMicros: number,
    settledAt: string,
    usage: UsageRecord | null = null,
  ): Promise<void> {
    const statements: D1PreparedStatement[] = [];
    if (state === 'released') {
      statements.push(
        this.db
          .prepare(
            `UPDATE quota_counters
             SET count = MAX(0, count - 1), updated_at = ?
             WHERE scope = 'ip_day'
               AND counter_key = (SELECT client_hash FROM generation_requests WHERE request_id = ?)
               AND window_start = (SELECT day_key FROM generation_requests WHERE request_id = ?)
               AND EXISTS (
                 SELECT 1 FROM generation_requests WHERE request_id = ? AND state = 'reserved'
               )`,
          )
          .bind(settledAt, requestId, requestId, requestId),
        this.db
          .prepare(
            `UPDATE quota_counters
             SET count = MAX(0, count - 1), updated_at = ?
             WHERE scope = 'global_day' AND counter_key = 'all'
               AND window_start = (SELECT day_key FROM generation_requests WHERE request_id = ?)
               AND EXISTS (
                 SELECT 1 FROM generation_requests WHERE request_id = ? AND state = 'reserved'
               )`,
          )
          .bind(settledAt, requestId, requestId),
      );
    }
    statements.push(
      this.db
        .prepare(
          `UPDATE generation_requests
           SET state = ?, actual_micros = ?, settled_at = ?,
               provider = ?, model = ?, prompt_tokens = ?, completion_tokens = ?, total_tokens = ?
           WHERE request_id = ? AND state = 'reserved'`,
        )
        .bind(
          state,
          actualMicros,
          settledAt,
          usage?.provider ?? null,
          usage?.model ?? null,
          usage?.usage.promptTokens ?? null,
          usage?.usage.completionTokens ?? null,
          usage?.usage.totalTokens ?? null,
          requestId,
        ),
    );
    if (leaseId) {
      statements.push(
        this.db.prepare('DELETE FROM generation_leases WHERE lease_id = ?').bind(leaseId),
      );
    }
    await this.db.batch(statements);
  }

  async budgetSnapshot(monthKey: string, nowEpochSeconds: number): Promise<BudgetSnapshot> {
    const row = await this.db
      .prepare(
        `SELECT COALESCE(SUM(
          CASE
            WHEN state = 'settled' THEN COALESCE(actual_micros, estimated_micros)
            WHEN state = 'reserved' AND expires_at > ? THEN estimated_micros
            ELSE 0
          END
        ), 0) AS committed_micros
        FROM generation_requests
        WHERE month_key = ?`,
      )
      .bind(nowEpochSeconds, monthKey)
      .first<{ committed_micros: number }>();
    return { committedMicros: Number(row?.committed_micros ?? 0) };
  }
}

type GuardrailErrorCode =
  | 'verification_required'
  | 'verification_failed'
  | 'request_conflict'
  | 'guardrails_unavailable'
  | 'rate_limited'
  | 'budget_paused';

export class GuardrailError extends Error {
  constructor(
    readonly code: GuardrailErrorCode,
    message: string,
    readonly status: number,
    readonly retryable = false,
    readonly retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = 'GuardrailError';
  }
}

interface TurnstileResult {
  success?: boolean;
  hostname?: string;
  action?: string;
  'error-codes'?: string[];
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export async function verifyTurnstile(
  request: Request,
  env: Env,
  remoteIp: string,
  fetcher: Fetcher = fetch,
): Promise<void> {
  const config = guardrailConfig(env);
  if (!config.turnstileEnabled) return;
  const token = request.headers.get('X-Turnstile-Token')?.trim() ?? '';
  if (!token || token.length > 2_048) {
    throw new GuardrailError('verification_required', 'Human verification is required', 400);
  }

  const form = new FormData();
  form.set('secret', config.turnstileSecret ?? '');
  form.set('response', token);
  form.set('remoteip', remoteIp);
  form.set('idempotency_key', crypto.randomUUID());
  let response: Response;
  try {
    response = await fetcher('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
      method: 'POST',
      body: form,
      signal: AbortSignal.timeout(5_000),
    });
  } catch {
    throw new GuardrailError(
      'guardrails_unavailable',
      'Human verification is temporarily unavailable',
      503,
      true,
    );
  }
  let result: TurnstileResult;
  try {
    result = (await response.json()) as TurnstileResult;
  } catch {
    throw new GuardrailError(
      'guardrails_unavailable',
      'Human verification is temporarily unavailable',
      503,
      true,
    );
  }
  if (!response.ok) {
    throw new GuardrailError(
      'guardrails_unavailable',
      'Human verification is temporarily unavailable',
      503,
      true,
    );
  }
  const hostname = result.hostname?.toLowerCase() ?? '';
  const hostnameAllowed =
    config.turnstileHostnames.length === 0 || config.turnstileHostnames.includes(hostname);
  if (!result.success || result.action !== 'generate' || !hostnameAllowed) {
    throw new GuardrailError('verification_failed', 'Human verification failed', 403);
  }
}

function cnyToMicros(value: number): number {
  return Math.max(0, Math.round(value * 1_000_000));
}

function conservativeReserveCny(
  endpoint: GenerationEndpoint,
  configuredReserveCny: number,
  env: Env,
): number {
  const price = tokenPrice(env);
  if (!price) return configuredReserveCny;
  const maximumInputTokens = endpoint === 'ask' ? 32_000 : 10_000;
  const maximumOutputTokens = endpoint === 'ask' ? 1_200 : 900;
  const pricedMaximum =
    ((maximumInputTokens * price.inputCnyPerMillion +
      maximumOutputTokens * price.outputCnyPerMillion) /
      1_000_000) *
    1.25;
  return Math.max(configuredReserveCny, Number(pricedMaximum.toFixed(6)));
}

function safeIdempotencyKey(request: Request): string {
  const value = request.headers.get('Idempotency-Key')?.trim();
  if (!value) return crypto.randomUUID();
  if (value.length > 80 || !/^[a-zA-Z0-9._:-]+$/.test(value)) {
    throw new GuardrailError('request_conflict', 'Idempotency key is invalid', 400);
  }
  return value;
}

function utcKeys(now: Date): { dayKey: string; monthKey: string; secondsUntilNextDay: number } {
  const iso = now.toISOString();
  const nextDay = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1);
  return {
    dayKey: iso.slice(0, 10),
    monthKey: iso.slice(0, 7),
    secondsUntilNextDay: Math.max(1, Math.ceil((nextDay - now.getTime()) / 1_000)),
  };
}

export class GenerationReservation {
  private finalized = false;

  readonly usageRecorder: UsageRecorder = {
    record: async (record: UsageRecord): Promise<void> => {
      const actualMicros = cnyToMicros(record.estimatedCostCny ?? this.estimatedCny);
      await this.settle('settled', actualMicros, record);
    },
  };

  constructor(
    private readonly store: GuardrailStore,
    readonly requestId: string,
    private readonly leaseId: string,
    private readonly estimatedCny: number,
  ) {}

  private async settle(
    state: RequestState,
    actualMicros: number,
    usage: UsageRecord | null = null,
  ): Promise<void> {
    if (this.finalized) return;
    await this.store.finalize(
      this.requestId,
      this.leaseId,
      state,
      actualMicros,
      new Date().toISOString(),
      usage,
    );
    this.finalized = true;
  }

  async finish(modelAttempted: boolean): Promise<void> {
    if (this.finalized) return;
    await this.settle(
      modelAttempted ? 'settled' : 'released',
      modelAttempted ? cnyToMicros(this.estimatedCny) : 0,
    );
  }
}

export async function beginGeneration(
  request: Request,
  env: Env,
  endpoint: GenerationEndpoint,
  traceId: string,
  storeOverride?: GuardrailStore,
): Promise<GenerationReservation> {
  const config = guardrailConfig(env);
  const runtime = publicRuntimeConfig(env);
  const remoteIp = clientIp(request);
  if (!remoteIp || !config.ipHashSecret || (!env.GUARDRAIL_DB && !storeOverride)) {
    throw new GuardrailError(
      'guardrails_unavailable',
      'Persistent generation guardrails are unavailable',
      503,
      true,
    );
  }
  await verifyTurnstile(request, env, remoteIp);

  const now = new Date();
  const nowEpochSeconds = Math.floor(now.getTime() / 1_000);
  const { dayKey, monthKey, secondsUntilNextDay } = utcKeys(now);
  const clientHash = await anonymizeIp(`${dayKey}:${remoteIp}`, config.ipHashSecret);
  const requestId = safeIdempotencyKey(request);
  const configuredReserveCny = endpoint === 'ask' ? config.askReserveCny : config.profileReserveCny;
  const estimatedCny = conservativeReserveCny(endpoint, configuredReserveCny, env);
  const store = storeOverride ?? new D1GuardrailStore(env.GUARDRAIL_DB as D1Database);
  let reserved: Awaited<ReturnType<GuardrailStore['reserve']>>;
  try {
    reserved = await store.reserve({
      requestId,
      traceId,
      endpoint,
      clientHash,
      dayKey,
      monthKey,
      estimatedMicros: cnyToMicros(estimatedCny),
      hardLimitMicros: cnyToMicros(runtime.limits.hardBudgetCny),
      createdAt: now.toISOString(),
      expiresAt: nowEpochSeconds + config.leaseSeconds,
    });
  } catch {
    throw new GuardrailError(
      'guardrails_unavailable',
      'Persistent generation guardrails are temporarily unavailable',
      503,
      true,
    );
  }
  if (reserved === 'duplicate') {
    throw new GuardrailError('request_conflict', 'This generation request already exists', 409);
  }
  if (reserved === 'budget_exceeded') {
    throw new GuardrailError('budget_paused', 'The monthly generation budget is exhausted', 503);
  }

  const leaseId = crypto.randomUUID();
  try {
    const budget = await store.budgetSnapshot(monthKey, nowEpochSeconds);
    const savingMode = budget.committedMicros >= cnyToMicros(runtime.limits.monthlyBudgetCny);
    const globalLimit = savingMode
      ? Math.min(runtime.limits.globalDailyGenerations, runtime.limits.softBudgetDailyGenerations)
      : runtime.limits.globalDailyGenerations;
    const leaseAcquired = await store.acquireLease(
      requestId,
      leaseId,
      nowEpochSeconds + config.leaseSeconds,
      runtime.limits.maxConcurrentGenerations,
      now.toISOString(),
    );
    if (!leaseAcquired) {
      await store.finalize(requestId, null, 'denied', 0, new Date().toISOString());
      throw new GuardrailError(
        'rate_limited',
        'Too many generation requests are running',
        429,
        true,
        10,
      );
    }
    const quotaAllowed = await store.consumeQuotas({
      clientHash,
      dayKey,
      perIpLimit: runtime.limits.dailyQuestionsPerIp,
      globalLimit,
      updatedAt: now.toISOString(),
    });
    if (!quotaAllowed) {
      await store.finalize(requestId, leaseId, 'denied', 0, new Date().toISOString());
      throw new GuardrailError(
        'rate_limited',
        'The daily generation limit has been reached',
        429,
        false,
        secondsUntilNextDay,
      );
    }
  } catch (error) {
    if (error instanceof GuardrailError) throw error;
    await store.finalize(requestId, null, 'denied', 0, new Date().toISOString()).catch(() => {});
    throw new GuardrailError(
      'guardrails_unavailable',
      'Persistent generation guardrails are temporarily unavailable',
      503,
      true,
    );
  }
  return new GenerationReservation(store, requestId, leaseId, estimatedCny);
}

export async function generationCapabilityState(env: Env): Promise<CapabilityState> {
  const config = guardrailConfig(env);
  if (!env.GUARDRAIL_DB || !config.ipHashSecret) return 'static-only';
  const runtime = publicRuntimeConfig(env);
  const { monthKey } = utcKeys(new Date());
  const budget = await new D1GuardrailStore(env.GUARDRAIL_DB).budgetSnapshot(
    monthKey,
    Math.floor(Date.now() / 1_000),
  );
  if (budget.committedMicros >= cnyToMicros(runtime.limits.hardBudgetCny)) {
    return 'budget-paused';
  }
  if (budget.committedMicros >= cnyToMicros(runtime.limits.monthlyBudgetCny)) {
    return 'saving-mode';
  }
  return 'available';
}

export function guardrailsConfigured(env: Env): boolean {
  try {
    const config = guardrailConfig(env);
    return Boolean(
      env.GUARDRAIL_DB &&
      config.ipHashSecret &&
      (!config.turnstileEnabled || (config.turnstileSiteKey && config.turnstileSecret)),
    );
  } catch {
    return false;
  }
}

export function finalizeStreamingResponse(
  response: Response,
  reservation: GenerationReservation,
): Response {
  if (!response.body) return response;
  const reader = response.body.getReader();
  const body = new ReadableStream<Uint8Array>({
    async pull(controller) {
      try {
        const { done, value } = await reader.read();
        if (done) {
          await reservation.finish(true);
          controller.close();
          return;
        }
        controller.enqueue(value);
      } catch (error) {
        await reservation.finish(true).catch(() => {});
        controller.error(error);
      }
    },
    async cancel(reason) {
      await reader.cancel(reason).catch(() => {});
      await reservation.finish(true).catch(() => {});
    },
  });
  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}
