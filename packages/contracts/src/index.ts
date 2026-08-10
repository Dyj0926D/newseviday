export const SCHEMA_VERSION = '1.0.0' as const;

export const API_PATHS = {
  health: '/api/health',
  status: '/api/status',
  runtimeConfig: '/api/runtime-config',
  profileEnhance: '/api/profile/enhance',
  ask: '/api/ask',
} as const;

export type IsoDateTime = string;
export type LanguageCode = 'zh-CN' | 'en' | 'mixed' | string;
export type RuntimeMode = 'archive' | 'warmup' | 'interview';
export type CapabilityState =
  'available' | 'saving-mode' | 'static-only' | 'rate-limited' | 'budget-paused';

export type ApiErrorCode =
  | 'bad_request'
  | 'body_too_large'
  | 'invalid_configuration'
  | 'method_not_allowed'
  | 'not_found'
  | 'origin_not_allowed'
  | 'verification_required'
  | 'verification_failed'
  | 'request_conflict'
  | 'guardrails_unavailable'
  | 'rate_limited'
  | 'budget_paused'
  | 'ai_unavailable'
  | 'rag_unavailable'
  | 'evidence_insufficient'
  | 'invalid_model_output'
  | 'upstream_timeout'
  | 'upstream_error'
  | 'internal_error';

export interface ApiMeta {
  requestId: string;
  generatedAt: IsoDateTime;
  version: string;
  durationMs: number;
}

export interface ApiSuccess<T> {
  ok: true;
  data: T;
  meta: ApiMeta;
}

