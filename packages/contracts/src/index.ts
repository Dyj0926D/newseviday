export const API_PATHS = {
  health: '/api/health',
  status: '/api/status',
} as const;

export type RuntimeMode = 'archive' | 'warmup' | 'interview';
export type CapabilityState =
  'available' | 'saving-mode' | 'static-only' | 'rate-limited' | 'budget-paused';

export interface HealthResponse {
  ok: true;
  service: 'newseviday-api';
  timestamp: string;
}

export interface StatusResponse {
  product: 'NewsEviday';
  version: string;
  mode: RuntimeMode;
  generatedAt: string;
  content: {
    state: 'empty' | 'ready' | 'stale';
    updatedAt: string | null;
    sourceCount: number;
  };
  ai: {
    state: CapabilityState;
    model: string | null;
  };
}
