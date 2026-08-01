<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

import PageIntro from '../components/PageIntro.vue';
import { useRuntimeStore } from '../stores/runtime';

const query = ref('');
const router = useRouter();
const runtime = useRuntimeStore();

const sourceCount = computed(() => runtime.status?.content.sourceCount ?? 0);

function submitSearch(): void {
  const value = query.value.trim();
  void router.push(value ? { path: '/', query: { q: value } } : { path: '/' });
}
</script>

<template>
  <main id="main-content">
    <PageIntro
      eyebrow="DAILY INTELLIGENCE"
      title="发现变化，看见脉络"
      description="海内外 AI 与数据情报，经过翻译、整理与证据关联。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" to="/profile">定制我的关注</RouterLink>
      </template>
    </PageIntro>

    <section class="page-container home-layout" aria-labelledby="feed-title">
      <div class="feed-shell">
        <form class="search-bar" role="search" @submit.prevent="submitSearch">
          <label for="home-search">搜索已收录情报</label>
          <div class="search-bar__row">
            <input
              id="home-search"
              v-model="query"
              name="q"
              type="search"
              placeholder="例如：统一语义层最近有什么变化"
            />
            <button class="button button--primary" type="submit">搜索</button>
          </div>
        </form>

        <div class="section-heading">
          <div>
            <h2 id="feed-title">今日情报</h2>
            <p>工程骨架已就绪，内容快照会在 Python 管道接入后显示。</p>
          </div>
          <RouterLink class="text-link" to="/brief">查看趋势简报</RouterLink>
        </div>

        <div class="empty-state" role="status">
          <h3>当前没有已发布的内容快照</h3>
          <p>网站仍可浏览。采集任务默认关闭，避免在开发阶段产生不必要费用。</p>
          <RouterLink class="button button--secondary" to="/product">了解产品方案</RouterLink>
        </div>
      </div>

      <aside class="signal-panel" aria-labelledby="signal-title">
        <h2 id="signal-title">信号概览</h2>
        <dl>
          <div>
            <dt>运行模式</dt>
            <dd>{{ runtime.modeLabel }}</dd>
          </div>
          <div>
            <dt>已启用来源</dt>
            <dd>{{ sourceCount }}</dd>
          </div>
          <div>
            <dt>AI 问答</dt>
            <dd>{{ runtime.status?.ai.state === 'available' ? '可用' : '暂停' }}</dd>
          </div>
        </dl>
        <RouterLink class="text-link" to="/status">查看数据状态</RouterLink>
      </aside>
    </section>
  </main>
</template>
