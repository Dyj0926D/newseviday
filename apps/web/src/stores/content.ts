import { assertContentSnapshot, type ContentSnapshot } from '@newseviday/contracts';
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

type ContentState = 'idle' | 'loading' | 'ready' | 'error';

export const useContentStore = defineStore('content', () => {
  const state = ref<ContentState>('idle');
  const snapshot = ref<ContentSnapshot | null>(null);
  let pendingRequest: Promise<void> | null = null;

  const isDemo = computed(() => snapshot.value?.snapshotKind === 'demo');

  function refresh(force = false): Promise<void> {
    if (!force && state.value === 'ready') return Promise.resolve();
    if (pendingRequest) return pendingRequest;

    pendingRequest = (async () => {
      state.value = 'loading';
      const basePath = import.meta.env.BASE_URL.replace(/\/$/, '');

      try {
        const response = await fetch(`${basePath}/data/current.json`, {
          headers: { Accept: 'application/json' },
          cache: 'no-cache',
        });
        if (!response.ok) throw new Error(`snapshot request failed: ${response.status}`);
        const payload: unknown = await response.json();
        assertContentSnapshot(payload);
        snapshot.value = payload;
        state.value = 'ready';
      } catch {
        state.value = 'error';
      } finally {
        pendingRequest = null;
      }
    })();

    return pendingRequest;
  }

  return { isDemo, refresh, snapshot, state };
});
