<script setup lang="ts">
import { PhList, PhMagnifyingGlass, PhUserCircle, PhX } from '@phosphor-icons/vue';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { useRuntimeStore } from '../stores/runtime';

const runtime = useRuntimeStore();
const route = useRoute();
const isCompact = ref(false);
const mobileOpen = ref(false);
const menuButton = ref<HTMLButtonElement | null>(null);
const drawer = ref<HTMLElement | null>(null);
let heroObserver: IntersectionObserver | null = null;

const currentSection = computed(() =>
  typeof route.meta.title === 'string' ? route.meta.title : '情报流',
);

function observeHero(): void {
  heroObserver?.disconnect();
  const intro = document.querySelector('[data-page-intro]');
  if (!intro) {
    isCompact.value = true;
    return;
  }
  heroObserver = new IntersectionObserver(
    ([entry]) => {
      isCompact.value = !entry?.isIntersecting;
    },
    { rootMargin: '-64px 0px 0px', threshold: 0.04 },
  );
  heroObserver.observe(intro);
}

async function openMenu(): Promise<void> {
  mobileOpen.value = true;
  await nextTick();
  drawer.value?.querySelector<HTMLElement>('a')?.focus();
}

function closeMenu(restoreFocus = true): void {
  mobileOpen.value = false;
  if (restoreFocus) void nextTick(() => menuButton.value?.focus());
}

function handleDrawerKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    closeMenu();
    return;
  }
  if (event.key !== 'Tab' || !drawer.value) return;
  const focusable = [...drawer.value.querySelectorAll<HTMLElement>('a, button:not([disabled])')];
  const first = focusable[0];
  const last = focusable.at(-1);
  if (!first || !last) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

watch(
  () => route.fullPath,
  async () => {
    if (mobileOpen.value) closeMenu(false);
    await nextTick();
    observeHero();
  },
);

watch(mobileOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : '';
});

onMounted(observeHero);
onBeforeUnmount(() => {
  heroObserver?.disconnect();
  document.body.style.overflow = '';
});
</script>

<template>
  <header class="app-header" :class="{ 'app-header--compact': isCompact }">
    <div class="page-container app-header__inner">
      <RouterLink class="brand" to="/" aria-label="NewsEviday 首页">
        <span class="brand__mark" aria-hidden="true">N</span>
        <span>NewsEviday</span>
      </RouterLink>

      <nav class="desktop-nav" aria-label="主导航">
        <RouterLink to="/">情报流</RouterLink>
        <RouterLink to="/brief">趋势简报</RouterLink>
        <RouterLink to="/ask">情报问答</RouterLink>
        <RouterLink to="/product">产品介绍</RouterLink>
      </nav>

      <span class="header-context" aria-live="polite">{{ currentSection }}</span>

      <div class="app-header__actions">
        <span class="mode-badge">{{ runtime.statusLabel }}</span>
        <RouterLink class="icon-link" to="/?focus=search" aria-label="搜索情报">
          <PhMagnifyingGlass :size="20" weight="regular" aria-hidden="true" />
        </RouterLink>
        <RouterLink class="icon-link desktop-profile" to="/profile" aria-label="我的画像">
          <PhUserCircle :size="20" weight="regular" aria-hidden="true" />
        </RouterLink>
        <button
          ref="menuButton"
          class="mobile-menu-button"
          type="button"
          aria-label="打开导航菜单"
          :aria-expanded="mobileOpen"
          aria-controls="mobile-navigation"
          @click="openMenu"
        >
          <PhList :size="22" aria-hidden="true" />
        </button>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="drawer-fade">
        <div v-if="mobileOpen" class="mobile-drawer-layer">
          <button class="mobile-drawer-backdrop" type="button" aria-label="关闭导航菜单" @click="closeMenu()" />
          <aside
            id="mobile-navigation"
            ref="drawer"
            class="mobile-drawer"
            aria-label="移动端导航"
            @keydown="handleDrawerKeydown"
          >
            <div class="mobile-drawer__heading">
              <span>导航</span>
              <button type="button" aria-label="关闭导航菜单" @click="closeMenu()">
                <PhX :size="21" aria-hidden="true" />
              </button>
            </div>
            <nav>
              <RouterLink to="/">情报流</RouterLink>
              <RouterLink to="/brief">趋势简报</RouterLink>
              <RouterLink to="/ask">情报问答</RouterLink>
              <RouterLink to="/product">产品介绍</RouterLink>
              <RouterLink to="/profile">我的画像</RouterLink>
              <RouterLink to="/eval">Eval</RouterLink>
              <RouterLink to="/status">数据状态</RouterLink>
            </nav>
            <p>{{ runtime.statusLabel }}，动态 AI 能力保持关闭。</p>
          </aside>
        </div>
      </Transition>
    </Teleport>
  </header>
</template>
