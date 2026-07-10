export type Tone = "positive" | "negative" | "neutral" | "warning";

type ReportSummary = {
  selected_bet_count: number;
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
  dimension: "venue" | "bet_type";
  key: string;
  selected_bet_count: number;
  hit_rate: string;
  return_rate: string;
  net_profit_yen: string;
};

type Settlement = {
  recommendation_id: string;
  race_id: string;
  stake_yen: string;
  returned_yen: string;
  net_profit_yen: string;
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
  summary: ReportSummary;
  equity_curve: {
    final_equity_yen: string;
    max_drawdown_yen: string;
    points: EquityPoint[];
  };
  slices: ReportSlice[];
  settlements: Settlement[];
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

export type SettlementRow = {
  id: string;
  raceId: string;
  status: string;
  combination: string;
  stake: string;
  returned: string;
  netProfit: string;
  tone: Tone;
};

export type DashboardModel = {
  statusLabel: string;
  riskNotice: string;
  summaryCards: SummaryCard[];
  sliceRows: SliceRow[];
  settlementRows: SettlementRow[];
  equityPoints: Array<{
    raceId: string;
    equityYen: number;
    drawdownYen: number;
  }>;
};

export function buildDashboardModel(report: BacktestReport): DashboardModel {
  return {
    statusLabel: report.readiness.status.toUpperCase(),
    riskNotice: "历史表现不代表未来结果；本系统只提供分析与回测，不承诺盈利，不提供自动下单。",
    summaryCards: [
      {
        label: "净收益",
        value: formatSignedYen(report.summary.net_profit_yen),
        tone: profitTone(report.summary.net_profit_yen),
      },
      {
        label: "回收率",
        value: formatRate(report.summary.return_rate),
        tone: rateTone(report.summary.return_rate, "1"),
      },
      {
        label: "命中率",
        value: formatRate(report.summary.hit_rate),
        tone: "neutral",
      },
      {
        label: "最大回撤",
        value: formatYen(report.equity_curve.max_drawdown_yen),
        tone: "warning",
      },
    ],
    sliceRows: report.slices.map((item) => ({
      dimensionLabel: dimensionLabel(item.dimension),
      key: item.key,
      selectedBetCount: item.selected_bet_count,
      hitRate: formatRate(item.hit_rate),
      returnRate: formatRate(item.return_rate),
      netProfit: formatSignedYen(item.net_profit_yen),
      tone: profitTone(item.net_profit_yen),
    })),
    settlementRows: report.settlements.map((item) => ({
      id: item.recommendation_id,
      raceId: item.race_id,
      status: statusLabel(item.settlement.status),
      combination: `${item.settlement.combination.bet_type} ${item.settlement.combination.lanes.join("-")}`,
      stake: formatYen(item.stake_yen),
      returned: formatYen(item.returned_yen),
      netProfit: formatSignedYen(item.net_profit_yen),
      tone: profitTone(item.net_profit_yen),
    })),
    equityPoints: report.equity_curve.points.map((point) => ({
      raceId: point.race_id,
      equityYen: Number(point.equity_yen),
      drawdownYen: Number(point.drawdown_yen),
    })),
  };
}

function dimensionLabel(dimension: ReportSlice["dimension"]): string {
  return dimension === "venue" ? "场地" : "票种";
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

function formatRate(value: string): string {
  return `${(Number(value) * 100).toFixed(1)}%`;
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
  const numeric = Number(value);
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
