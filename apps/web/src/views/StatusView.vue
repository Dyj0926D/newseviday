<script setup lang="ts">
import {
  PhArrowRight,
  PhArchive,
  PhCloudCheck,
  PhDatabase,
  PhRobot,
  PhWarningCircle,
} from '@phosphor-icons/vue';
import { computed } from 'vue';

import InnerPageHero from '../components/InnerPageHero.vue';
import { formatDateTime } from '../lib/intelligence';
import { useContentStore } from '../stores/content';
import { useRuntimeStore } from '../stores/runtime';

const content = useContentStore();
const runtime = useRuntimeStore();
const isRefreshing = computed(
  () => content.state === 'loading' || runtime.requestState === 'loading',
);

async function refreshStatus(): Promise<void> {
  await Promise.all([content.refresh(true), runtime.refresh()]);
}
</script>

<template>
  <main id="main-content">
    <InnerPageHero
      eyebrow="PUBLIC SYSTEM STATUS"
      title="数据是否新鲜，AI 是否开启，都公开说明"
      description="状态页只展示脱敏后的运行信息。当前处于归档模式，静态快照可浏览，自动采集与生成已暂停。"
    >
      <template #actions>
        <button
          class="button button--secondary"
          type="button"
          :disabled="isRefreshing"
          @click="refreshStatus"
        >
          {{ isRefreshing ? '正在确认' : '重新确认状态' }}
        </button>
      </template>
    </InnerPageHero>

    <section class="page-container status-shell">
      <div class="status-summary">
        <article>
          <PhArchive :size="22" weight="duotone" aria-hidden="true" />
          <span>运行模式</span>
          <strong>{{ runtime.modeLabel }}</strong>
          <p>采集和生成任务暂停</p>
        </article>
        <article>
          <PhDatabase :size="22" weight="duotone" aria-hidden="true" />
          <span>内容快照</span>
          <strong>{{ content.snapshot?.state === 'ready' ? '可用' : '不可用' }}</strong>
          <p>{{ content.snapshot?.articles.length ?? 0 }} 条公开情报</p>
        </article>
        <article>
          <PhRobot :size="22" weight="duotone" aria-hidden="true" />
          <span>AI 与 RAG</span>
          <strong>{{ runtime.status?.ai.state === 'available' ? '已开启' : '已暂停' }}</strong>
          <p>不会产生新模型调用</p>
        </article>
        <article>
          <PhCloudCheck :size="22" weight="duotone" aria-hidden="true" />
          <span>状态来源</span>
          <strong>{{ runtime.requestState === 'success' ? 'Worker API' : '静态降级' }}</strong>
          <p>失败时回退本地快照</p>
        </article>
      </div>

      <section class="status-details">
        <div class="section-heading">
          <div>
            <p class="section-kicker">CONTENT SNAPSHOT</p>
            <h2>当前数据快照</h2>
            <p>这里只确认快照中包含什么，不推断每个外部来源此刻仍然在线。</p>
          </div>
        </div>
        <dl class="status-facts">
          <div>
            <dt>快照 ID</dt>
            <dd>{{ content.snapshot?.snapshotId ?? '未知' }}</dd>
          </div>
          <div>
            <dt>最后整理时间</dt>
            <dd>{{ content.snapshot ? formatDateTime(content.snapshot.generatedAt) : '未知' }}</dd>
          </div>
          <div>
            <dt>来源数量</dt>
            <dd>{{ content.snapshot?.sourceCount ?? 0 }}</dd>
          </div>
          <div>
            <dt>简报数量</dt>
            <dd>{{ content.snapshot?.briefs.length ?? 0 }}</dd>
          </div>
        </dl>
      </section>

      <section class="source-status-section">
        <div class="section-heading">
          <div>
            <p class="section-kicker">SOURCE CATALOG</p>
            <h2>快照内来源</h2>
            <p>“快照可用”仅表示当前归档中保留了对应来源元数据。</p>
          </div>
        </div>
        <div class="source-status-list">
          <article v-for="source in content.snapshot?.sources ?? []" :key="source.id">
            <span class="source-mark">{{ source.name.slice(0, 1) }}</span>
            <div>
              <strong>{{ source.name }}</strong><small>{{ source.region }} · {{ source.language }}</small>
            </div>
            <span class="status-text">快照可用</span>
            <a :href="source.homepageUrl" target="_blank" rel="noreferrer">访问来源</a>
          </article>
        </div>
      </section>

      <section class="known-issues">
        <div>
          <PhWarningCircle :size="22" aria-hidden="true" />
          <div>
            <h2>已知边界</h2>
            <p>以下项目已经登记，不影响静态浏览。</p>
          </div>
        </div>
        <ul>
          <li>
            <strong>演示数据</strong><span>当前 6 条内容用于验证产品结构，不代表实时新闻。</span>
          </li>
          <li><strong>自动更新暂停</strong><span>需要进入面试阶段时再手动开启采集。</span></li>
          <li>
            <strong>大陆访问稳定性</strong><span>Cloudflare 为主站，EdgeOne Makers 作为有时效的备用验证入口。</span>
          </li>
        </ul>
      </section>

      <nav class="page-next-links" aria-label="状态页后续入口">
        <RouterLink to="/">
          <span>返回内容</span><strong>浏览静态情报流</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
        <RouterLink to="/product#cost-security">
          <span>了解边界</span><strong>查看成本与安全设计</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
      </nav>
    </section>
  </main>
</template>
