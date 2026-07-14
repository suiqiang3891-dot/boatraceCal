# 赛前快照任务计划

本项目用 `snapshot-job-plan` 命令把比赛开赛时间表转换成可审计的日内快照任务计划。该命令只生成 JSON 计划，不访问外部网站，也不直接执行抓取。

## 输入 CSV

输入文件必须使用以下列，列名和顺序都需要一致：

```csv
race_date,venue,race_no,starts_at
2026-06-23,05,1,2026-06-23T04:30:00+00:00
2026-06-23,05,2,2026-06-23T05:00:00+00:00
```

- `race_date`: 比赛日期，格式为 `YYYY-MM-DD`。
- `venue`: BOAT RACE 场地代码，例如 `05`。
- `race_no`: 比赛编号，范围为 `1` 到 `12`。
- `starts_at`: 带时区的开赛时间，禁止使用无时区时间。

## 生成命令

```powershell
boatrace-cal snapshot-job-plan `
  --race-starts .\configs\race-starts.csv `
  --source official `
  --data-type odds `
  --output .\artifacts\jobs\snapshot-plan.json
```

每场比赛会生成四个任务：

| 快照点 | 执行时间 | 决策模式 |
| --- | --- | --- |
| `T30` | 开赛前 30 分钟 | `refresh` |
| `T15` | 开赛前 15 分钟 | `refresh` |
| `T10` | 开赛前 10 分钟 | `freeze_final_decision` |
| `T05` | 开赛前 5 分钟 | `change_alert_only` |

`T10` 是正式 SELECT/PASS 决策冻结点。`T05` 只能用于变化告警，不应静默覆盖已经冻结的确认版本。

## 输出契约

输出 JSON 的 `schema_version` 为 `snapshot-job-plan-v1`。每条任务包含稳定的 `job_key`、场地、日期、比赛编号、数据类型、快照点、计划执行时间、开赛时间和决策模式。

后续真实抓取或 Windows 任务计划只应消费这个计划，不应重新推导 T-10 冻结和 T-5 告警规则。

## 选择当前窗口到期任务

如果 Windows 任务计划按固定频率触发，可以先用 `snapshot-job-due` 从整天计划中筛出当前窗口内应执行的任务：

```powershell
boatrace-cal snapshot-job-due `
  --plan .\artifacts\jobs\snapshot-plan.json `
  --now 2026-06-23T04:14:00+00:00 `
  --lookahead-minutes 1 `
  --past-tolerance-minutes 0 `
  --output .\artifacts\jobs\snapshot-due.json
```

输出 JSON 的 `schema_version` 为 `snapshot-job-due-v1`，会保留原始任务对象，并额外记录本次筛选的 `window_start`、`window_end` 和 `job_count`。

## 记录任务账本

快照执行器在真正抓取前后应把状态写入本地任务账本。账本使用 `job_key` 幂等定位同一任务，并记录尝试次数、错误码、下次重试时间、checkpoint、解析器版本和产物标识。

```powershell
boatrace-cal job-ledger-record `
  --ledger .\artifacts\jobs\ledger.json `
  --job-key "official|05|2026-06-23|1|odds|T15" `
  --status pending `
  --updated-at 2026-06-23T04:14:00+00:00 `
  --checkpoint snapshot-plan-20260623 `
  --output .\artifacts\jobs\job-status.json
```

开始执行时把状态推进为 `running`；失败可推进为 `retry_wait`、`failed` 或 `skipped`；成功推进为 `succeeded` 并写入 `--artifact-id`。非法状态回退会被拒绝，例如 `succeeded` 不能回到 `running`。

```powershell
boatrace-cal job-ledger-get `
  --ledger .\artifacts\jobs\ledger.json `
  --job-key "official|05|2026-06-23|1|odds|T15" `
  --output .\artifacts\jobs\job-status.json
```

也可以把 `snapshot-job-due` 的输出批量登记为 `pending`。重复执行同一个 due 文件不会创建重复任务；已存在的 `job_key` 会计入 `skipped_existing_count`。

```powershell
boatrace-cal job-ledger-register-due `
  --ledger .\artifacts\jobs\ledger.json `
  --due .\artifacts\jobs\snapshot-due.json `
  --updated-at 2026-06-23T04:14:00+00:00 `
  --checkpoint snapshot-due-20260623T0414Z `
  --output .\artifacts\jobs\register-due.json
