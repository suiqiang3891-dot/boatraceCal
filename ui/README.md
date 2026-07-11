# boatraceCal UI

第一版前端工作台默认读取 `examples/sample_backtest/report.json`，也可以在页面顶部用导入按钮加载本地 `backtest-report` JSON。页面展示回测总览、风险声明、资金曲线、切片表现、候选智能表格和行级解释。

当前 UI 是离线工作台，不连接服务端 HTTP API，也不提供自动下单。人工审核结果保存在当前浏览器，并可导出为：

- 审核表 XLSX：包含全部候选、人工状态、备注和版本信息。
- 审核 JSON：顶层使用 OpenAPI `ReviewImportRequest` 形状 `{ "reviews": [...] }`，可交给 `boatrace-cal review-store-import` 导入服务端文件 store。
- 确认清单 XLSX：只包含人工确认且单位数大于 0 的候选。

智能表格支持按日期、场地和审核/决策状态筛选，并支持按场次、模型概率或 EV 排序。所有筛选和审核动作只作用于浏览器本地状态，不会改写导入的回测报告。

## 本地查看

```powershell
npm install --no-audit --no-fund
npm run build
```

构建完成后可以直接打开 `dist/index.html` 查看静态版本，也可以运行：

```powershell
npm run dev -- --port 5173
```

## 验证

```powershell
npm run test
npm run build
```
