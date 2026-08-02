<script setup lang="ts">
import { PhMagnifyingGlass, PhSlidersHorizontal } from '@phosphor-icons/vue';

defineProps<{
  query: string;
  view: 'all' | 'recommended';
  topics: Array<{ id: string; label: string }>;
  topic: string;
  region: string;
  source: string;
  time: string;
  regions: string[];
  sources: Array<{ id: string; name: string }>;
}>();

const emit = defineEmits<{
  search: [];
  'update:query': [value: string];
  'update:view': [value: 'all' | 'recommended'];
  'update:topic': [value: string];
  'update:region': [value: string];
  'update:source': [value: string];
  'update:time': [value: string];
}>();
</script>

<template>
  <div class="feed-controls">
    <div class="feed-controls__topline">
      <form class="feed-search" role="search" @submit.prevent="emit('search')">
        <PhMagnifyingGlass :size="19" aria-hidden="true" />
        <label class="visually-hidden" for="home-search">搜索已收录情报</label>
        <input
          id="home-search"
          data-home-search
          :value="query"
          name="q"
          type="search"
          placeholder="搜索主题、来源或关键信号"
          @input="emit('update:query', ($event.target as HTMLInputElement).value)"
        />
        <button type="submit">搜索</button>
      </form>

      <div class="segmented-control" aria-label="情报视图">
        <button type="button" :aria-pressed="view === 'all'" @click="emit('update:view', 'all')">
          全部情报
        </button>
        <button
          type="button"
          :aria-pressed="view === 'recommended'"
          @click="emit('update:view', 'recommended')"
        >
          为你推荐
        </button>
      </div>
    </div>

    <div class="topic-strip" aria-label="主题筛选">
      <button
        class="filter-chip"
        type="button"
        :aria-pressed="topic === ''"
        @click="emit('update:topic', '')"
      >
        全部主题
      </button>
      <button
        v-for="item in topics"
        :key="item.id"
        class="filter-chip"
        type="button"
        :aria-pressed="topic === item.id"
        @click="emit('update:topic', item.id)"
      >
        {{ item.label }}
      </button>
    </div>

    <div class="secondary-filters" aria-label="更多筛选">
      <span class="secondary-filters__label">
        <PhSlidersHorizontal :size="16" aria-hidden="true" />
        精细筛选
      </span>
      <label>
        <span>区域</span>
        <select
          :value="region"
          @change="emit('update:region', ($event.target as HTMLSelectElement).value)"
        >
          <option value="">全部区域</option>
          <option v-for="item in regions" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label>
        <span>来源</span>
        <select
          :value="source"
          @change="emit('update:source', ($event.target as HTMLSelectElement).value)"
        >
          <option value="">全部来源</option>
          <option v-for="item in sources" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </label>
      <label>
        <span>时间</span>
        <select
          :value="time"
          @change="emit('update:time', ($event.target as HTMLSelectElement).value)"
        >
          <option value="">不限时间</option>
          <option value="24h">24 小时</option>
          <option value="3d">3 天</option>
          <option value="7d">7 天</option>
        </select>
      </label>
    </div>
  </div>
</template>