```

周期任务还应定期标记已经超过有效窗口且未完成的快照，避免后续补造赛前赔率：

```powershell
boatrace-cal job-ledger-mark-missed `
  --ledger .\artifacts\jobs\ledger.json `
  --plan .\artifacts\jobs\snapshot-plan.json `
  --now 2026-06-23T04:17:00+00:00 `
  --allowed-lateness-minutes 1 `
  --checkpoint missed-window-20260623T0417Z `
  --output .\artifacts\jobs\missed-window.json
```

该命令会把过窗且未进入终态的任务推进到 `skipped`，并记录 `last_error_code: MISSED_WINDOW`。已 `succeeded`、`failed` 或 `skipped` 的任务不会被覆盖。

## 失败重试策略

抓取执行器在任务处于 `running` 后，如果遇到失败，应使用 `job-ledger-record-failure`
把错误交给统一的重试策略处理，而不是在外部脚本里临时决定是否继续重试。

```powershell
boatrace-cal job-ledger-record-failure `
  --ledger .\artifacts\jobs\ledger.json `
  --job-key "official|05|2026-06-23|1|odds|T15" `
  --error-code FETCH_TIMEOUT `
  --observed-at 2026-06-23T04:16:00+00:00 `
  --max-attempts 3 `
  --base-delay-seconds 60 `
  --max-delay-seconds 300 `
  --window-expires-at 2026-06-23T04:20:00+00:00 `
  --checkpoint retry-policy-20260623T0416Z `
  --output .\artifacts\jobs\failure-decision.json
```

输出 JSON 的 `schema_version` 为 `job-retry-decision-v1`，包含 `decision` 和更新后的
`record`。当前策略只把 `FETCH_TIMEOUT` 和 `RATE_LIMITED` 视为可重试错误：

- 未超过 `--max-attempts` 且下一次重试未超过 `--window-expires-at` 时，任务进入 `retry_wait` 并写入 `next_retry_at`。
- 超过最大尝试次数时，任务进入 `failed`，原因码为 `max_attempts_exhausted`。
- 下一次重试会落在赛前有效窗口之外时，任务进入 `skipped`，原因码为 `retry_window_expired`，避免事后补抓覆盖赛前可用性。
- `SOURCE_UNAVAILABLE` 和 `PARSE_SCHEMA_CHANGED` 等非临时错误直接进入 `failed`，避免无限重试。
- 对限流响应可传入 `--retry-after-seconds`，优先使用来源返回的等待时间。

## 账本汇总

调度器或 UI 可以用 `job-ledger-summary` 只读汇总当前账本状态，检查是否存在到期重试任务或异常堆积：

```powershell
boatrace-cal job-ledger-summary `
  --ledger .\artifacts\jobs\ledger.json `
  --as-of 2026-06-23T04:18:00+00:00 `
  --output .\artifacts\jobs\ledger-summary.json
```

输出 JSON 的 `schema_version` 为 `job-ledger-summary-v1`，包含：

- `status_counts`: 各任务状态数量；
- `error_counts`: 当前账本中最后错误码的数量；
- `terminal_count`: 已进入 `succeeded`、`failed` 或 `skipped` 的任务数量；
- `retry_due_jobs`: `retry_wait` 且 `next_retry_at <= --as-of` 的任务键列表。

## T-5 赔率变化告警

T-10 冻结后，可以用 `odds-change-alert` 对比冻结时点和临近开赛时点可见的最新赔率：

```powershell
boatrace-cal odds-change-alert `
  --odds .\data\market\odds.csv `
  --race-date 2026-06-23 `
  --venue 05 `
  --race-no 1 `
  --bet-type trifecta_ordered `
  --frozen-as-of 2026-06-23T04:20:00+00:00 `
  --alert-as-of 2026-06-23T04:25:00+00:00 `
  --min-relative-change 0.10 `
  --output .\artifacts\alerts\odds-change-alert.json
```

输出 JSON 的 `schema_version` 为 `odds-change-alert-v1`，并固定包含：

- `alert_only: true`
- `action: review_required_no_overwrite`

这表示报告只用于提示人工复核或记录风险，不应自动覆盖 T-10 已冻结的确认清单。
