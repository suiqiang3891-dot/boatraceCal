import sampleReport from "../../examples/sample_backtest/report.json";
import { buildDashboardModel, type BacktestReport } from "./reportMetrics";

const typedSampleReport = sampleReport as BacktestReport;
const sampleSettlements = typedSampleReport.settlements ?? [];

test("buildDashboardModel formats report metrics for the smart table workbench", () => {
  const model = buildDashboardModel(typedSampleReport);

  expect(model.reportSchemaVersion).toBe("backtest-report-v1");
  expect(model.statusLabel).toBe("READY");
  expect(model.riskNotice).toContain("历史表现不代表未来结果");
  expect(model.statusBar).toEqual({
    businessDate: "2025-01-02",
    freshness: "2025-01-02 10:15 UTC",
    venueCount: 1,
    raceCount: 2,
    candidateCount: 2,
    simulationBudget: "¥200",
  });
  expect(model.summaryCards).toEqual([
    { label: "净收益", value: "+¥900", tone: "positive" },
    { label: "回收率", value: "550.0%", tone: "positive" },
    { label: "命中率", value: "50.0%", tone: "neutral" },
    { label: "最大回撤", value: "¥100", tone: "warning" },
  ]);
  expect(model.confidenceIntervals).toEqual([
    {
      label: "净收益区间",
      pointEstimate: "+¥900",
      interval: "-¥200 至 +¥2,000",
      tone: "positive",
    },
    {
      label: "回收率区间",
      pointEstimate: "550.0%",
      interval: "0.0% 至 1100.0%",
      tone: "positive",
    },
    {
      label: "命中率区间",
      pointEstimate: "50.0%",
      interval: "0.0% 至 100.0%",
      tone: "neutral",
    },
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
    {
      dimensionLabel: "月份",
      key: "2025-01",
      selectedBetCount: 2,
      hitRate: "50.0%",
      returnRate: "550.0%",
      netProfit: "+¥900",
      tone: "positive",
    },
    {
      dimensionLabel: "赔率区间",
      key: "odds_3_to_10",
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
  expect(model.smartTableRows[0]).toMatchObject({
    id: "sample-rec-hit",
    venue: "01",
    raceNo: "1R",
    startTime: "等待赛前数据",
    combination: "三连单 1-2-3",
    modelProbability: "25.0%",
    marketOdds: "5.20",
    impliedProbability: "19.2%",
    expectedValue: "+30.0%",
    conservativeExpectedValue: "+24.0%",
    confidenceLabel: "高",
    stakeUnits: "1",
    decisionLabel: "候选",
    reviewStatus: "待审核",
    notes: "positive_ev / sample",
    freshness: "2025-01-02 10:00 UTC",
    settlementLabel: "命中",
  });
  const firstRow = model.smartTableRows[0];
  expect(firstRow.probabilityDetail).toContain("模型概率 25.0%");
  expect(firstRow.probabilityDetail).toContain("EV +30.0%");
  expect(firstRow.marketComparison).toContain("市场赔率 5.20");
  expect(firstRow.marketComparison).toContain("模型优势 +5.8个百分点");
  expect(firstRow.alternatives).toBe(
    "原因码 positive_ev / sample；策略建议 候选；历史回放 命中",
  );
  expect(firstRow.probabilityDetail).not.toContain("等待模型明细");
  expect(firstRow.alternatives).not.toContain("等待策略明细");
});

test("buildDashboardModel uses waiting placeholders for unavailable market fields", () => {
  const report: BacktestReport = {
    ...typedSampleReport,
    settlements: [
      {
        ...sampleSettlements[0],
        recommendation: {
          ...sampleSettlements[0].recommendation,
          odds: null,
          expected_value: null,
        },
      },
    ],
  };

  const model = buildDashboardModel(report);

  expect(model.smartTableRows[0].marketOdds).toBe("等待赛前数据");
  expect(model.smartTableRows[0].impliedProbability).toBe("等待赛前数据");
  expect(model.smartTableRows[0].expectedValue).toBe("等待赛前数据");
  expect(model.smartTableRows[0].conservativeExpectedValue).toBe("等待赛前数据");
  expect(model.smartTableRows[0].probabilityDetail).toContain("模型概率 25.0%");
  expect(model.smartTableRows[0].probabilityDetail).toContain("EV 等待赛前数据");
  expect(model.smartTableRows[0].marketComparison).toBe(
    "市场赔率等待赛前数据；无法计算隐含概率差",
  );
});

test("buildDashboardModel returns a safe empty model for blocked reports", () => {
  const model = buildDashboardModel({
    readiness: {
      status: "blocked",
      ready: false,
    },
    summary: null,
    equity_curve: null,
    slices: null,
    settlements: null,
  });

  expect(model.isReady).toBe(false);
  expect(model.statusLabel).toBe("BLOCKED");
  expect(model.statusBar.businessDate).toBe("等待赛前数据");
  expect(model.summaryCards[0]).toEqual({ label: "净收益", value: "¥0", tone: "neutral" });
  expect(model.confidenceIntervals).toEqual([]);
  expect(model.smartTableRows).toEqual([]);
  expect(model.equityPoints).toEqual([]);
});

test("buildDashboardModel shows a date range for multi-day reports", () => {
  const report: BacktestReport = {
    ...typedSampleReport,
    settlements: [
      sampleSettlements[0],
      {
        ...sampleSettlements[1],
        race_id: "20250103-01-02",
      },
    ],
  };

  const model = buildDashboardModel(report);

  expect(model.statusBar.businessDate).toBe("2025-01-02 至 2025-01-03");
});
