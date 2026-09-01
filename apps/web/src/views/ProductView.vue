<script setup lang="ts">
import {
  PhArrowRight,
  PhArticle,
  PhBrain,
  PhBracketsCurly,
  PhCheckCircle,
  PhDatabase,
  PhFlask,
  PhFlowArrow,
  PhGlobeHemisphereWest,
  PhLockKey,
  PhMagnifyingGlass,
  PhRobot,
  PhStack,
} from '@phosphor-icons/vue';
import { computed } from 'vue';

const homePreviewUrl = '/brand/home-product-preview.png';
import { displaySummary, displayTitle, resolveSource } from '../lib/intelligence';
import { useContentStore } from '../stores/content';

const content = useContentStore();
const exampleArticle = computed(() => content.snapshot?.articles[0] ?? null);
const exampleSource = computed(() =>
  exampleArticle.value
    ? resolveSource(exampleArticle.value, content.snapshot?.sources ?? [])
    : undefined,
);

const loopSteps = [
  ['发现', '汇总海内外官方、论文、研究机构、专业媒体和作者信号'],
  ['理解', '翻译并整理标题、摘要和为什么值得看'],
  ['推荐', '按站点主题或关注偏好调整内容顺序'],
  ['追问', '在已收录语料内发起证据约束问答'],
  ['验证', '从回答回到文章、证据和原始来源'],
  ['简报', '把近 7 天信号整理成趋势与观察问题'],
] as const;

const architectureLayers = [
  {
    name: '公开来源',
    icon: PhGlobeHemisphereWest,
    summary: 'RSS、Atom、公开 API 和网页元数据。',
    detail: '来源按官方、论文、研究机构、专业媒体和独立作者分层，并标记一手、二手或观点证据。',
  },
  {
    name: 'Python 内容管道',
    icon: PhBracketsCurly,
    summary: '解析、规范化、规则去重、主题筛选和原子快照。',
    detail: '确定性任务优先使用 Python，降低 Token 成本并保持结果可复现。',
  },
  {
    name: '内容发布层',
    icon: PhDatabase,
    summary: '版本化 JSON 快照承载内容、证据和简报。',
    detail: '内容发布与在线生成解耦；动态服务不可用时仍能读取最近一次有效快照。',
  },
  {
    name: '检索与质量评测',
    icon: PhFlowArrow,
    summary: '有限步骤检索、证据门禁、引用生成和版本化评测。',
    detail:
      '问题先路由，最多执行两轮检索，再检查范围、时间与必需证据；公开问答仍受人工质量门槛控制。',
  },
  {
    name: 'Worker API',
    icon: PhRobot,
    summary: '统一处理密钥隔离、能力状态、超时和错误语义。',
    detail: '浏览器不会接触模型密钥；证据问答开放前还需通过访问额度和预算保护。',
  },
  {
    name: 'Vue 响应式前端',
    icon: PhStack,
    summary: 'Cloudflare 主站与 EdgeOne Makers 静态备用站共用一份产物。',
    detail: '页面优先读取内容快照，在线 API 暂不可用时不影响已发布内容。',
  },
] as const;
</script>

