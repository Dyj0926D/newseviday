<script setup lang="ts">
import {
  API_PATHS,
  type ApiResponse,
  type RagCitation,
  type RagRefusalData,
  type RagStreamMeta,
} from '@newseviday/contracts';
import {
  PhArrowRight,
  PhDatabase,
  PhMagnifyingGlass,
  PhPauseCircle,
  PhShieldCheck,
  PhStopCircle,
} from '@phosphor-icons/vue';
import { computed, onBeforeUnmount, ref } from 'vue';
import { useRoute } from 'vue-router';

import InnerPageHero from '../components/InnerPageHero.vue';
import InlineNotice from '../components/home/InlineNotice.vue';
import { displayTitle, resolveSource } from '../lib/intelligence';
import { useContentStore } from '../stores/content';
import { useRuntimeStore } from '../stores/runtime';

interface DeepSeekStreamPayload {
  choices?: Array<{ delta?: { content?: string } }>;
}

const route = useRoute();
const content = useContentStore();
const runtime = useRuntimeStore();
const question = ref('');
const range = ref<'7d' | '30d'>('30d');
const answer = ref('');
const citations = ref<RagCitation[]>([]);
const traceId = ref('');
const refusal = ref(false);
const askError = ref('');
const asking = ref(false);
let activeController: AbortController | null = null;

const scopedArticle = computed(() => {
  const id = typeof route.query.article === 'string' ? route.query.article : '';
  return content.snapshot?.articles.find((item) => item.id === id) ?? null;
});
const ragAvailable = computed(() => runtime.status?.rag.state === 'available');
const suggested = [
  'Data Agent 最近出现了哪些产品变化？',
  '统一语义层为什么重新受到关注？',
  'RAG 评测正在从哪些指标转向发布门禁？',
];

function chooseQuestion(value: string): void {
  question.value = value;
  document.querySelector<HTMLTextAreaElement>('#intelligence-question')?.focus();
}

function parseEvent(block: string): void {
  const event = block
    .split('\n')
    .find((line) => line.startsWith('event:'))
    ?.slice(6)
    .trim();
  const data = block
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n');
  if (!data || data === '[DONE]') return;
  if (event === 'meta') {
    const meta = JSON.parse(data) as RagStreamMeta;
    citations.value = meta.citations;
    traceId.value = meta.traceId;
    return;
  }
  const payload = JSON.parse(data) as DeepSeekStreamPayload;
  answer.value += payload.choices?.[0]?.delta?.content ?? '';
}

async function consumeStream(response: Response): Promise<void> {
  if (!response.body) throw new Error('empty_stream');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n');
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';
    blocks.filter(Boolean).forEach(parseEvent);
    if (done) break;
  }
  if (buffer.trim()) parseEvent(buffer);
}

async function ask(): Promise<void> {
  if (!ragAvailable.value || !question.value.trim() || asking.value) return;
  activeController = new AbortController();
  asking.value = true;
  answer.value = '';
  citations.value = [];
  traceId.value = '';
  refusal.value = false;
  askError.value = '';
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';
  try {
    const response = await fetch(`${baseUrl}${API_PATHS.ask}`, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream, application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question: question.value.trim(),
        range: range.value,
        ...(scopedArticle.value ? { articleId: scopedArticle.value.id } : {}),
      }),
      signal: activeController.signal,
    });
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
      const payload = (await response.json()) as ApiResponse<RagRefusalData>;
      if (!payload.ok) throw new Error(payload.error.code);
      refusal.value = payload.data.refusalReason === 'evidence_insufficient';
      citations.value = payload.data.citations;
      traceId.value = payload.data.traceId;
      return;
    }
    if (!response.ok) throw new Error(`request_failed_${response.status}`);
    await consumeStream(response);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      askError.value = '回答已停止，当前已接收内容保留在页面中。';
    } else {
      askError.value = '问答暂时不可用，没有产生可展示的结果。请稍后重试。';
    }
  } finally {
    asking.value = false;
    activeController = null;
  }
}

function cancelAsk(): void {
  activeController?.abort();
}

onBeforeUnmount(cancelAsk);
</script>

<template>
  <main id="main-content">
    <InnerPageHero
      eyebrow="EVIDENCE-GROUNDED Q&A"
      title="基于已收录情报继续追问"
      description="从已收录内容中检索相关依据，回答必须回到文章、证据和原始来源。"
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
          title="证据问答正在准备"
          description="当前可先查看问题示例、语料范围和回答边界。开放后，回答将只基于已收录内容并附引用。"
        />

        <form class="question-composer" @submit.prevent="ask">
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
            <button v-if="asking" class="button button--secondary" type="button" @click="cancelAsk">
              <PhStopCircle :size="17" aria-hidden="true" />
              停止回答
            </button>
            <button
              v-else
              class="button button--primary"
              type="submit"
              :disabled="!ragAvailable || !question.trim()"
            >
              <PhMagnifyingGlass :size="17" aria-hidden="true" />
              {{ ragAvailable ? '开始检索' : '暂未开放' }}
            </button>
          </div>
        </form>

        <p v-if="askError" class="ask-error" role="alert">{{ askError }}</p>

        <section v-if="asking || answer || refusal" class="rag-answer" aria-live="polite">
          <p class="section-kicker">TRACEABLE ANSWER</p>
          <h2>{{ refusal ? '当前语料不足以回答' : '基于证据的回答' }}</h2>
          <p v-if="refusal" class="rag-answer__refusal">
            检索结果没有达到证据阈值，因此本次不调用模型生成结论。
          </p>
          <p v-else class="rag-answer__body">
            {{ answer || '正在检索证据并生成回答…' }}
          </p>
          <div v-if="citations.length" class="rag-citations">
            <h3>引用证据</h3>
            <a
              v-for="citation in citations"
              :key="citation.chunkId"
              :href="citation.url"
              target="_blank"
              rel="noreferrer"
            >
              <span>[{{ citation.index }}] {{ citation.source }}</span>
              <strong>{{ citation.title }}</strong>
              <small>{{ citation.excerpt }}</small>
            </a>
          </div>
          <small v-if="traceId" class="rag-answer__trace">Trace {{ traceId.slice(0, 8) }}</small>
        </section>

        <div class="suggested-questions">
          <h2>可以这样问</h2>
          <button v-for="item in suggested" :key="item" type="button" @click="chooseQuestion(item)">
            <span>{{ item }}</span>
            <PhArrowRight :size="16" aria-hidden="true" />
          </button>
        </div>

        <section v-if="!answer && !refusal" class="rag-empty-state">
          <PhPauseCircle :size="28" weight="duotone" aria-hidden="true" />
          <div>
            <h2>{{ ragAvailable ? '等待问题' : '功能准备中' }}</h2>
            <p>
              正式回答按“检索候选、证据阈值、引用式生成、匿名 Trace”执行。没有足够证据时会拒答。
            </p>
          </div>
        </section>
      </div>

      <aside class="ask-context" aria-label="问答范围与安全边界">
        <div v-if="scopedArticle" class="ask-scope-card">
          <p>来自文章详情</p>
          <RouterLink :to="`/article/${scopedArticle.id}`">
            {{ displayTitle(scopedArticle) }}
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
              <dt>快照</dt>
              <dd>{{ runtime.status?.rag.corpusSnapshotId ?? '内容预览' }}</dd>
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
