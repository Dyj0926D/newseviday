import {
  API_PATHS,
  assertContentSnapshot,
  type ApiResponse,
  type RuntimeConfigData,
  type StatusData,
} from '@newseviday/contracts';
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

type RequestState = 'idle' | 'loading' | 'success' | 'static' | 'error';

export const useRuntimeStore = defineStore('runtime', () => {
  const requestState = ref<RequestState>('idle');
  const status = ref<StatusData | null>(null);
  const config = ref<RuntimeConfigData | null>(null);

  const modeLabel = computed(() => {
    const mode = status.value?.mode;
    if (mode === 'interview') return '在线服务';
    if (mode === 'warmup') return '内容准备中';
    return '内容快照模式';
  });

  const statusLabel = computed(() => {
    if (requestState.value === 'loading') return '正在确认更新状态';
    if (requestState.value === 'static') return '最新快照可用';
    if (requestState.value === 'error') return '已载入本地快照';
    return modeLabel.value;
  });

  async function loadStaticSnapshot(): Promise<void> {
    const basePath = import.meta.env.BASE_URL.replace(/\/$/, '');
    const response = await fetch(`${basePath}/data/current.json`, {
      headers: { Accept: 'application/json' },
      cache: 'no-cache',
    });
    if (!response.ok) throw new Error(`snapshot request failed: ${response.status}`);
    const snapshot: unknown = await response.json();
    assertContentSnapshot(snapshot);

    status.value = {
      product: 'NewsEviday',
      mode: 'archive',
      content: {
        state: snapshot.state,
        updatedAt: snapshot.generatedAt,
        sourceCount: snapshot.sourceCount,
        snapshotId: snapshot.snapshotId,
      },
      ai: { state: 'static-only', provider: null, model: null },
      rag: { state: 'static-only', retrievalMode: null, corpusSnapshotId: null },
      protection: { persistentGuardrails: 'unavailable', turnstile: 'disabled' },
    };
    requestState.value = 'static';
  }

  async function refresh(): Promise<void> {
    requestState.value = 'loading';
    const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';

    try {
      const response = await fetch(`${baseUrl}${API_PATHS.status}`, {
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`status request failed: ${response.status}`);

      const payload = (await response.json()) as ApiResponse<StatusData>;
      if (!payload.ok) throw new Error(payload.error.code);
      status.value = payload.data;
      try {
        const configResponse = await fetch(`${baseUrl}${API_PATHS.runtimeConfig}`, {
          headers: { Accept: 'application/json' },
        });
        if (!configResponse.ok) throw new Error('runtime config unavailable');
        const configPayload = (await configResponse.json()) as ApiResponse<RuntimeConfigData>;
        config.value = configPayload.ok ? configPayload.data : null;
      } catch {
        config.value = null;
      }
      requestState.value = 'success';
    } catch {
      try {
        await loadStaticSnapshot();
      } catch {
        requestState.value = 'error';
      }
    }
  }

  return { config, modeLabel, refresh, requestState, status, statusLabel };
});
