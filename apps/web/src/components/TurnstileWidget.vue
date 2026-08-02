<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

interface TurnstileApi {
  render(
    element: HTMLElement,
    options: {
      sitekey: string;
      action: string;
      appearance: 'interaction-only';
      theme: 'light';
      size: 'flexible';
      callback(token: string): void;
      'expired-callback'(): void;
      'error-callback'(): void;
    },
  ): string;
  remove(widgetId: string): void;
  reset(widgetId: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const props = defineProps<{ siteKey: string; resetKey: number }>();
const emit = defineEmits<{ token: [value: string] }>();
const container = ref<HTMLElement | null>(null);
const state = ref<'loading' | 'ready' | 'error'>('loading');
let widgetId: string | null = null;

function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  const existing = document.querySelector<HTMLScriptElement>('script[data-newseviday-turnstile]');
  if (existing) {
    if (existing.dataset.loaded === 'true') {
      return Promise.reject(new Error('turnstile_unavailable'));
    }
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('turnstile_load_failed')), {
        once: true,
      });
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.dataset.newsevidayTurnstile = 'true';
    script.addEventListener(
      'load',
      () => {
        script.dataset.loaded = 'true';
        resolve();
      },
      { once: true },
    );
    script.addEventListener('error', () => reject(new Error('turnstile_load_failed')), {
      once: true,
    });
    document.head.append(script);
  });
}

async function renderWidget(): Promise<void> {
  if (!container.value) return;
  state.value = 'loading';
  try {
    await loadScript();
    if (!window.turnstile || !container.value) throw new Error('turnstile_unavailable');
    widgetId = window.turnstile.render(container.value, {
      sitekey: props.siteKey,
      action: 'generate',
      appearance: 'interaction-only',
      theme: 'light',
      size: 'flexible',
      callback(token) {
        state.value = 'ready';
        emit('token', token);
      },
      'expired-callback'() {
        emit('token', '');
      },
      'error-callback'() {
        state.value = 'error';
        emit('token', '');
      },
    });
  } catch {
    state.value = 'error';
    emit('token', '');
  }
}

watch(
  () => props.resetKey,
  () => {
    emit('token', '');
    if (widgetId && window.turnstile) window.turnstile.reset(widgetId);
  },
);

onMounted(renderWidget);
onBeforeUnmount(() => {
  if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
});
</script>

<template>
  <div class="turnstile-control" aria-label="人机验证">
    <div ref="container"></div>
    <p v-if="state === 'loading'">正在准备安全验证…</p>
    <p v-else-if="state === 'error'" role="alert">安全验证暂时无法加载，请稍后重试。</p>
    <p v-else>安全验证已完成，本次凭证仅用于当前生成请求。</p>
  </div>
</template>
