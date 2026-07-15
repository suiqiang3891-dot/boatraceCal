export type Tone = "positive" | "negative" | "neutral" | "warning";

const WAITING_FOR_PRERACE_DATA = "等待赛前数据";

type ReportSummary = {
  expected_race_count: number;
  selected_bet_count: number;
  selected_race_count: number;
  hit_count: number;
  miss_count: number;
  net_profit_yen: string;
  return_rate: string;
  hit_rate: string;
  total_stake_yen: string;
  total_returned_yen: string;
};

type EquityPoint = {
  race_id: string;
  equity_yen: string;
  drawdown_yen: string;
};

type ReportSlice = {
  dimension: "venue" | "bet_type" | "race_month" | "odds_band";
  key: string;
  selected_bet_count: number;
  hit_rate: string;
  return_rate: string;
  net_profit_yen: string;
};

type ReportMetricInterval = {
  name: "net_profit_yen" | "return_rate" | "hit_rate";
  point_estimate: string;
  lower: string;
  upper: string;
};

type ReportConfidenceIntervals = {
  metrics: ReportMetricInterval[];
};

type RecommendationSnapshot = {
  stage: "preplan" | "final";
  decision: "select" | "pass";
  confidence: "low" | "medium" | "high";
  probability: string;
  odds: string | null;
  expected_value: string | null;
  as_of: string;
  stake_units: number;
  versions: {
    data: string;
    feature: string;
    model: string;
    strategy: string;
  };
  reason_codes: string[];
};

type Settlement = {
  recommendation_id: string;
  race_id: string;
  stake_units: number;
  stake_yen: string;
  returned_yen: string;
  net_profit_yen: string;
  recommendation: RecommendationSnapshot;
  settlement: {
    status: "hit" | "miss" | "payout_missing";
    combination: {
      bet_type: string;
      lanes: number[];
    };
  };
};

export type BacktestReport = {
  readiness: {
    status: string;
    ready: boolean;
  };
  summary: ReportSummary | null;
  equity_curve: {
    final_equity_yen: string;
    max_drawdown_yen: string;
    points: EquityPoint[];
  } | null;
  slices: ReportSlice[] | null;
  settlements: Settlement[] | null;
  confidence_intervals?: ReportConfidenceIntervals | null;
};

export type SummaryCard = {
  label: string;
  value: string;
  tone: Tone;
};

export type SliceRow = {
  dimensionLabel: string;
  key: string;
  selectedBetCount: number;
  hitRate: string;
  returnRate: string;
  netProfit: string;
  tone: Tone;
};

export type ConfidenceIntervalRow = {
  label: string;
  pointEstimate: string;
  interval: string;
  tone: Tone;
};

export type SmartTableRow = {
  id: string;
  raceId: string;
  venue: string;
  raceNo: string;
  startTime: string;
  combination: string;
  modelProbability: string;
  marketOdds: string;
  impliedProbability: string;
  expectedValue: string;
  expectedValueTone: Tone;
  conservativeExpectedValue: string;
  conservativeExpectedValueTone: Tone;
  confidenceLabel: string;
  confidenceTone: Tone;
  stakeUnits: string;
  decisionLabel: string;
  reviewStatus: string;
  notes: string;
  freshness: string;
  settlementLabel: string;
  settlementTone: Tone;
  dataVersion: string;
  featureVersion: string;
  modelVersion: string;
  strategyVersion: string;
  probabilityDetail: string;
  marketComparison: string;
  supportFactors: string[];
  alternatives: string;
};

export type DashboardModel = {
  statusLabel: string;
  isReady: boolean;
  riskNotice: string;
  statusBar: {
    businessDate: string;
    freshness: string;
    venueCount: number;
    raceCount: number;
    candidateCount: number;
    simulationBudget: string;
  };
  summaryCards: SummaryCard[];
  confidenceIntervals: ConfidenceIntervalRow[];
  sliceRows: SliceRow[];
  smartTableRows: SmartTableRow[];
  equityPoints: Array<{
    raceId: string;
    equityYen: number;
    drawdownYen: number;
  }>;
};

