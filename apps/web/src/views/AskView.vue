<script setup lang="ts">
import {
  PhArrowRight,
  PhDatabase,
  PhMagnifyingGlass,
  PhPauseCircle,
  PhShieldCheck,
} from '@phosphor-icons/vue';
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';

import InnerPageHero from '../components/InnerPageHero.vue';
import InlineNotice from '../components/home/InlineNotice.vue';
import { displayTitle, resolveSource } from '../lib/intelligence';
import { useContentStore } from '../stores/content';
import { useRuntimeStore } from '../stores/runtime';

const route = useRoute();
const content = useContentStore();
const runtime = useRuntimeStore();
const question = ref('');
const range = ref('30d');
const scopedArticle = computed(() => {
  const id = typeof route.query.article === 'string' ? route.query.article : '';
  return content.snapshot?.articles.find((item) => item.id === id) ?? null;
});
const ragAvailable = computed(() => runtime.status?.ai.state === 'available');
const suggested = [
  'Data Agent 最近出现了哪些产品变化？',
  '统一语义层为什么重新受到关注？',
  'RAG 评测正在从哪些指标转向发布门禁？',
];

function chooseQuestion(value: string): void {
  question.value = value;
  document.querySelector<HTMLTextAreaElement>('#intelligence-question')?.focus();
}
</script>

<template>
  <main id="main-content">
    <InnerPageHero
      eyebrow="EVIDENCE-GROUNDED Q&A"
      title="基于已收录情报继续追问"
      description="检索最近 30 天的公开快照，回答必须回到文章和证据。当前归档模式不会触发新生成。"
    >
      <template #actions>
        <RouterLink class="hero-text-link" to="/eval">
          查看评测方法
          <PhArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </template>
    </InnerPageHero>

    <section class="page-container ask-layout">
      <div class="ask-main">
        <InlineNotice
          v-if="!ragAvailable"
          title="情报问答当前暂停"
          description="RAG 和 DeepSeek 总开关保持关闭。你仍可浏览问题设计、语料范围和已有情报，不会产生模型费用。"
        />

        <form class="question-composer" @submit.prevent>
          <div class="question-composer__heading">
            <label for="intelligence-question">输入你的问题</label>
            <span>{{ question.length }} / 300</span>
          </div>
          <textarea
            id="intelligence-question"
            v-model="question"
            maxlength="300"
            rows="5"
            placeholder="例如：统一语义层最近为什么重新受到关注？"
          ></textarea>
          <div class="question-composer__footer">
            <label>
              <span>检索范围</span>
              <select v-model="range">
                <option value="30d">最近 30 天</option>
                <option value="7d">最近 7 天</option>
              </select>
            </label>
            <button
              class="button button--primary"
              type="submit"
              :disabled="!ragAvailable || !question.trim()"
            >
              <PhMagnifyingGlass :size="17" aria-hidden="true" />
              {{ ragAvailable ? '开始检索' : '问答已暂停' }}
            </button>
          </div>
        </form>

        <div class="suggested-questions">
          <h2>可以这样问</h2>
          <button v-for="item in suggested" :key="item" type="button" @click="chooseQuestion(item)">
            <span>{{ item }}</span>
            <PhArrowRight :size="16" aria-hidden="true" />
          </button>
        </div>

        <section class="rag-empty-state">
          <PhPauseCircle :size="28" weight="duotone" aria-hidden="true" />
          <div>
            <h2>等待能力开启</h2>
            <p>
              正式回答将按“检索候选、证据阈值、引用式生成、匿名
              Trace”四步执行。没有足够证据时会拒答。
            </p>
          </div>
        </section>
      </div>

      <aside class="ask-context" aria-label="问答范围与安全边界">
        <div v-if="scopedArticle" class="ask-scope-card">
          <p>来自文章详情</p>
          <RouterLink :to="`/article/${scopedArticle.id}`">
            {{
              displayTitle(scopedArticle)
            }}
          </RouterLink>
        </div>

        <section>
          <PhDatabase :size="20" aria-hidden="true" />
          <h2>当前语料</h2>
          <dl>
            <div>
              <dt>公开文章</dt>
              <dd>{{ content.snapshot?.articles.length ?? 0 }}</dd>
            </div>
            <div>
              <dt>来源</dt>
              <dd>{{ content.snapshot?.sourceCount ?? 0 }}</dd>
            </div>
            <div>
              <dt>范围</dt>
              <dd>静态演示快照</dd>
            </div>
          </dl>
        </section>

        <section>
          <PhShieldCheck :size="20" aria-hidden="true" />
          <h2>回答边界</h2>
          <ul>
            <li>不临时搜索全网</li>
            <li>事实句必须带引用</li>
            <li>证据不足时明确拒答</li>
            <li>不保存原始问题正文</li>
          </ul>
        </section>

        <section v-if="content.snapshot?.articles.length">
          <h2>可检索示例</h2>
          <RouterLink
            v-for="item in content.snapshot.articles.slice(0, 3)"
            :key="item.id"
            class="ask-source-link"
            :to="`/article/${item.id}`"
          >
            <span>{{
              resolveSource(item, content.snapshot.sources ?? [])?.name ?? item.sourceId
            }}</span>
            {{ displayTitle(item) }}
          </RouterLink>
        </section>
      </aside>
    </section>
  </main>
</template>
