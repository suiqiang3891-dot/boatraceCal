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