<template>
  <main id="main-content" class="product-page">
    <section class="product-hero" data-page-intro>
      <div class="page-container product-hero__inner">
        <div class="product-hero__copy">
          <p class="product-eyebrow">NEWS + EVIDENCE + DAY</p>
          <h1>把信息变成可验证的判断</h1>
          <p>
            NewsEviday 面向 AI
            与数据产品从业者，汇集海内外一手动态，用中文整理关键变化，并保留原文和证据入口。
          </p>
          <div class="product-hero__actions">
            <RouterLink class="button button--primary" to="/">
              浏览最新情报
              <PhArrowRight :size="17" aria-hidden="true" />
            </RouterLink>
            <a class="hero-text-link" href="#technical-perspective">了解技术实现</a>
          </div>
          <dl>
            <div>
              <dt>信息覆盖</dt>
              <dd>海内外动态</dd>
            </div>
            <div>
              <dt>内容处理</dt>
              <dd>跨语言整理</dd>
            </div>
            <div>
              <dt>可信机制</dt>
              <dd>原文与证据回链</dd>
            </div>
          </dl>
        </div>
        <div class="product-preview">
          <img :src="homePreviewUrl" alt="NewsEviday 首页实际 Vue 实现截图" />
          <p>NewsEviday 首页界面</p>
        </div>
      </div>
    </section>

    <nav class="product-jump-nav" aria-label="产品介绍快速定位">
      <div class="page-container">
        <a href="#product-perspective">产品视角</a>
        <a href="#technical-perspective">技术架构</a>
        <a href="#rag">RAG</a>
        <a href="#evaluation">评测</a>
        <a href="#cost-security">成本与安全</a>
      </div>
    </nav>

    <section id="product-perspective" class="page-container product-problem section-block">
      <div class="product-section-heading">
        <p class="product-eyebrow">PRODUCT PROBLEM</p>
        <h2>信息很多，真正缺的是一条可信的研究闭环</h2>
        <p>
          普通聚合工具解决了“看见链接”，但跨语言理解、上下文追问和趋势判断仍然需要用户手动完成。
        </p>
      </div>
      <div class="problem-list">
        <article>
          <span>01</span>
          <div>
            <h3>来源分散</h3>
            <p>新闻、官方博客、播客、GitHub Trending 和 arXiv 缺少统一入口。</p>
          </div>
        </article>
        <article>
          <span>02</span>
          <div>
            <h3>跨语言成本高</h3>
            <p>海外产品变化进入中文语境较慢，术语和原始语义容易丢失。</p>
          </div>
        </article>
        <article>
          <span>03</span>
          <div>
            <h3>结论难验证</h3>
            <p>只有摘要，没有来源、证据和检索过程，用户无法判断答案依据。</p>
          </div>
        </article>
      </div>
    </section>

    <section class="research-loop-section section-block">
      <div class="page-container">
        <div class="product-section-heading">
          <p class="product-eyebrow">RESEARCH LOOP</p>
          <h2>从发现变化到形成趋势判断</h2>
        </div>
        <ol class="research-loop">
          <li v-for="(step, index) in loopSteps" :key="step[0]">
            <span>{{ String(index + 1).padStart(2, '0') }}</span>
            <strong>{{ step[0] }}</strong>
            <p>{{ step[1] }}</p>
          </li>
        </ol>
      </div>
    </section>

    <section class="page-container capability-section section-block">
      <div class="product-section-heading">
        <p class="product-eyebrow">CORE CAPABILITIES</p>
        <h2>产品能力与当前状态放在一起说明</h2>
      </div>
      <div class="capability-list">
        <article>
          <PhGlobeHemisphereWest :size="24" aria-hidden="true" />
          <div>
            <h3>海内外情报整理</h3>
            <p>保留原始标题、语言、时间和原文入口，海外内容提供中文结构化摘要。</p>
          </div>
          <span>跨语言</span>
        </article>
        <article>
          <PhBrain :size="24" aria-hidden="true" />
          <div>
            <h3>可选关注偏好</h3>
            <p>本地保存兴趣权重，未设置时继续使用通用排序。</p>
          </div>
          <span>本地保存</span>
        </article>
        <article>
          <PhMagnifyingGlass :size="24" aria-hidden="true" />
          <div>
            <h3>证据约束问答</h3>
            <p>只检索已收录语料，回答必须带引用，证据不足时拒答。</p>
          </div>
          <span>证据约束</span>
        </article>
        <article>
          <PhArticle :size="24" aria-hidden="true" />
          <div>
            <h3>7 日趋势简报</h3>
            <p>按变化、影响、依据和不确定性组织趋势，访客不能重复生成。</p>
          </div>
          <span>来源回链</span>
        </article>
      </div>
    </section>

    <section v-if="exampleArticle" class="evidence-demo section-block">
      <div class="page-container evidence-demo__inner">
        <div class="product-section-heading">
          <p class="product-eyebrow">EVIDENCE IN PRACTICE</p>
          <h2>一条海外信号如何保留原文和中文判断</h2>
        </div>
        <div class="evidence-demo__content">
          <div>
            <span>{{ exampleSource?.name }} · {{ exampleSource?.region }}</span>
            <h3>{{ displayTitle(exampleArticle) }}</h3>
            <p>{{ displaySummary(exampleArticle) }}</p>
            <RouterLink class="text-link" :to="`/article/${exampleArticle.id}`">
              查看完整证据链
              <PhArrowRight :size="16" aria-hidden="true" />
            </RouterLink>
          </div>
          <dl>
            <div>
              <dt>原始信息</dt>
              <dd>{{ exampleArticle.facts.title }}</dd>
            </div>
            <div>
              <dt>
                {{
                  exampleArticle.ai?.provider === 'deepseek'
                    ? 'AI 整理'
                    : exampleArticle.ai?.provider === 'editorial'
                      ? '编辑整理'
                      : '内容状态'
                }}
              </dt>
              <dd>
                {{
                  exampleArticle.ai
                    ? '中文标题、摘要、关键点和为什么值得看'
                    : '保留来源标题与摘要，未经 AI 改写'
                }}
              </dd>
            </div>
            <div>
              <dt>可追溯性</dt>
              <dd>Article → Evidence → Source URL</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>

    <section class="page-container decision-section section-block">
      <div class="product-section-heading">
        <p class="product-eyebrow">PRODUCT DECISIONS</p>
        <h2>主动控制 MVP 的能力边界</h2>
      </div>
      <div class="decision-list">
        <article>
          <h3>关注偏好保持可选</h3>
          <p>首次访问不强制填写信息，通用内容始终可用。</p>
          <strong>降低体验门槛和隐私风险</strong>
        </article>
        <article>
          <h3>内容与生成解耦</h3>
          <p>内容快照独立发布，在线生成暂不可用时仍可稳定浏览。</p>
          <strong>保证内容连续性</strong>
        </article>
        <article>
          <h3>生成与浏览分离</h3>
          <p>访客可以查看简报和已有结果，但不能重复触发高成本生成。</p>
          <strong>避免公开额度失控</strong>
        </article>
        <article>
          <h3>证据先于答案</h3>
          <p>问答没有足够引用时直接拒答，不用模型补齐缺失事实。</p>
          <strong>建立可信边界</strong>
        </article>
      </div>
    </section>

    <section id="technical-perspective" class="architecture-section section-block">
      <div class="page-container">
        <div class="product-section-heading">
          <p class="product-eyebrow">TECHNICAL ARCHITECTURE</p>
          <h2>可靠优先、按需生成、全过程可追溯</h2>
          <p>内容、检索和生成分别控制。任何动态能力异常，都不会影响已经发布的情报和证据。</p>
        </div>
        <div class="architecture-flow">
          <details
            v-for="(layer, index) in architectureLayers"
            :key="layer.name"
            :open="index === 1"
          >
            <summary>
              <component :is="layer.icon" :size="22" aria-hidden="true" />
              <span>{{ layer.name }}</span>
              <small>{{ layer.summary }}</small>
            </summary>
            <p>{{ layer.detail }}</p>
          </details>
        </div>
      </div>
    </section>

    <section class="page-container ai-boundary section-block">
      <div class="product-section-heading">
        <p class="product-eyebrow">PYTHON AND AI</p>
        <h2>能用确定性代码解决的任务，不消耗大模型 Token</h2>
      </div>
      <div class="boundary-columns">
        <article>
          <PhBracketsCurly :size="25" aria-hidden="true" />
          <h3>Python 与规则</h3>
          <ul>
            <li>Feed 解析与字段规范化</li>
            <li>URL、哈希和相似去重</li>
            <li>主题初筛与内容配额</li>
            <li>快照校验、发布与回滚</li>
            <li>质量指标计算</li>
          </ul>
        </article>
        <article>
          <PhRobot :size="25" aria-hidden="true" />
          <h3>DeepSeek 与 Embedding</h3>
          <ul>
            <li>跨语言标题与摘要</li>
            <li>可选关注偏好整理</li>
            <li>基于证据的问答生成</li>
            <li>趋势简报文本组织</li>
            <li>跨语言语义检索</li>
          </ul>
        </article>
      </div>
    </section>

    <section id="rag" class="rag-section section-block">
      <div class="page-container rag-section__inner">
        <div class="product-section-heading">
          <p class="product-eyebrow">TRACEABLE RAG</p>
          <h2>RAG 负责把问题连接到可引用的证据</h2>
          <p>路由、检索、证据充分性判断、生成和 Trace 分开记录，任何一步失败都能说明原因并回退。</p>
        </div>
        <ol class="rag-flow">
          <li>
            <span>Query</span><strong>校验问题与范围</strong>
            <p>限制 300 字，并识别问题类型、时间边界和产品范围。</p>
          </li>
          <li>
            <span>Retrieve</span><strong>召回相关候选</strong>
            <p>以分块 BM25 为低成本主路径，按需补充跨语言表达，最多两轮检索。</p>
          </li>
          <li>
            <span>Gate</span><strong>检查证据是否够用</strong>
            <p>同时检查相关性和必需事实，缺少价格、数量等直接证据时拒答。</p>
          </li>
          <li>
            <span>Generate</span><strong>引用式回答</strong>
            <p>只注入选定上下文，事实句带编号。</p>
          </li>
          <li>
            <span>Trace</span><strong>记录匿名过程</strong>
            <p>保存候选、上下文、延迟和回退原因。</p>
          </li>
        </ol>
        <RouterLink class="text-link" to="/ask">
          查看问答能力边界 <PhArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </div>
    </section>

    <section id="evaluation" class="page-container evaluation-section section-block">
      <div class="product-section-heading">
        <p class="product-eyebrow">EVALUATION</p>
        <h2>评测覆盖内容管道、检索、回答和性能</h2>
        <p>所有公开指标都来自版本化语料、测试集和可重复运行的评测结果。</p>
      </div>
      <div class="evaluation-layers">
        <article>
          <span>内容质量</span>
          <h3>去重与语料健康</h3>
          <p>Precision、Recall、来源覆盖率、空内容率。</p>
        </article>
        <article>
          <span>检索质量</span>
          <h3>候选是否准确</h3>
          <p>Recall@5、Hit@5、MRR、NDCG@10。</p>
        </article>
        <article>
          <span>回答质量</span>
          <h3>结论是否受证据约束</h3>
          <p>引用覆盖率、Faithfulness、拒答准确率。</p>
        </article>
        <article>
          <span>系统性能</span>
          <h3>成本和延迟是否可接受</h3>
          <p>p50/p95、Token、缓存命中和失败回退。</p>
        </article>
      </div>
      <div class="evaluation-cta">
        <PhFlask :size="24" weight="duotone" aria-hidden="true" />
        <div>
          <strong>可复现检索基线</strong>
          <p>24 题内部黄金集与 2,255 题 MultiHop-RAG 公开基准可重复运行；回答正在进行逐句引用评测。</p>
        </div>
        <RouterLink class="button button--secondary" to="/eval">查看质量评测</RouterLink>
      </div>
    </section>

    <section id="cost-security" class="cost-section section-block">
      <div class="page-container cost-section__inner">
        <div class="product-section-heading">
          <p class="product-eyebrow">COST AND SECURITY</p>
          <h2>按需调用、额度保护、失败可降级</h2>
        </div>
        <div class="cost-principles">
          <article>
            <PhLockKey :size="23" aria-hidden="true" />
            <h3>密钥只在 Worker</h3>
            <p>前端和仓库不保存 DeepSeek Key，日志执行脱敏。</p>
          </article>
          <article>
            <PhCheckCircle :size="23" aria-hidden="true" />
            <h3>能力分别控制</h3>
            <p>采集、摘要、问答和简报拥有独立状态，故障不会相互扩散。</p>
          </article>
          <article>
            <PhDatabase :size="23" aria-hidden="true" />
            <h3>静态快照兜底</h3>
            <p>动态 API 失败后仍能显示最后成功内容。</p>
          </article>
          <article>
            <PhRobot :size="23" aria-hidden="true" />
            <h3>访问额度设计</h3>
            <p>证据问答开放以单 IP 次数和月度费用双重限制为前置条件。</p>
          </article>
        </div>
        <RouterLink class="text-link" to="/status">
          查看更新状态 <PhArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </div>
    </section>

    <section class="resource-section section-block">
      <div class="page-container">
        <div class="product-section-heading">
          <p class="product-eyebrow">EXPLORE NEWSEVIDAY</p>
          <h2>继续体验核心能力</h2>
        </div>
        <nav class="resource-links" aria-label="项目资料">
          <RouterLink to="/">
            <span>产品体验</span><strong>最新情报</strong><PhArrowRight :size="17" aria-hidden="true" />
          </RouterLink>
          <RouterLink to="/eval">
            <span>质量透明</span><strong>质量评测</strong><PhArrowRight :size="17" aria-hidden="true" />
          </RouterLink>
          <RouterLink to="/status">
            <span>更新透明</span><strong>更新状态</strong><PhArrowRight :size="17" aria-hidden="true" />
          </RouterLink>
        </nav>
      </div>
    </section>
  </main>
</template>
