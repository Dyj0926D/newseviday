import {
  API_PATHS,
  assertContentSnapshot,
  type ApiResponse,
  type StatusData,
} from '@newseviday/contracts';
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

type RequestState = 'idle' | 'loading' | 'success' | 'static' | 'error';

export const useRuntimeStore = defineStore('runtime', () => {
  const requestState = ref<RequestState>('idle');
  const status = ref<StatusData | null>(null);

  const modeLabel = computed(() => {
    const mode = status.value?.mode;
    if (mode === 'interview') return '面试模式';
    if (mode === 'warmup') return '预热模式';
    return '归档模式';
  });

  const statusLabel = computed(() => {
    if (requestState.value === 'loading') return '连接状态服务';
    if (requestState.value === 'static') return '静态快照可用';
    if (requestState.value === 'error') return '静态页面可用';
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
      requestState.value = 'success';
    } catch {
      try {
        await loadStaticSnapshot();
      } catch {
        requestState.value = 'error';
      }
    }
  }

  return { modeLabel, refresh, requestState, status, statusLabel };
});
