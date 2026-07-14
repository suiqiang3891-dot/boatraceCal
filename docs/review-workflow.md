# 审核工作流本地演练

当前项目还没有引入 FastAPI 运行时依赖，但 `ReviewWorkflowService` 已经覆盖 OpenAPI 中的人工审核路径。可以用 CLI 在本地按同一请求/响应契约演练离线 UI 到后端文件 store 的交接。

## 1. 从 UI 导出审核 JSON

前端“导出审核 JSON”按钮会生成 OpenAPI `ReviewImportRequest` 形状：

```json
{
  "reviews": [
    {
      "recommendation_id": "sample-rec-hit",
      "race_id": "20250102-01-01",
      "decision": "confirmed",
      "stake_units": 1,
      "notes": "server handoff",
      "reviewed_at": "2026-07-11T04:30:00.000Z",
      "reviewed_by": "browser-analyst"
    }
  ]
}
```

`decision` 只能是 `pending`、`confirmed` 或 `pass`。`pass` 必须使用 `stake_units: 0`。

## 2. 导入审核记录

```powershell
boatrace-cal review-workflow-import `
  --store data/reviews/reviews.json `
  --archive-dir artifacts/review-archives `
  --export-dir artifacts/review-exports `
  --reviews downloads/boatrace-reviews-2025-01-02.json `
  --output artifacts/api/review-import.json
```

输出对应 `/reviews/import` 的响应：

```json
{
  "stored_count": 2
}
```

## 3. 生成确认清单

```powershell
boatrace-cal review-workflow-confirmed-list `
  --store data/reviews/reviews.json `
  --archive-dir artifacts/review-archives `
  --export-dir artifacts/review-exports `
  --business-date 2025-01-02 `
  --generated-at 2026-07-11T04:00:00+00:00 `
  --generated-by analyst `
  --output artifacts/api/confirmed-list.json
```

输出对应 `/reviews/confirmed-list`，只包含人工确认且模拟单位数大于 0 的记录。

## 4. 冻结不可变归档

```powershell
boatrace-cal review-workflow-archive `
  --store data/reviews/reviews.json `
  --archive-dir artifacts/review-archives `
  --export-dir artifacts/review-exports `
  --business-date 2025-01-02 `
  --generated-at 2026-07-11T04:00:00+00:00 `
  --generated-by analyst `
  --frozen-at 2026-07-11T04:10:00+00:00 `
  --frozen-by analyst `
  --output artifacts/api/confirmed-archive.json
```

输出对应 `/reviews/archives`，同时在 `--archive-dir` 下写入内容哈希可追溯的归档文件。

## 5. 导出 Excel 并查询任务

```powershell
boatrace-cal review-workflow-export `
  --store data/reviews/reviews.json `
  --archive-dir artifacts/review-archives `
  --export-dir artifacts/review-exports `
  --business-date 2025-01-02 `
  --export-type confirmed_list `
  --generated-at 2026-07-11T04:00:00+00:00 `
  --generated-by analyst

boatrace-cal export-job-status `
  --store data/reviews/reviews.json `
  --archive-dir artifacts/review-archives `
  --export-dir artifacts/review-exports `
  --job-id confirmed-list-2025-01-02 `
  --output artifacts/api/export-job.json
```

`review-workflow-export` 会写入 `.xlsx` 文件和导出任务 manifest。`export-job-status` 输出对应 `/exports/{job_id}`。

## 6. 按 OpenAPI 路径演练本地请求

也可以用 `api-request` 直接按 OpenAPI 的 method/path 调用本地 adapter。输出会保留
`status_code` 和 JSON `body`，用于在没有 FastAPI 依赖时验证路由语义和 `ApiError` 形状：

```powershell
boatrace-cal api-request `
  --method POST `
  --path /reviews/import `
  --store data/reviews/reviews.json `
  --archive-dir artifacts/review-archives `
  --export-dir artifacts/review-exports `
  --body downloads/boatrace-reviews-2025-01-02.json `
  --output artifacts/api/local-request.json
```

候选查询路径可以通过 `--report-business-date` 和 `--report` 挂载回测报告：

```powershell
boatrace-cal api-request `
  --method GET `
  --path /business-dates/2025-01-02/candidates/sample-rec-hit `
  --report-business-date 2025-01-02 `
  --report examples/sample_backtest/report.json `
  --output artifacts/api/local-candidate-detail.json
```

## 7. 启动本地 HTTP API 并让 UI 直连

当前仍不新增 FastAPI 运行时依赖；浏览器联调可先使用标准库 HTTP server：

```powershell
boatrace-cal serve-api `
  --host 127.0.0.1 `
  --port 8765 `
  --report-business-date 2025-01-02 `
  --report examples/sample_backtest/report.json `
  --store data/reviews/reviews.json `
  --archive-dir artifacts/review-archives `
  --export-dir artifacts/review-exports `
  --allowed-origin http://127.0.0.1:5174
```

前端配置 API 地址后，顶部会出现“同步审核到本地 API”按钮：

```powershell
cd ui
$env:VITE_BOATRACE_API_BASE_URL="http://127.0.0.1:8765"
npm run dev -- --host 127.0.0.1 --port 5174
```

该按钮复用“导出审核 JSON”的 `ReviewImportRequest` 契约，POST 到 `/reviews/import`，不会改写回测报告中的模型推荐或结算事实。

## 风险边界

- 这些命令只演练纸面模拟审核链路，不提供自动下单。
- UI 导入的回测报告、人工审核状态和服务端 store 是分离的；审核动作不会改写模型推荐或回测事实。
- 真正接入 FastAPI 时，HTTP 路由应复用 `AnalysisApiAdapter` 和 `ReviewWorkflowService`，不要重新实现一套业务逻辑。
