# NewsEviday API 契约

| 项目 | 当前基线 |
|---|---|
| API 版本 | `0.1.x` |
| 数据 Schema | `1.0.0` |
| 传输 | HTTPS + JSON；问答使用 SSE |
| 当前状态 | 健康、状态、运行配置、画像增强和问答路由已实现；付费能力默认关闭 |

## 1. 统一响应

成功响应：

```json
{
  "ok": true,
  "data": {},
  "meta": {
    "requestId": "0f7b...",
    "generatedAt": "2026-08-01T08:00:00.000Z",
    "version": "0.1.0",
    "durationMs": 3
  }
}
```

失败响应：

```json
{
  "ok": false,
  "error": {
    "code": "ai_unavailable",
    "message": "AI is disabled or its server-side configuration is incomplete",
    "retryable": false
  },
  "meta": {
    "requestId": "0f7b...",
    "generatedAt": "2026-08-01T08:00:00.000Z",
    "version": "0.1.0",
    "durationMs": 2
  }
}
```

约束：

- `requestId` 用于串联 API 日志、RAG Trace 和费用记录，不承载 IP 或用户问题原文。
- 对外错误信息不返回密钥、上游请求体、堆栈和内部配置值。
- `durationMs` 是 Worker 侧处理耗时，不等同于端到端页面耗时。
- 字段只做向后兼容新增；删除、改名或语义变化必须提升 Schema 主版本。

## 2. 已实现接口

| 方法 | 路径 | 用途 | AI 调用 | 缓存 |
|---|---|---|---|---|
| GET | `/api/health` | Worker 存活检查 | 无 | `no-store` |
| GET | `/api/status` | 公开内容和 AI 能力状态 | 无 | `no-store` |
| GET | `/api/runtime-config` | 公开开关与额度，不含密钥 | 无 | `no-store` |
| OPTIONS | `/api/*` | CORS 预检 | 无 | 浏览器最多 600 秒 |

机器可读草案见 [openapi.yaml](./openapi.yaml)。共享 TypeScript 类型见 `packages/contracts/src/index.ts`。

## 3. 状态语义

内容状态：

| 值 | 含义 |
|---|---|
| `empty` | 尚无已发布快照 |
| `ready` | 有可展示快照 |
| `stale` | 有历史快照，但超过更新时效 |

AI 状态：

| 值 | 含义 |
|---|---|
| `available` | 总开关、Key 和 model ID 均已配置 |
| `static-only` | AI 关闭或配置不完整；静态内容仍可访问 |
| `saving-mode` | 主动节省 Token |
| `rate-limited` | 达到匿名访问额度 |
| `budget-paused` | 达到月度或硬预算上限 |

## 4. 错误码

| code | 常见 HTTP | 是否建议重试 | 说明 |
|---|---:|---|---|
| `bad_request` | 400/415 | 否 | 参数或 JSON 格式错误 |
| `body_too_large` | 413 | 否 | 请求体超过上限 |
| `origin_not_allowed` | 403 | 否 | CORS 来源未列入白名单 |
| `method_not_allowed` | 405 | 否 | 方法不受支持 |
| `not_found` | 404 | 否 | API 路由不存在 |
| `rate_limited` | 429 | 等待后重试 | 单 IP 匿名额度用尽 |
| `budget_paused` | 503 | 否 | 项目预算开关已暂停生成 |
| `ai_unavailable` | 503 | 否 | AI 关闭、缺 Key 或缺 model ID |
| `rag_unavailable` | 503 | 否 | RAG 关闭、缺静态语料 binding 或缺 Trace Secret |
| `evidence_insufficient` | 200（结构化拒答） | 否 | 检索证据未达到阈值，不调用生成模型 |
| `invalid_model_output` | 502 | 否 | 画像等结构化输出未通过校验 |
| `upstream_timeout` | 504 | 可重试 | 模型调用超时 |
| `upstream_error` | 502/429/503 | 视字段而定 | 模型服务异常 |
| `invalid_configuration` | 503 | 否 | 服务端配置不合法 |
| `internal_error` | 500 | 可重试 | 未分类服务端错误 |

DeepSeek 适配器只把 429、500、503 归为可重试错误。默认重试次数为 0，防止 POST 在结果不确定时重复计费；需要时最多配置 1 次。

## 5. AI 画像与问答接口

### `POST /api/profile/enhance`

- 输入：`role`、`work`、`goal`、`description`，至少一项非空；
- 输出：结构化字段、允许主题内的兴趣建议、推断术语、警告、模型与 Prompt 版本；
- 结果只进入前端预览，用户点击“应用建议”后才写入表单，再次保存后才进入浏览器本地画像；
- AI 关闭或缺少服务端配置时返回 `ai_unavailable`，手动画像不受影响。

### `POST /api/ask`

- 输入：2–300 字问题、`7d/30d` 范围、可选 `articleId`；
- 证据不足时返回结构化 `RagRefusalData`，不会调用生成模型；
- 证据充分时返回 SSE。首个事件为 `event: meta`，包含匿名 Trace ID、检索模式与引用；后续 `data:` 保持 OpenAI-compatible delta 格式，最后为 `[DONE]`；
- 客户端停止或断开连接时通过 `AbortSignal` 取消上游请求；
- Trace 只记录问题 HMAC 指纹、候选 chunk、注入 chunk、回退原因和耗时，不保存问题或 IP 原文。

服务端在模型调用前执行：功能开关、配置完整性、请求体校验、检索和证据阈值。持久匿名限流与预算台账属于 P7，因此公开环境继续保持 RAG 关闭。

## 6. 边界

- CORS 是浏览器边界，不是身份认证。
- `/api/runtime-config` 只公开布尔开关和数字额度；不得出现 Key、哈希盐、账号 ID。
- 真实 IP 只在请求内存中用于生成 HMAC 匿名键，不写入业务日志。
- 用户问题原文默认不进入长期日志；Eval 使用脱敏样本或人工构造黄金集。