export function buildDashboardModel(report: BacktestReport): DashboardModel {
  const summary = report.summary ?? emptySummary();
  const equityCurve = report.equity_curve ?? emptyEquityCurve();
  const slices = report.slices ?? [];
  const smartTableRows = (report.settlements ?? []).map(toSmartTableRow);

  return {
    statusLabel: report.readiness.status.toUpperCase(),
    isReady: report.readiness.ready,
    riskNotice: "历史表现不代表未来结果；本系统只提供分析与回测，不承诺盈利，不提供自动下单。",
    statusBar: {
      businessDate: businessDateFromRows(smartTableRows),
      freshness: latestFreshness(smartTableRows),
      venueCount: new Set(smartTableRows.map((row) => row.venue)).size,
      raceCount: new Set(smartTableRows.map((row) => row.raceId)).size,
      candidateCount: smartTableRows.length,
      simulationBudget: formatYen(summary.total_stake_yen),
    },
    summaryCards: [
      {
        label: "净收益",
        value: formatSignedYen(summary.net_profit_yen),
        tone: profitTone(summary.net_profit_yen),
      },
      {
        label: "回收率",
        value: formatRate(summary.return_rate),
        tone: rateTone(summary.return_rate, "1"),
      },
      {
        label: "命中率",
        value: formatRate(summary.hit_rate),
        tone: "neutral",
      },
      {
        label: "最大回撤",
        value: formatYen(equityCurve.max_drawdown_yen),
        tone: "warning",
      },
    ],
    confidenceIntervals: buildConfidenceIntervals(report.confidence_intervals),
    sliceRows: slices.map((item) => ({
      dimensionLabel: dimensionLabel(item.dimension),
      key: item.key,
      selectedBetCount: item.selected_bet_count,
      hitRate: formatRate(item.hit_rate),
      returnRate: formatRate(item.return_rate),
      netProfit: formatSignedYen(item.net_profit_yen),
      tone: profitTone(item.net_profit_yen),
    })),
    smartTableRows,
    equityPoints: equityCurve.points.map((point) => ({
      raceId: point.race_id,
      equityYen: Number(point.equity_yen),
      drawdownYen: Number(point.drawdown_yen),
    })),
  };
}

function buildConfidenceIntervals(
  intervals: ReportConfidenceIntervals | null | undefined,
): ConfidenceIntervalRow[] {
  if (!intervals) {
    return [];
  }
  return intervals.metrics.map(toConfidenceIntervalRow);
}

function toConfidenceIntervalRow(metric: ReportMetricInterval): ConfidenceIntervalRow {
  if (metric.name === "net_profit_yen") {
    return {
      label: "净收益区间",
      pointEstimate: formatSignedYen(metric.point_estimate),
      interval: `${formatSignedYen(metric.lower)} 至 ${formatSignedYen(metric.upper)}`,
      tone: profitTone(metric.point_estimate),
    };
  }
  if (metric.name === "return_rate") {
    return {
      label: "回收率区间",
      pointEstimate: formatRate(metric.point_estimate),
      interval: `${formatRate(metric.lower)} 至 ${formatRate(metric.upper)}`,
      tone: rateTone(metric.point_estimate, "1"),
    };
  }
  return {
    label: "命中率区间",
    pointEstimate: formatRate(metric.point_estimate),
    interval: `${formatRate(metric.lower)} 至 ${formatRate(metric.upper)}`,
    tone: "neutral",
  };
}

function emptySummary(): ReportSummary {
  return {
    expected_race_count: 0,
    selected_bet_count: 0,
    selected_race_count: 0,
    hit_count: 0,
    miss_count: 0,
    net_profit_yen: "0",
    return_rate: "0",
    hit_rate: "0",
    total_stake_yen: "0",
    total_returned_yen: "0",
  };
}

function emptyEquityCurve(): NonNullable<BacktestReport["equity_curve"]> {
  return {
    final_equity_yen: "0",
    max_drawdown_yen: "0",
    points: [],
  };
}

