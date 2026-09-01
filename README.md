# NewsEviday

> 有证据、可追溯、可暂停的 AI 产品与技术情报站。

[在线体验](https://newseviday.dyjnewseviday-worker.workers.dev) · [产品说明](./docs/产品说明.md) · [技术架构](./docs/工程架构说明.md) · [RAG 与评测](./docs/RAG与评测体系.md)

NewsEviday 面向产品经理、AI 产品经理和数据产品从业者，整理海内外 AI、数据平台与产品情报。产品通过双语信息流、来源证据、关注偏好、趋势简报和引用式问答，降低跨语言阅读与信息核验成本。

## 产品能力

- 配置 15 个海内外来源，覆盖官方、学术、研究机构、专业媒体和独立作者；内容经过规则清洗、两级去重和主题筛选后生成版本化快照；
- 提供最新情报、详情、趋势简报、证据问答、关注偏好、质量评测和更新状态页面；
- 首页默认展示近 30 天中文情报并按发布时间倒序；海外内容保留原始链接，未完成中文整理的原文只在“不限时间”视图中展示；
- 中文结构化内容区分 DeepSeek 生成与编辑整理，二者都保留来源事实层和证据回链；
- 来源只提供短标题或极短摘录时不调用模型扩写，避免用生成内容补齐缺失事实；
- 用户可以选择填写职业与关注方向，画像仅保存在浏览器本地，并支持 JSON 导入导出；
- AI、采集和问答可以独立关闭，停用后网站仍展示最后一份已发布快照。

## 技术特点

- Vue 3、Vite 与 TypeScript 构建响应式 Web；
- Cloudflare Workers Static Assets 承载同源静态站和 API，EdgeOne 保留静态备用构建；
- Python 管道负责来源采集、正文清洗、规则去重、确定性价值排序、内容质量审计、AI 增强和原子发布；
- DeepSeek V4 Flash 通过服务端适配层调用，显式使用非思考模式；
- D1 实现匿名 IP 配额、全站限额、并发租约、幂等请求和月度预算台账；
- Turnstile、精确 CORS、安全响应头和服务端 Secret 降低公开站的滥用风险；
- 有限步骤 Agentic RAG 先路由问题，最多进行两轮检索，再按时间、范围和必需证据判断是否回答；
- Eval Harness 管理版本化题集、检索指标、证据门禁、语料健康检查和发布 Gate。

## 架构

```mermaid
flowchart LR
    Sources["官方 / 学术 / 研究机构 / 专业媒体 / 作者"] --> Pipeline["Python 清洗 / 去重 / 价值排序"]
    Pipeline --> Snapshot["版本化 ContentSnapshot"]
    Snapshot --> Web["Vue 响应式 Web"]
    Web --> Worker["Cloudflare Worker API"]
    Worker --> Guardrails["Turnstile + D1 配额 / 预算 / 并发"]
    Worker --> Model["DeepSeek V4 Flash"]
    Worker --> RAG["问题路由 / 最多两轮检索 / 证据缺口检查"]
    RAG --> Trace["匿名 RAG Trace"]
    Snapshot --> Eval["Eval Harness + 质量 Gate"]
    Worker -. "AI 关闭或异常" .-> Snapshot
```

完整说明见 [工程架构说明](./docs/工程架构说明.md)。

## RAG 评测基线

当前仓库维护固定在真实生产快照上的 24 题内部黄金集，并接入 MultiHop-RAG 全量可回答问题作为跨文档迁移验证。检索主路径已切换为无需模型调用的 BM25，hashing dense 保留为回滚对照。

| 指标 | 内部 24 题 | MultiHop-RAG 2,255 题 |
| --- | ---: | ---: |
| Recall@5 | 1.0000 | 0.7394 |
| Recall@10 | 1.0000 | 0.8604 |
| MRR | 0.9167 | 0.8418 |
| NDCG@10 | 0.9385 | 0.7601 |
| Hit@5 | 1.0000 | 0.9805 |
| 本地 p95 | 60 ms | 33 ms |

内部集覆盖 40 篇真实文章、69 个分块，24 题检索证据与拒答判断已完成人工复核；MultiHop-RAG 使用固定 revision `71ac0d0b`、609 篇语料和 2,255 道可回答问题。RAGBench 的逐句支持、相关性、证据利用率和完整性标签用于校准回答评测字段。生成回答的逐句引用与忠实度仍在受控评测，因此总 Gate 保持 `fail`，线上 RAG 继续关闭。指标口径与复现命令见 [RAG 与评测体系](./docs/RAG与评测体系.md)。

## 本地运行

环境要求：Node.js 24、npm 10 或 11、Python 3.12、uv。

```powershell
git clone https://github.com/Dyj0926D/newseviday.git
cd newseviday
npm ci
python -m pip install uv
python -m uv sync --project pipeline --frozen
npm run dev
```

完整检查：

```powershell
npm run check
npm run test:e2e -w @newseviday/web
npm run pipeline:check
```

Python 离线评测：

```powershell
python -m uv run --project pipeline newseviday-pipeline eval-rag `
  apps/web/public/data/versions/snapshot-20260805T035314Z-a2c2f64d-ai-07822422.json `
  pipeline/eval/rag-gold-trial-v3.json --retrieval-mode chunk_bm25

python -m uv run --project pipeline newseviday-pipeline eval-public-rag `
  --allow-network --sample-size 0 --retrieval-mode bm25
```

## 安全默认值

真实密钥只允许放在 Cloudflare Secret、GitHub Actions Secret 或本地未跟踪的 `.dev.vars` 中。仓库默认保持：

```text
AI_ENABLED=false
INGESTION_ENABLED=false
RAG_ENABLED=false
TREND_BRIEF_ENABLED=false
DEEPSEEK_MODEL=deepseek-v4-flash
MONTHLY_BUDGET_CNY=5
HARD_BUDGET_CNY=10
```

内容批处理支持手动或受控定时触发。定时任务有总开关、截止日期和每日模型调用上限；当前每次最多整理 5 篇，优先处理高价值外文内容，定时任务关闭时不会产生调用。更多配置见 [安全与成本控制](./docs/安全与成本控制.md)。

公共 7 日趋势简报在北京时间每周六 10:00 生成，统计窗口为上周六 09:00 至本周六 09:00。每个趋势至少引用两个来源，并包含一手来源或两个独立二手来源；观点来源不能单独支撑趋势。证据不足、模型失败或候选未通过评审时保留上一版成功简报。

## 工程目录

```text
apps/web/               Vue 网站
apps/worker/            Cloudflare Worker API
packages/contracts/     TypeScript 契约与 JSON Schema
pipeline/               Python 内容管道与 Eval Harness
config/                 运行模式、主题和来源配置
design/                 Design Tokens 与视觉基准
docs/                   产品、架构、安全和 API 文档
migrations/             D1 数据库迁移
.github/workflows/      CI 与受控内容刷新
```

## 当前边界

- 当前公开内容来自受控生产快照，日更和周报都通过 Pull Request 审查后发布；
- DeepSeek 已配置为 V4 Flash，用于受控批量中文整理和周报候选；访客在线 RAG 与画像生成仍由质量 Gate 控制；
- 已实现 `bounded_v1` 有限步骤 Agentic RAG 编排；它是有固定步数和成本上限的 MVP，不宣称为开放式研究 Agent；
- RAG Trace 记录检索输入、排序候选、注入上下文和停止原因；内部黄金集已签字，生成回答的逐句引用 Gate 尚未完成；
- `workers.dev` 在部分中国大陆网络下可能无法直连；
- 开源许可证和信息源使用条款需在仓库转为公开前单独确认。

`package.json` 保持 `private: true`，防止误发布到 npm。
