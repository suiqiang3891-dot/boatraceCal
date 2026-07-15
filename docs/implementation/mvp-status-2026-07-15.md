# MVP 开发状态记录（2026-07-15）

本记录用于区分“代码层面已实现并通过测试的能力”和“必须依赖真实官方数据、持续运行或浏览器环境才能验收的门禁”。项目不能把缺少外部证据的状态称为 100% 完成。

## 当前结论

代码层面的研究 MVP 已覆盖数据契约、赛前快照作业、概率评价、价值策略、回测报告、API 工作流和第一版 React 智能表格。当前最新验证证明这些模块在本地测试夹具和样例报告上可重复运行。

真实生产可用仍不是 100%。原因是官方数据源条款、robots、访问频率、真实长期数据回填、连续纸面模拟和真实浏览器视觉验收尚未完成。

## 已实现并有测试覆盖的能力

| 范围 | 已证明能力 | 主要证据 |
| --- | --- | --- |
| 领域契约 | 比赛、票种、组合、版本、推荐决策、时间因果字段校验 | `tests/domain/*` |
| 数据导入 | 结果、赔付、赔率、推荐 CSV 输入契约；隔离区响应清理报告 | `tests/ingestion/*`、`tests/validation/*` |
| 作业调度 | 快照计划、到期筛选、重试决策、作业账本、漏跑窗口和汇总报告 | `tests/jobs/*` |
| 模型评价 | 艇位频率、市场隐含概率、线性概率基线、时间切分、Log Loss、Brier、ECE、基线对比 | `tests/models/*` |
| 策略 | EV、保守 EV、SELECT/PASS、固定单位、风险预算 | `tests/strategies/*` |
| 回测 | 赛后结算、资金曲线、回撤、置信区间、月份/赔率区间/场地/票种切片、报告版本 | `tests/backtest/*` |
| API | 本地 OpenAPI 契约、候选查询、人工审核导入、确认清单、冻结归档、Excel 导出任务 | `tests/api/*` |
| UI | React/Vite 智能表格、筛选排序、ECharts 资金曲线、审核状态、本地导出和 API 同步入口 | `ui/src/*.test.*` |
| 审计版本 | 主要公开 JSON 报告带 `schema_version` 或 `artifact_type` | `tests/cli/test_cli.py`、各序列化测试 |

## 最新本地验证证据

以下命令在 `D:\boatraceCal\.worktrees\ui-review-actions-contract` 执行：

```powershell
python -m pytest
python -m ruff check .
python -m mypy src
git diff --check
codegraph index
```

观察结果：

- `python -m pytest`：440 passed。
- `python -m ruff check .`：All checks passed。
- `python -m mypy src`：Success: no issues found in 55 source files。
- `git diff --check`：退出码 0；仅有 Windows 工作树 LF/CRLF 提示。
- `codegraph index`：856 nodes，2,007 edges。

UI 验证也已重新执行：

```powershell
cd ui
npm test
npm run build
```

观察结果：

- `npm test`：2 个测试文件、17 个测试通过。
- `npm run build`：TypeScript 构建和 Vite 生产构建通过，生成 `dist/` 产物。

## 不能在本地直接声明完成的门禁

| 门禁 | 当前状态 | 完成条件 |
| --- | --- | --- |
| 官方数据源合规 | 未完成现场确认 | 明确 BOAT RACE 官方入口、robots、条款和可接受访问频率，并记录日期与依据 |
| 真实历史回填 | 未完成 | 用版本化配置导入真实历史数据，生成质量报告，并固定数据快照 |
| 长期纸面模拟 | 未完成 | 至少连续 14 天保存赛前冻结推荐、赛后结算和漂移报告 |
| 真实浏览器视觉验收 | 未完成 | 在实际浏览器中打开 UI，保存截图或录屏，核对桌面/移动布局、无重叠、图表非空、导入导出可用 |
| Python 最低版本 | 未完成 | 在 Python 3.12 环境运行 pytest、ruff、mypy |
| 外部依赖风险 | 部分完成 | 前端依赖已安装并锁定；后端运行依赖仍为空。需要在交付包中明确安装步骤 |

## 下一步开发顺序

1. 启动本地 Vite 服务，给出可访问 URL，并进行人工浏览器验收。
2. 继续版本化剩余公开 API/CLI 响应：候选查询响应、审核导入响应、作业账本单条查询和错误响应。
3. 制作真实数据接入前的合规核验清单；未确认前不启用持续采集。
4. 准备纸面模拟运行手册，明确每日输入、冻结时点、结算和报告归档路径。

## 100% 判定口径

“100% 完成”只能用于下面两种不同对象之一：

- 本地代码 MVP：所有计划内代码、文档、单元/集成/UI 构建验证通过，工作树干净，提交已推送。
- 真实业务 MVP：本地代码 MVP 之外，还要完成官方合规确认、真实数据回填、连续纸面模拟和浏览器视觉验收。

截至 2026-07-15，本项目可以继续冲刺“本地代码 MVP 100%”，但不能把“真实业务 MVP”声明为 100%。