export interface ApiError {
  ok: false;
  error: {
    code: ApiErrorCode;
    message: string;
    retryable: boolean;
    details?: Record<string, string | number | boolean | null>;
  };
  meta: ApiMeta;
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export interface HealthData {
  service: 'newseviday-api';
  status: 'ok';
}

export interface StatusData {
  product: 'NewsEviday';
  mode: RuntimeMode;
  content: {
    state: 'empty' | 'ready' | 'stale';
    updatedAt: IsoDateTime | null;
    sourceCount: number;
    snapshotId: string | null;
  };
  ai: {
    state: CapabilityState;
    provider: 'deepseek' | null;
    model: string | null;
  };
  rag: {
    state: CapabilityState;
    retrievalMode: 'chunk_dense' | 'article_dense' | null;
    corpusSnapshotId: string | null;
  };
  protection: {
    persistentGuardrails: 'available' | 'unavailable';
    turnstile: 'enabled' | 'disabled';
  };
}

export interface RuntimeConfigData {
  schemaVersion: typeof SCHEMA_VERSION;
  mode: RuntimeMode;
  features: {
    ingestion: boolean;
    aiSummary: boolean;
    rag: boolean;
    trendBrief: boolean;
    turnstile: boolean;
  };
  limits: {
    dailyQuestionsPerIp: number;
    globalDailyGenerations: number;
    softBudgetDailyGenerations: number;
    maxConcurrentGenerations: number;
    monthlyBudgetCny: number;
    hardBudgetCny: number;
    requestBodyBytes: number;
    upstreamTimeoutMs: number;
  };
  protection: {
    turnstileSiteKey: string | null;
  };
}

export type HealthResponse = ApiSuccess<HealthData>;
export type StatusResponse = ApiSuccess<StatusData>;
export type RuntimeConfigResponse = ApiSuccess<RuntimeConfigData>;

export type SourceKind = 'atom' | 'rss' | 'json' | 'html' | 'manual';

export interface Source {
  schemaVersion: typeof SCHEMA_VERSION;
  id: string;
  name: string;
  kind: SourceKind;
  homepageUrl: string;
  feedUrl: string | null;
  language: LanguageCode;
  region: string;
  active: boolean;
  usageScope: string;
}

export interface Evidence {
  schemaVersion: typeof SCHEMA_VERSION;
  id: string;
  articleId: string;
  sourceId: string;
  url: string;
  excerpt: string;
  retrievedAt: IsoDateTime;
}

export interface GeneratedText {
  titleZh: string | null;
  summaryZh: string | null;
  whyItMatters?: string | null;
  keyPoints: string[];
  provider: 'deepseek';
  model: string;
  promptVersion: string;
  generatedAt: IsoDateTime;
}

export interface ContentScoreBreakdown {
  targetRelevance: number;
  technicalAdvancement: number;
  engineeringApplicability: number;
  technicalGenerality: number;
  productIndustryImpact: number;
  freshness: number;
  evidenceMaturity: number;
  completeness: number;
}

export interface KeySignalAssessment {
  eligible: boolean;
  score: number;
  userValue: number;
  changeMagnitude: number;
  actionability: number;
  generality: number;
  freshness: number;
  reasons: string[];
  gateFailures: string[];
}

export interface SnapshotTopic {
  id: string;
  label: string;
}

export interface Article {
  schemaVersion: typeof SCHEMA_VERSION;
  id: string;
  sourceId: string;
  canonicalUrl: string;
  language: LanguageCode;
  publishedAt: IsoDateTime | null;
  collectedAt: IsoDateTime;
  facts: {
    title: string;
    authors: string[];
    abstract: string | null;
  };
  ai: GeneratedText | null;
  evidenceIds: string[];
  topicScores: Record<string, number>;
  /** Deterministic 0-1 score used for feed ordering; never model-generated. */
  contentScore?: number;
  /** Observable sub-scores used to calculate contentScore. */
  contentScoreBreakdown?: ContentScoreBreakdown;
  /** Human-readable deterministic signals behind contentScore. */
  selectionReasons?: string[];
  /** Independent editorial gate and score for the homepage Key Signal slot. */
  keySignal?: KeySignalAssessment;
  contentHash: string;
}

export interface Chunk {
  schemaVersion: typeof SCHEMA_VERSION;
  id: string;
  articleId: string;
  position: number;
  text: string;
  language: LanguageCode;
  tokenEstimate: number;
  contentHash: string;
}

export interface PipelineStageResult {
  stage:
    | 'fetch'
    | 'extract'
    | 'normalize'
    | 'exact_dedup'
    | 'fuzzy_dedup'
    | 'select'
    | 'ai_enrich'
    | 'chunk'
    | 'index'
    | 'eval'
    | 'snapshot';
  status: 'succeeded' | 'skipped' | 'failed';
  inputCount: number;
  outputCount: number;
  durationMs: number;
  reason: string | null;
}

export interface SourceRunOutcome {
  sourceId: string;
  fetchStatus: 'succeeded' | 'failed';
  parseStatus: 'succeeded' | 'failed' | 'skipped';
  itemCount: number;
  selectedCount: number;
  finalUrl: string | null;
  errorCode: string | null;
}

export interface PipelineRun {
  schemaVersion: typeof SCHEMA_VERSION;
  id: string;
  startedAt: IsoDateTime;
  finishedAt: IsoDateTime | null;
  status: 'running' | 'succeeded' | 'failed';
  configVersion: number;
  sourceIds: string[];
  sourceOutcomes: SourceRunOutcome[];
  stages: PipelineStageResult[];
  errorCode: string | null;
}

export interface Brief {
  schemaVersion: typeof SCHEMA_VERSION;
  id: string;
  title: string;
  periodStart: IsoDateTime;
  periodEnd: IsoDateTime;
  sections: Array<{
    heading: string;
    body: string;
    evidenceIds: string[];
  }>;
  generatedBy: GeneratedText | null;
  publishedAt: IsoDateTime;
}

export interface ContentSnapshot {
  schemaVersion: typeof SCHEMA_VERSION;
  snapshotId: string;
  generatedAt: IsoDateTime;
  pipelineRunId: string;
  state: 'empty' | 'ready' | 'stale';
  snapshotKind?: 'demo' | 'production';
  sourceCount: number;
  sources?: Source[];
  topics?: SnapshotTopic[];
  articles: Article[];
  evidence: Evidence[];
  briefs: Brief[];
}

export interface RagTrace {
  schemaVersion: typeof SCHEMA_VERSION;
  id: string;
  createdAt: IsoDateTime;
  queryFingerprint: string;
  retrievalMode: 'chunk_dense' | 'article_dense' | 'hybrid_rerank';
  rankedCandidates: Array<{
    chunkId: string;
    rank: number;
    score: number;
  }>;
  injectedChunkIds: string[];
  answerId: string | null;
  fallbackReason: string | null;
  agentMode?: 'bounded_v1';
  route?: 'single_fact' | 'comparison' | 'timeline' | 'policy_scope';
  retrievalRounds?: number;
  sufficiencyReason?: string | null;
  stopReason?: 'evidence_sufficient' | 'evidence_insufficient' | 'policy_scope' | 'round_limit';
  latencyMs: number;
}

export interface EvalRun {
  schemaVersion: typeof SCHEMA_VERSION;
  id: string;
  createdAt: IsoDateTime;
  datasetVersion: string;
  retrievalMode: RagTrace['retrievalMode'];
  sampleCount: number;
  metrics: {
    recallAt5: number;
    recallAt10: number;
    mrr: number;
    ndcgAt10: number;
    hitAt5: number;
    p50LatencyMs: number;
    p95LatencyMs: number;
  };
  gate: 'pass' | 'fail' | 'observe';
  datasetKind?: 'demo' | 'production';
  corpusSnapshotId?: string | null;
  embeddingModel?: string | null;
}

export interface ProfileEnhanceRequest {
  role: string;
  work: string;
  goal: string;
  description: string;
}

export interface ProfileInterestSuggestion {
  topicId: string;
  weight: number;
  reason: string;
}

export interface ProfileEnhanceData extends ProfileEnhanceRequest {
  interests: ProfileInterestSuggestion[];
  inferredTerms: string[];
  warnings: string[];
  model: string;
  promptVersion: string;
}

export interface AskRequest {
  question: string;
  range: '7d' | '30d';
  articleId?: string;
}

export interface RagCitation {
  index: number;
  chunkId: string;
  articleId: string;
  title: string;
  source: string;
  url: string;
  excerpt: string;
}

export interface RagStreamMeta {
  traceId: string;
  retrievalMode: 'chunk_dense' | 'article_dense';
  agentMode?: 'bounded_v1';
  route?: 'single_fact' | 'comparison' | 'timeline' | 'policy_scope';
  retrievalRounds?: number;
  citations: RagCitation[];
}

export interface RagRefusalData {
  answer: null;
  refusalReason: 'evidence_insufficient';
  traceId: string;
  citations: RagCitation[];
}

export interface RuntimeConfig {
  schemaVersion: typeof SCHEMA_VERSION;
  version: number;
  mode: RuntimeMode;
  features: RuntimeConfigData['features'];
  limits: RuntimeConfigData['limits'];
  ai: {
    enabled: boolean;
    provider: 'deepseek';
    model: string | null;
  };
}

export function assertContentSnapshot(value: unknown): asserts value is ContentSnapshot {
  if (!value || typeof value !== 'object') throw new Error('snapshot_must_be_object');
  const snapshot = value as Record<string, unknown>;
  if (snapshot.schemaVersion !== SCHEMA_VERSION) throw new Error('unsupported_schema_version');
  if (typeof snapshot.snapshotId !== 'string' || snapshot.snapshotId.length < 1) {
    throw new Error('snapshot_id_required');
  }
  if (typeof snapshot.generatedAt !== 'string') throw new Error('generated_at_required');
  if (typeof snapshot.pipelineRunId !== 'string') throw new Error('pipeline_run_id_required');
  if (!['empty', 'ready', 'stale'].includes(String(snapshot.state))) {
    throw new Error('invalid_snapshot_state');
  }
  if (typeof snapshot.sourceCount !== 'number' || snapshot.sourceCount < 0) {
    throw new Error('invalid_source_count');
  }
  for (const field of ['articles', 'evidence', 'briefs']) {
    if (!Array.isArray(snapshot[field])) throw new Error(`${field}_must_be_array`);
  }
  for (const field of ['sources', 'topics']) {
    if (snapshot[field] !== undefined && !Array.isArray(snapshot[field])) {
      throw new Error(`${field}_must_be_array`);
    }
  }
  if (
    snapshot.snapshotKind !== undefined &&
    !['demo', 'production'].includes(String(snapshot.snapshotKind))
  ) {
    throw new Error('invalid_snapshot_kind');
  }
}
