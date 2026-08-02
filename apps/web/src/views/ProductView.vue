<script setup lang="ts">
import {
  PhArrowRight,
  PhArrowUpRight,
  PhArticle,
  PhBrain,
  PhBracketsCurly,
  PhCheckCircle,
  PhDatabase,
  PhFlask,
  PhFlowArrow,
  PhGithubLogo,
  PhGlobeHemisphereWest,
  PhLockKey,
  PhMagnifyingGlass,
  PhRobot,
  PhStack,
} from '@phosphor-icons/vue';
import { computed } from 'vue';

import homePreviewUrl from '../../../../design/reference/实现回归/P3-首页/首页-1440.png?url';
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
  ['发现', '汇总海内外官方博客、论文和开源信号'],
  ['理解', '翻译并整理标题、摘要和为什么值得看'],
  ['推荐', '按站点主题或本地画像调整内容顺序'],
  ['追问', '在已收录语料内发起证据约束问答'],
  ['验证', '从回答回到文章、证据和原始来源'],
  ['简报', '把近 7 天信号整理成趋势与观察问题'],
] as const;

const architectureLayers = [
  {
    name: '公开来源',
    icon: PhGlobeHemisphereWest,
    summary: 'RSS、Atom、公开 API、网页元数据和手动来源。',
    detail: '每个来源独立配置类型、语言、区域、启停状态和使用范围。',
  },
  {
    name: 'Python 内容管道',
    icon: PhBracketsCurly,
    summary: '解析、规范化、规则去重、主题筛选和原子快照。',
    detail: '确定性任务优先使用 Python，降低 Token 成本并保持结果可复现。',
  },
  {
    name: '数据与向量层',
    icon: PhDatabase,
    summary: 'Postgres/D1 保存结构化记录，Vectorize 保存可追溯 Chunk。',
    detail: '当前 MVP 只发布静态 JSON，数据库和向量服务在 RAG 阶段接入。',
  },
  {
    name: 'RAG 与 Eval',
    icon: PhFlowArrow,
    summary: '检索候选、注入上下文、引用式生成、Trace 和发布门禁。',
    detail: '当前入口保留但动态能力关闭，正式 Eval 尚未运行。',
  },
  {
    name: 'Worker API',
    icon: PhRobot,
    summary: '密钥隔离、开关、限流、预算、超时和统一错误语义。',
    detail: '浏览器永远不接触 DeepSeek Key，API 失败时页面回退静态快照。',
  },
  {
    name: 'Vue 响应式前端',
    icon: PhStack,
    summary: 'Cloudflare 主站与 EdgeOne Makers 静态备用站共用一份产物。',
    detail: '归档模式仍可浏览页面、往期情报、简报和项目说明。',
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
            与数据产品从业者，整理海内外情报，降低跨语言信息差，并保留证据和技术边界。
          </p>
          <div class="product-hero__actions">
            <RouterLink class="button button--primary" to="/">
              体验情报流
              <PhArrowRight :size="17" aria-hidden="true" />
            </RouterLink>
            <a class="hero-text-link" href="#technical-perspective">查看技术视角</a>
          </div>
          <dl>
            <div>
              <dt>当前阶段</dt>
              <dd>P3 静态产品</dd>
            </div>
            <div>
              <dt>动态 AI</dt>
              <dd>默认关闭</dd>
            </div>
            <div>
              <dt>月度预算</dt>
              <dd>目标 35 元内</dd>
            </div>
          </dl>
        </div>
        <div class="product-preview">
          <img :src="homePreviewUrl" alt="NewsEviday 首页实际 Vue 实现截图" />
          <p>实际页面截图，内容为演示快照</p>
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
          <span>静态演示可用</span>
        </article>
        <article>
          <PhBrain :size="24" aria-hidden="true" />
          <div>
            <h3>可选个人画像</h3>
            <p>本地保存兴趣权重，未设置时继续使用通用排序。</p>
          </div>
          <span>手动模式可用</span>
        </article>
        <article>
          <PhMagnifyingGlass :size="24" aria-hidden="true" />
          <div>
            <h3>证据约束问答</h3>
            <p>只检索已收录语料，回答必须带引用，证据不足时拒答。</p>
          </div>
          <span>规划中</span>
        </article>
        <article>
          <PhArticle :size="24" aria-hidden="true" />
          <div>
            <h3>7 日趋势简报</h3>
            <p>按变化、影响、依据和不确定性组织趋势，访客不能重复生成。</p>
          </div>
          <span>演示简报可用</span>
        </article>
      </div>
    </section>

    <section v-if="exampleArticle" class="evidence-demo section-block">
      <div class="page-container evidence-demo__inner">
        <div class="product-section-heading">
          <p class="product-eyebrow">EVIDENCE DEMO</p>
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
              <dt>AI 整理</dt>
              <dd>中文标题、摘要、关键点和为什么值得看</dd>
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
          <h3>画像保持可选</h3>
          <p>首次访问不弹窗强迫创建画像，通用流始终可用。</p>
          <strong>降低体验门槛和隐私风险</strong>
        </article>
        <article>
          <h3>归档模式优先</h3>
          <p>暂停采集与生成后，网站仍展示历史数据和完整前端。</p>
          <strong>控制长期成本</strong>
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
          <h2>静态优先、AI 可拔插、全过程可追溯</h2>
          <p>每层都能单独关闭或回滚。MVP 先保证页面与历史快照稳定，再逐步开放动态能力。</p>
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
            <li>Eval 指标计算</li>
          </ul>
        </article>
        <article>
          <PhRobot :size="25" aria-hidden="true" />
          <h3>DeepSeek 与 Embedding</h3>
          <ul>
            <li>跨语言标题与摘要</li>
            <li>可选画像语义增强</li>
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
          <p class="product-eyebrow">AGENTIC RAG</p>
          <h2>RAG 负责把问题连接到可引用的证据</h2>
          <p>检索、阈值判断、生成和 Trace 分开记录，任何一步失败都能说明原因并回退。</p>
        </div>
        <ol class="rag-flow">
          <li>
            <span>Query</span><strong>校验问题与范围</strong>
            <p>最近 30 天，默认单轮，限制 300 字。</p>
          </li>
          <li>
            <span>Retrieve</span><strong>chunk dense 检索</strong>
            <p>召回候选并保留 article fallback。</p>
          </li>
          <li>
            <span>Gate</span><strong>判断证据阈值</strong>
            <p>相关性不足时拒答，不进入生成。</p>
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
        <p>参考项目的指标只用于理解方法，NewsEviday 必须用自己的语料和黄金集重新运行。</p>
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
          <strong>正式黄金集尚未运行</strong>
          <p>当前 Eval 页面只展示方法和目标门槛。</p>
        </div>
        <RouterLink class="button button--secondary" to="/eval">查看 Eval 页面</RouterLink>
      </div>
    </section>

    <section id="cost-security" class="cost-section section-block">
      <div class="page-container cost-section__inner">
        <div class="product-section-heading">
          <p class="product-eyebrow">COST AND SECURITY</p>
          <h2>低成本运行依赖架构开关，不依赖人工盯守</h2>
        </div>
        <div class="cost-principles">
          <article>
            <PhLockKey :size="23" aria-hidden="true" />
            <h3>密钥只在 Worker</h3>
            <p>前端和仓库不保存 DeepSeek Key，日志执行脱敏。</p>
          </article>
          <article>
            <PhCheckCircle :size="23" aria-hidden="true" />
            <h3>默认全部关闭</h3>
            <p>采集、AI、RAG 和简报开关默认 false。</p>
          </article>
          <article>
            <PhDatabase :size="23" aria-hidden="true" />
            <h3>静态快照兜底</h3>
            <p>动态 API 失败后仍能显示最后成功内容。</p>
          </article>
          <article>
            <PhRobot :size="23" aria-hidden="true" />
            <h3>预算与额度接口</h3>
            <p>单 IP 次数、月度软阈值与硬上限可配置。</p>
          </article>
        </div>
        <RouterLink class="text-link" to="/status">
          查看当前运行状态 <PhArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </div>
    </section>

    <section class="page-container reference-boundary section-block">
      <div>
        <p class="product-eyebrow">REFERENCE BOUNDARY</p>
        <h2>参考 newnews 的方法，不复制代码和结果</h2>
      </div>
      <p>
        NewsEviday 复用“Agentic RAG、Trace、Eval Gate
        和静态降级”的方法论，再针对个人作品集、低成本运行和中国大陆访问边界重新设计产品与工程实现。
      </p>
      <a
        href="https://github.com/huiq777/newnews#%E4%B8%AD%E6%96%87"
        target="_blank"
        rel="noreferrer"
      >查看参考项目 <PhArrowUpRight :size="16" aria-hidden="true" /></a>
    </section>

    <section class="resource-section section-block">
      <div class="page-container">
        <div class="product-section-heading">
          <p class="product-eyebrow">PROJECT RESOURCES</p>
          <h2>继续查看产品、评测和项目资料</h2>
        </div>
        <nav class="resource-links" aria-label="项目资料">
          <RouterLink to="/">
            <span>产品体验</span><strong>情报流</strong><PhArrowRight :size="17" aria-hidden="true" />
          </RouterLink>
          <RouterLink to="/eval">
            <span>质量透明</span><strong>Eval</strong><PhArrowRight :size="17" aria-hidden="true" />
          </RouterLink>
          <RouterLink to="/status">
            <span>运行透明</span><strong>数据状态</strong><PhArrowRight :size="17" aria-hidden="true" />
          </RouterLink>
          <a href="https://github.com/Dyj0926D/newseviday" target="_blank" rel="noreferrer"><span>当前私有</span><strong>GitHub</strong><PhGithubLogo :size="18" aria-hidden="true" /></a>
          <a
            href="https://github.com/Dyj0926D/newseviday/blob/main/prd/NewsEviday-PRD.md"
            target="_blank"
            rel="noreferrer"
          ><span>产品文档</span><strong>PRD</strong><PhArrowUpRight :size="17" aria-hidden="true" /></a>
          <a
            href="https://github.com/Dyj0926D/newseviday/blob/main/docs/%E9%A1%B9%E7%9B%AE%E5%AE%9E%E6%96%BD%E8%AE%A1%E5%88%92%E4%B8%8E%E8%BF%9B%E5%BA%A6%E8%B7%9F%E8%B8%AA.md"
            target="_blank"
            rel="noreferrer"
          ><span>实施记录</span><strong>项目进度</strong><PhArrowUpRight :size="17" aria-hidden="true" /></a>
        </nav>
        <p class="resource-note">
          GitHub 仓库当前为私有状态，公开发布后外部访客才能查看源码和仓库文档。
        </p>
      </div>
    </section>
  </main>
</template>
