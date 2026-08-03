<script setup lang="ts">
import { PhList, PhMagnifyingGlass, PhUserCircle, PhX } from '@phosphor-icons/vue';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import BrandMark from './BrandMark.vue';

const route = useRoute();
const isCompact = ref(false);
const mobileOpen = ref(false);
const menuButton = ref<HTMLButtonElement | null>(null);
const drawer = ref<HTMLElement | null>(null);
let heroObserver: IntersectionObserver | null = null;
let observationFrame = 0;

const currentSection = computed(() =>
  typeof route.meta.title === 'string' ? route.meta.title : '最新情报',
);
const isHome = computed(() => route.name === 'home');

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

async function scheduleHeroObservation(): Promise<void> {
  await nextTick();
  window.cancelAnimationFrame(observationFrame);
  observationFrame = window.requestAnimationFrame(observeHero);
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
    await scheduleHeroObservation();
  },
);

watch(mobileOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : '';
});

onMounted(() => {
  void scheduleHeroObservation();
});
onBeforeUnmount(() => {
  window.cancelAnimationFrame(observationFrame);
  heroObserver?.disconnect();
  document.body.style.overflow = '';
});
</script>

<template>
  <header
    class="app-header"
    :class="{
      'app-header--compact': isCompact,
      'app-header--immersive': isHome && !isCompact,
    }"
  >
    <div class="page-container app-header__inner">
      <RouterLink class="brand" to="/" aria-label="NewsEviday 首页">
        <BrandMark />
        <span>NewsEviday</span>
      </RouterLink>

      <nav class="desktop-nav" aria-label="主导航">
        <RouterLink to="/">最新情报</RouterLink>
        <RouterLink to="/brief">趋势简报</RouterLink>
        <RouterLink to="/ask">证据问答</RouterLink>
        <RouterLink to="/product">产品介绍</RouterLink>
      </nav>

      <span class="header-context" aria-live="polite">{{ currentSection }}</span>

      <div class="app-header__actions">
        <RouterLink class="icon-link" to="/?focus=search" aria-label="搜索情报">
          <PhMagnifyingGlass :size="20" weight="regular" aria-hidden="true" />
        </RouterLink>
        <RouterLink class="icon-link desktop-profile" to="/profile" aria-label="关注偏好">
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
          <button
            class="mobile-drawer-backdrop"
            type="button"
            aria-label="关闭导航菜单"
            @click="closeMenu()"
          />
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
              <RouterLink to="/">最新情报</RouterLink>
              <RouterLink to="/brief">趋势简报</RouterLink>
              <RouterLink to="/ask">证据问答</RouterLink>
              <RouterLink to="/product">产品介绍</RouterLink>
              <RouterLink to="/profile">关注偏好</RouterLink>
              <RouterLink to="/eval">质量评测</RouterLink>
              <RouterLink to="/status">更新状态</RouterLink>
            </nav>
            <p>所有 AI 整理均保留原始来源与内容更新时间。</p>
          </aside>
        </div>
      </Transition>
    </Teleport>
  </header>
</template>