function toSmartTableRow(item: Settlement): SmartTableRow {
  const parsedRace = parseRaceId(item.race_id);
  const probability = Number(item.recommendation.probability);
  const odds = parseOptionalNumber(item.recommendation.odds);
  const expectedValue = parseOptionalNumber(item.recommendation.expected_value);
  const impliedProbability = odds === null ? null : 1 / odds;
  const conservativeExpectedValue =
    expectedValue === null ? null : expectedValue * 0.8;

  return {
    id: item.recommendation_id,
    raceId: item.race_id,
    venue: parsedRace.venue,
    raceNo: `${parsedRace.raceNo}R`,
    startTime: WAITING_FOR_PRERACE_DATA,
    combination: `${betTypeLabel(item.settlement.combination.bet_type)} ${item.settlement.combination.lanes.join("-")}`,
    modelProbability: formatPercent(probability),
    marketOdds: odds === null ? WAITING_FOR_PRERACE_DATA : odds.toFixed(2),
    impliedProbability:
      impliedProbability === null ? WAITING_FOR_PRERACE_DATA : formatPercent(impliedProbability),
    expectedValue:
      expectedValue === null ? WAITING_FOR_PRERACE_DATA : formatSignedPercent(expectedValue),
    expectedValueTone: valueTone(expectedValue),
    conservativeExpectedValue:
      conservativeExpectedValue === null
        ? WAITING_FOR_PRERACE_DATA
        : formatSignedPercent(conservativeExpectedValue),
    conservativeExpectedValueTone: valueTone(conservativeExpectedValue),
    confidenceLabel: confidenceLabel(item.recommendation.confidence),
    confidenceTone: confidenceTone(item.recommendation.confidence),
    stakeUnits: item.stake_units.toString(),
    decisionLabel: decisionLabel(item.recommendation.decision),
    reviewStatus: "待审核",
    notes: item.recommendation.reason_codes.join(" / "),
    freshness: formatTimestamp(item.recommendation.as_of),
    settlementLabel: statusLabel(item.settlement.status),
    settlementTone: settlementTone(item.settlement.status),
    dataVersion: item.recommendation.versions.data,
    featureVersion: item.recommendation.versions.feature,
    modelVersion: item.recommendation.versions.model,
    strategyVersion: item.recommendation.versions.strategy,
    probabilityDetail: probabilityDetail(probability, expectedValue, conservativeExpectedValue),
    marketComparison: marketComparison(probability, odds, impliedProbability),
    supportFactors: item.recommendation.reason_codes,
    alternatives: strategyExplanation(item.recommendation, item.settlement.status),
  };
}

function parseRaceId(raceId: string): { businessDate: string; venue: string; raceNo: string } {
  const [compactDate = "", venue = "", raceNo = ""] = raceId.split("-");
  return {
    businessDate: compactDate.replace(/^(\d{4})(\d{2})(\d{2})$/, "$1-$2-$3"),
    venue,
    raceNo: String(Number(raceNo)),
  };
}

function businessDateFromRows(rows: SmartTableRow[]): string {
  if (rows.length === 0) {
    return WAITING_FOR_PRERACE_DATA;
  }
  const dates = rows.map((row) => parseRaceId(row.raceId).businessDate).sort();
  const firstDate = dates[0];
  const lastDate = dates[dates.length - 1];
  return firstDate === lastDate ? firstDate : `${firstDate} 至 ${lastDate}`;
}

