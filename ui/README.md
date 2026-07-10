# boatraceCal UI

第一版前端工作台读取 `examples/sample_backtest/report.json`，展示回测总览、风险声明、资金曲线、切片表现和结算明细。

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
