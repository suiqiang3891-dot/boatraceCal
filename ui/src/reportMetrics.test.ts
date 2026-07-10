import sampleReport from "../../examples/sample_backtest/report.json";
import { buildDashboardModel, type BacktestReport } from "./reportMetrics";

test("buildDashboardModel formats report metrics for the first UI dashboard", () => {
  const model = buildDashboardModel(sampleReport as BacktestReport);

  expect(model.statusLabel).toBe("READY");
  expect(model.riskNotice).toContain("历史表现不代表未来结果");
  expect(model.summaryCards).toEqual([
    { label: "净收益", value: "+¥900", tone: "positive" },
    { label: "回收率", value: "550.0%", tone: "positive" },
    { label: "命中率", value: "50.0%", tone: "neutral" },
    { label: "最大回撤", value: "¥100", tone: "warning" },
  ]);
  expect(model.sliceRows).toEqual([
    {
      dimensionLabel: "场地",
      key: "01",
      selectedBetCount: 2,
      hitRate: "50.0%",
      returnRate: "550.0%",
      netProfit: "+¥900",
      tone: "positive",
    },
    {
      dimensionLabel: "票种",
      key: "trifecta_ordered",
      selectedBetCount: 2,
      hitRate: "50.0%",
      returnRate: "550.0%",
      netProfit: "+¥900",
      tone: "positive",
    },
  ]);
  expect(model.equityPoints).toEqual([
    { raceId: "20250102-01-01", equityYen: 1000, drawdownYen: 0 },
    { raceId: "20250102-01-02", equityYen: 900, drawdownYen: 100 },
  ]);
});