function latestFreshness(rows: SmartTableRow[]): string {
  return rows.reduce(
    (latest, row) => (latest.localeCompare(row.freshness) > 0 ? latest : row.freshness),
    rows[0]?.freshness ?? WAITING_FOR_PRERACE_DATA,
  );
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  const hour = String(date.getUTCHours()).padStart(2, "0");
  const minute = String(date.getUTCMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute} UTC`;
}

function dimensionLabel(dimension: ReportSlice["dimension"]): string {
  if (dimension === "venue") {
    return "场地";
  }
  if (dimension === "bet_type") {
    return "票种";
  }
  if (dimension === "race_month") {
    return "月份";
  }
  return "赔率区间";
}

function betTypeLabel(betType: string): string {
  return betType === "trifecta_ordered" ? "三连单" : betType;
}

function statusLabel(status: Settlement["settlement"]["status"]): string {
  if (status === "hit") {
    return "命中";
  }
  if (status === "miss") {
    return "未中";
  }
  return "缺赔付";
}

function settlementTone(status: Settlement["settlement"]["status"]): Tone {
  if (status === "hit") {
    return "positive";
  }
  if (status === "miss") {
    return "negative";
  }
  return "warning";
}

function confidenceLabel(confidence: RecommendationSnapshot["confidence"]): string {
  if (confidence === "high") {
    return "高";
  }
  if (confidence === "medium") {
    return "中";
  }
  return "低";
}

function confidenceTone(confidence: RecommendationSnapshot["confidence"]): Tone {
  if (confidence === "high") {
    return "positive";
  }
  if (confidence === "medium") {
    return "warning";
  }
  return "neutral";
}

function decisionLabel(decision: RecommendationSnapshot["decision"]): string {
  return decision === "select" ? "候选" : "PASS";
}

function probabilityDetail(
  probability: number,
  expectedValue: number | null,
  conservativeExpectedValue: number | null,
): string {
  const evDetail =
    expectedValue === null
      ? "EV 等待赛前数据"
      : `EV ${formatSignedPercent(expectedValue)}`;
  const conservativeDetail =
    conservativeExpectedValue === null
      ? "保守EV 等待赛前数据"
      : `保守EV ${formatSignedPercent(conservativeExpectedValue)}`;
  return `模型概率 ${formatPercent(probability)}；${evDetail}；${conservativeDetail}`;
}

function marketComparison(
  probability: number,
  odds: number | null,
  impliedProbability: number | null,
): string {
  if (odds === null || impliedProbability === null) {
    return "市场赔率等待赛前数据；无法计算隐含概率差";
  }
  const edge = probability - impliedProbability;
  return `市场赔率 ${odds.toFixed(2)}，隐含概率 ${formatPercent(
    impliedProbability,
  )}；模型优势 ${formatSignedPointDelta(edge)}`;
}

function strategyExplanation(
  recommendation: RecommendationSnapshot,
  settlementStatus: Settlement["settlement"]["status"],
): string {
  const reasonCodes =
    recommendation.reason_codes.length > 0 ? recommendation.reason_codes.join(" / ") : "未提供";
  return `原因码 ${reasonCodes}；策略建议 ${decisionLabel(
    recommendation.decision,
  )}；历史回放 ${statusLabel(settlementStatus)}`;
}

function parseOptionalNumber(value: string | null): number | null {
  return value === null ? null : Number(value);
}

function formatRate(value: string): string {
  return formatPercent(Number(value));
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatSignedPercent(value: number): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${formatPercent(value)}`;
}

function formatSignedPointDelta(value: number): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${(value * 100).toFixed(1)}个百分点`;
}

function formatYen(value: string): string {
  return `¥${formatInteger(value)}`;
}

function formatSignedYen(value: string): string {
  const numeric = Number(value);
  const prefix = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
  return `${prefix}¥${formatInteger(Math.abs(numeric).toString())}`;
}

function formatInteger(value: string): string {
  return Number(value).toLocaleString("ja-JP", { maximumFractionDigits: 0 });
}

function profitTone(value: string): Tone {
  return valueTone(Number(value));
}

function valueTone(value: number | null): Tone {
  if (value === null) {
    return "warning";
  }
  const numeric = value;
  if (numeric > 0) {
    return "positive";
  }
  if (numeric < 0) {
    return "negative";
  }
  return "neutral";
}

function rateTone(value: string, baseline: string): Tone {
  return Number(value) >= Number(baseline) ? "positive" : "negative";
}
