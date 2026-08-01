# ADR-003：DeepSeek 适配层与默认关闭

- 状态：已采纳
- 日期：2026-08-01

## 背景

项目计划使用 DeepSeek，但产品名“V4 Pro”不一定等于 API 的稳定 model ID；价格、错误语义和流式格式也可能调整。

## 决策

- Worker 通过 `AiProvider` 接口封装 DeepSeek；
- model ID、Base URL、超时和重试均由服务端配置；
- API Key 只放 Worker Secret；
- 默认 `AI_ENABLED=false`，缺 Key 或 model ID 返回 `ai_unavailable`；
- 非流式和 SSE 流式均记录 Token，价格通过外部配置计算，代码不写死；
- 默认不重试，最多显式开启一次临时错误重试。

## 结果

前端与 RAG 编排不依赖具体供应商字段，替换模型时改动集中。真实价格和 model ID 需要在上线前按官方控制台复核。
