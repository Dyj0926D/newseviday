# NewsEviday Cloudflare 运行手册

## 1. 部署形态

根目录 `wrangler.jsonc` 是主部署配置：

- `apps/web/dist` 作为 Workers Static Assets；
- `/api/*` 先进入 Worker；
- 其他未知页面回退到 Vue `index.html`；
- 前端与 API 同源；
- `apps/worker/wrangler.jsonc` 只作为 API 独立回滚路径。

Cloudflare 官方建议把 Wrangler 配置作为配置事实源。Dashboard 中临时改动普通变量，可能在下次部署时被仓库配置覆盖；Secret 不会被普通部署自动删除。参考：[Wrangler Configuration](https://developers.cloudflare.com/workers/wrangler/configuration/)、[Workers Secrets](https://developers.cloudflare.com/workers/configuration/secrets/)。

## 2. 本地安全模式

```powershell
cd D:\workspace\eviday
npm ci
npm run cloudflare:check
npm run dev
```

默认配置：

- `RUNTIME_MODE=archive`；
- 采集、AI、RAG、趋势简报全部关闭；
- 无 DeepSeek Key 也可以构建、测试和浏览；
- Worker 不发起真实模型请求。

本地需要模型适配测试时，把根目录 `.dev.vars.example` 复制为 `.dev.vars`。该文件已被 Git 忽略。不要同时使用 `.env` 和 `.dev.vars` 保存 Worker Secret。

## 3. 部署前检查

```powershell
npm run security:scan
npm run check
npm run pipeline:check
git status --short
```

确认：

- 只提交示例环境文件；
- `apps/web/public/data/current.json` 可通过契约测试；
- `wrangler deploy --dry-run` 成功；
- AI 开关与预算状态符合本次发布目标；
- EdgeOne 备用站 Origin 如需访问 API，已加入 `ALLOWED_ORIGINS`。

## 4. 归档模式部署

归档模式不需要 DeepSeek Key：

```powershell
npm run deploy:cloudflare
```

发布后检查：

```powershell
curl.exe -sS https://<worker-host>/api/health
curl.exe -sS https://<worker-host>/api/status
curl.exe -sS https://<worker-host>/data/current.json
```

预期：`/api/status` 中 `mode=archive`、`ai.state=static-only`；静态快照可读。

## 5. 配置 DeepSeek

只配置 Secret 不会自动产生费用；代码中的 `AI_ENABLED` 仍为 `false`。

```powershell
npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put IP_HASH_SECRET
```

模型准确 ID 作为普通配置 `DEEPSEEK_MODEL` 管理。开启真实调用前必须完成：

1. 问答路由、匿名持久限流和预算台账完成；
2. `DEEPSEEK_MODEL` 与控制台文档一致；
3. 月预算和硬上限不超过 35/50 元；
4. 将 `AI_ENABLED` 改为 `true` 并走 Git 评审；
5. 只执行一次最小烟雾测试，记录输入/输出 Token 与费用估算；
6. 验证通过后再扩大访问范围。

## 6. 暂停采集与 AI

节省成本时：

1. `AI_ENABLED=false`；
2. `INGESTION_ENABLED=false`；
3. `RAG_ENABLED=false`；
4. `TREND_BRIEF_ENABLED=false`；
5. 保留 `apps/web/public/data/current.json`；
6. 重新部署。

停机后页面、产品介绍、Eval 说明和历史快照继续可用。不要删除最后一份有效快照。

## 7. 快照更新与回滚

离线验证：

```powershell
python -m uv run --project pipeline newseviday-pipeline run `
  --fixture pipeline/tests/fixtures/arxiv-feed.xml `
  --output data/local-preview
python -m uv run --project pipeline newseviday-pipeline validate-snapshot `
  data/local-preview/current.json
```

真实采集尚未开放。后续发布任务只允许把校验通过的 `current.json` 同步到 `apps/web/public/data/current.json`，并保留 `versions/<snapshotId>.json`。回滚时从上一版本恢复 `current.json`，重新构建部署。

## 8. 故障处理

| 现象 | 首要检查 | 安全处置 |
|---|---|---|
| 页面可开，API 失败 | `/api/health`、最近部署 | 前端自动读静态快照；关闭 AI |
| `invalid_configuration` | Wrangler 数字变量和模式 | 改回仓库默认值再部署 |
| `ai_unavailable` | 总开关、Key、model ID | 保持静态模式，补齐配置后再测 |
| 429/503 | 匿名额度、预算、上游状态 | 不扩大重试；暂停生成 |
| 快照异常 | `schemaVersion`、发布日志 | 恢复上一版本，禁止覆盖唯一副本 |
| 疑似密钥泄露 | Git 历史、日志、构建产物 | 立即轮换 Secret，再调查范围 |

## 9. EdgeOne 备用站边界

EdgeOne 只部署 Vue 静态构建与同格式快照。动态 API 仍可指向 Cloudflare Worker，届时必须：

- 设置 `VITE_API_BASE_URL`；
- 将备用站精确 Origin 加入 Worker CORS；
- 验证 CSP `connect-src`；
- 在大陆不同运营商网络实测；
- API 不可达时确认静态快照仍可用。

本手册不记录账号、Token、Account ID 或真实 Secret。
