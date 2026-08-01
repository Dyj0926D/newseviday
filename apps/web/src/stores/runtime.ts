import { API_PATHS, type StatusResponse } from '@newseviday/contracts';
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

type RequestState = 'idle' | 'loading' | 'success' | 'error';

export const useRuntimeStore = defineStore('runtime', () => {
  const requestState = ref<RequestState>('idle');
  const status = ref<StatusResponse | null>(null);

  const modeLabel = computed(() => {
    const mode = status.value?.mode;
    if (mode === 'interview') return '面试模式';
    if (mode === 'warmup') return '预热模式';
    return '归档模式';
  });

  const statusLabel = computed(() => {
    if (requestState.value === 'loading') return '连接状态服务';
    if (requestState.value === 'error') return '静态页面可用';
    return modeLabel.value;
  });

  async function refresh(): Promise<void> {
    requestState.value = 'loading';
    const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';

    try {
      const response = await fetch(`${baseUrl}${API_PATHS.status}`, {
        headers: { Accept: 'application/json' },
      });

      if (!response.ok) throw new Error(`status request failed: ${response.status}`);

      status.value = (await response.json()) as StatusResponse;
      requestState.value = 'success';
    } catch {
      requestState.value = 'error';
    }
  }

  return { modeLabel, refresh, requestState, status, statusLabel };
});
