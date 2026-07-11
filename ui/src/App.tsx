import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Download,
  FileCheck2,
  Minus,
  Plus,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { useMemo, useState } from "react";
import sampleReport from "../../examples/sample_backtest/report.json";
import { EquityChart } from "./EquityChart";
import {
  buildDashboardModel,
  type BacktestReport,
  type SmartTableRow,
  type Tone,
} from "./reportMetrics";
import "./styles.css";

type FilterKey = "all" | "select" | "wait" | "pass" | "confirmed";

const filters: Array<{ key: FilterKey; label: string }> = [
  { key: "all", label: "全部" },
  { key: "select", label: "候选" },
  { key: "wait", label: "WAIT" },
  { key: "pass", label: "PASS" },
  { key: "confirmed", label: "已确认" },
];

const REVIEW_STORAGE_PREFIX = "boatraceCal.reviewState";

type ReviewDecision = "pending" | "confirmed" | "pass";

type ReviewState = {
  decision: ReviewDecision;
  stakeUnits: number;
  notes: string;
};

type ReviewStateMap = Record<string, ReviewState>;

type ReviewableRow = SmartTableRow & {
  reviewDecision: ReviewDecision;
  displayStakeUnits: string;
  displayReviewStatus: string;
  reviewStatusTone: Tone;
  displayNotes: string;
  displayDecisionLabel: string;
  decisionTone: Tone;
};

function App({ report = sampleReport as BacktestReport }: { report?: BacktestReport }) {
  const model = useMemo(() => buildDashboardModel(report), [report]);
  const reviewStorageKey = useMemo(
    () => buildReviewStorageKey(model.smartTableRows, model.statusBar.businessDate),
    [model.smartTableRows, model.statusBar.businessDate],
  );
  const [reviewState, setReviewState] = useState<ReviewStateMap>(() =>
    loadReviewState(reviewStorageKey, model.smartTableRows),
  );
  const [filter, setFilter] = useState<FilterKey>("all");
  const reviewRows = useMemo(
    () => model.smartTableRows.map((row) => applyReviewState(row, reviewState[row.id])),
    [model.smartTableRows, reviewState],
  );
  const filteredRows = useMemo(
    () => reviewRows.filter((row) => rowMatchesFilter(row, filter)),
    [filter, reviewRows],
  );
  const [selectedRowId, setSelectedRowId] = useState(model.smartTableRows[0]?.id ?? "");
  const selectedRow = useMemo(
    () =>
      filteredRows.find((row) => row.id === selectedRowId) ??
      filteredRows[0] ??
      reviewRows[0],
    [filteredRows, reviewRows, selectedRowId],
  );
  const reviewCounts = useMemo(() => countReviewRows(reviewRows), [reviewRows]);

  const updateReview = (
    row: SmartTableRow,
    updater: (state: ReviewState) => ReviewState,
  ) => {
    setReviewState((current) => {
      const existing = current[row.id] ?? defaultReviewState(row);
      const next = {
        ...current,
        [row.id]: updater(existing),
      };
      saveReviewState(reviewStorageKey, next);
      return next;
    });
  };

  const handleConfirm = (row: ReviewableRow) => {
    updateReview(row, (state) => ({ ...state, decision: "confirmed" }));
  };

  const handlePass = (row: ReviewableRow) => {
    updateReview(row, (state) => ({ ...state, decision: "pass" }));
  };

  const handleStakeChange = (row: ReviewableRow, delta: number) => {
    updateReview(row, (state) => ({
      ...state,
      stakeUnits: Math.max(0, state.stakeUnits + delta),
    }));
  };

  const handleNotesChange = (row: ReviewableRow, notes: string) => {
    updateReview(row, (state) => ({ ...state, notes }));
  };

  const handleReset = (row: ReviewableRow) => {
    setReviewState((current) => {
      const next = { ...current };
      delete next[row.id];
      saveReviewState(reviewStorageKey, next);
      return next;
    });
  };

  const handleExport = () => {
    exportReviewRows(reviewRows, model.statusBar.businessDate, model.riskNotice);
  };

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div className="title-block">
          <p className="eyebrow">smart table</p>
          <h1>BOAT RACE 智能表格工作台</h1>
        </div>
        <dl className="status-grid" aria-label="清单状态">
          <StatusItem label="业务日期" value={model.statusBar.businessDate} />
          <StatusItem label="生成状态" value={model.statusLabel} />
          <StatusItem label="新鲜度" value={model.statusBar.freshness} />
          <StatusItem label="场地" value={`${model.statusBar.venueCount}`} />
          <StatusItem label="场次" value={`${model.statusBar.raceCount}`} />
          <StatusItem label="候选" value={`${model.statusBar.candidateCount}`} />
          <StatusItem label="预算" value={model.statusBar.simulationBudget} />
        </dl>
        <div className="header-actions">
          <span className="risk-inline">
            <AlertTriangle size={16} aria-hidden="true" />
            风险警告
          </span>
          <button
            className="icon-button"
            type="button"
            aria-label="导出 Excel"
            title="导出 Excel 兼容 CSV"
            disabled={reviewRows.length === 0}
            onClick={handleExport}
          >
            <Download size={17} aria-hidden="true" />
          </button>
          <button className="icon-button" type="button" aria-label="确认明日清单" disabled>
            <FileCheck2 size={17} aria-hidden="true" />
          </button>
        </div>
      </header>

      <section className="risk-strip" aria-label="风险声明">
        <ShieldCheck size={16} aria-hidden="true" />
        <span>{model.riskNotice}</span>
      </section>

      <section className="summary-strip" aria-label="核心指标">
        {model.summaryCards.map((card) => (
          <article className={`summary-chip tone-${card.tone}`} key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </article>
        ))}
      </section>

      <section className="filter-row" aria-label="清单筛选">
        <div className="segment-control" aria-label="决策筛选">
          {filters.map((item) => (
            <button
              type="button"
              className={item.key === filter ? "segment-active" : ""}
              aria-pressed={item.key === filter}
              key={item.key}
              onClick={() => setFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="filter-meta">
          <SlidersHorizontal size={16} aria-hidden="true" />
          <span>模型 {selectedRow?.modelVersion ?? "等待赛前数据"}</span>
          <span>
            审核 已确认 {reviewCounts.confirmed} / PASS {reviewCounts.pass} / 待审{" "}
            {reviewCounts.pending}
          </span>
        </div>
      </section>

      <section className="workbench-grid">
        <section className="table-panel" aria-labelledby="smart-table-title">
          <div className="panel-heading compact">
            <div>
              <p className="eyebrow">candidate list</p>
              <h2 id="smart-table-title">候选组合智能表格</h2>
            </div>
            <span className="table-count">候选 {filteredRows.length}</span>
          </div>
          <SmartTable
            rows={filteredRows}
            selectedRowId={selectedRow?.id ?? ""}
            onSelect={setSelectedRowId}
          />
        </section>

        <aside className="detail-panel" aria-labelledby="detail-title">
          {selectedRow ? (
            <DetailPanel
              row={selectedRow}
              onConfirm={handleConfirm}
              onPass={handlePass}
              onReset={handleReset}
              onNotesChange={handleNotesChange}
              onStakeChange={handleStakeChange}
            />
          ) : (
            <EmptyDetailPanel />
          )}
        </aside>
      </section>

      <section className="context-grid" aria-label="回测上下文">
        <section className="panel chart-panel" aria-labelledby="equity-title">
          <div className="panel-heading compact">
            <div>
              <p className="eyebrow">equity</p>
              <h2 id="equity-title">资金曲线</h2>
            </div>
          </div>
          <EquityChart points={model.equityPoints} />
        </section>
        <section className="panel" aria-labelledby="slice-title">
          <div className="panel-heading compact">
            <div>
              <p className="eyebrow">segments</p>
              <h2 id="slice-title">切片表现</h2>
            </div>
          </div>
          <div className="mini-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>维度</th>
                  <th>键</th>
                  <th>投注</th>
                  <th>命中</th>
                  <th>回收</th>
                  <th>盈亏</th>
                </tr>
              </thead>
              <tbody>
                {model.sliceRows.map((row) => (
                  <tr key={`${row.dimensionLabel}-${row.key}`}>
                    <td>{row.dimensionLabel}</td>
                    <td>{row.key}</td>
                    <td>{row.selectedBetCount}</td>
                    <td>{row.hitRate}</td>
                    <td>{row.returnRate}</td>
                    <td className={toneClass(row.tone)}>{row.netProfit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </main>
  );
}

function rowMatchesFilter(row: ReviewableRow, filter: FilterKey): boolean {
  if (filter === "all") {
    return true;
  }
  if (filter === "select") {
    return row.displayDecisionLabel === "候选";
  }
  if (filter === "wait") {
    return row.startTime === "等待赛前数据" || row.marketOdds === "等待赛前数据";
  }
  if (filter === "pass") {
    return row.displayDecisionLabel === "PASS";
  }
  return row.reviewDecision === "confirmed";
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function SmartTable({
  rows,
  selectedRowId,
  onSelect,
}: {
  rows: ReviewableRow[];
  selectedRowId: string;
  onSelect: (id: string) => void;
}) {
  if (rows.length === 0) {
    return (
      <div className="empty-state" role="status">
        没有可显示候选
      </div>
    );
  }

  return (
    <div className="smart-table-wrap">
      <table className="smart-table">
        <thead>
          <tr>
            <th className="sticky-col">场地</th>
            <th>场次</th>
            <th>开赛时间</th>
            <th>组合</th>
            <th>模型概率</th>
            <th>市场赔率</th>
            <th>隐含概率</th>
            <th>EV</th>
            <th>保守EV</th>
            <th>置信度</th>
            <th>建议单位</th>
            <th>决策</th>
            <th>审核状态</th>
            <th>备注</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr className={row.id === selectedRowId ? "selected-row" : ""} key={row.id}>
              <td className="sticky-col">
                <button
                  className="row-selector"
                  type="button"
                  aria-label={`选择 ${row.raceId} ${row.combination}`}
                  onClick={() => onSelect(row.id)}
                >
                  {row.venue}
                </button>
              </td>
              <td>{row.raceNo}</td>
              <td className="muted-cell">{row.startTime}</td>
              <td>{row.combination}</td>
              <td className="number-cell">{row.modelProbability}</td>
              <td className="number-cell">{row.marketOdds}</td>
              <td className="number-cell">{row.impliedProbability}</td>
              <td className={`number-cell ${toneClass(row.expectedValueTone)}`}>
                {row.expectedValue}
              </td>
              <td className={`number-cell ${toneClass(row.conservativeExpectedValueTone)}`}>
                {row.conservativeExpectedValue}
              </td>
              <td>
                <span className={`status-tag tag-${row.confidenceTone}`}>
                  {row.confidenceLabel}
                </span>
              </td>
              <td className="number-cell">{row.displayStakeUnits}</td>
              <td>
                <span className={`status-tag tag-${row.decisionTone}`}>
                  {row.displayDecisionLabel}
                </span>
              </td>
              <td>
                <span className={`status-tag tag-${row.reviewStatusTone}`}>
                  {row.displayReviewStatus}
                </span>
              </td>
              <td className="notes-cell">{row.displayNotes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyDetailPanel() {
  return (
    <div className="empty-detail" role="status">
      <p className="eyebrow">row detail</p>
      <h2 id="detail-title">行级详情</h2>
      <p>没有可显示候选，等待数据质量检查或筛选条件调整。</p>
    </div>
  );
}

function DetailPanel({
  row,
  onConfirm,
  onPass,
  onReset,
  onNotesChange,
  onStakeChange,
}: {
  row: ReviewableRow;
  onConfirm: (row: ReviewableRow) => void;
  onPass: (row: ReviewableRow) => void;
  onReset: (row: ReviewableRow) => void;
  onNotesChange: (row: ReviewableRow, notes: string) => void;
  onStakeChange: (row: ReviewableRow, delta: number) => void;
}) {
  const displayedStakeUnits = Number(row.displayStakeUnits);

  return (
    <>
      <div className="detail-heading">
        <div>
          <p className="eyebrow">row detail</p>
          <h2 id="detail-title">行级详情</h2>
        </div>
        <span className={`status-tag tag-${row.settlementTone}`}>{row.settlementLabel}</span>
      </div>
      <h3>{row.raceId}</h3>
      <dl className="detail-list">
        <DetailItem label="组合" value={row.combination} />
        <DetailItem label="六艇概率构成" value={row.probabilityDetail} />
        <DetailItem label="模型 / 市场" value={row.marketComparison} />
        <DetailItem label="置信度" value={row.confidenceLabel} />
        <DetailItem label="数据新鲜度" value={row.freshness} />
        <DetailItem label="审核状态" value={row.displayReviewStatus} />
        <DetailItem label="模拟单位" value={`${row.displayStakeUnits} 单位`} />
        <DetailItem label="备选与拒绝原因" value={row.alternatives} />
      </dl>
      <section className="support-section" aria-label="主要支持因素">
        <h4>主要支持因素</h4>
        <div className="tag-row">
          {row.supportFactors.map((factor) => (
            <span className="reason-tag" key={factor}>
              {factor}
            </span>
          ))}
        </div>
      </section>
      <section className="support-section" aria-label="版本信息">
        <h4>版本信息</h4>
        <dl className="version-grid">
          <DetailItem label="数据" value={row.dataVersion} />
          <DetailItem label="特征" value={row.featureVersion} />
          <DetailItem label="模型" value={row.modelVersion} />
          <DetailItem label="策略" value={row.strategyVersion} />
        </dl>
      </section>
      <section className="support-section" aria-label="人工审核">
        <h4>人工审核</h4>
        <label className="notes-editor">
          <span>备注</span>
          <textarea
            aria-label="审核备注"
            value={row.displayNotes}
            onChange={(event) => onNotesChange(row, event.target.value)}
          />
        </label>
        <div className="detail-actions" aria-label="审核操作">
          <div className="unit-stepper" aria-label="模拟单位">
            <button
              className="square-action"
              type="button"
              aria-label="减少模拟单位"
              disabled={displayedStakeUnits <= 0}
              onClick={() => onStakeChange(row, -1)}
            >
              <Minus size={15} aria-hidden="true" />
            </button>
            <output aria-label="当前模拟单位">{row.displayStakeUnits} 单位</output>
            <button
              className="square-action"
              type="button"
              aria-label="增加模拟单位"
              onClick={() => onStakeChange(row, 1)}
            >
              <Plus size={15} aria-hidden="true" />
            </button>
          </div>
          <button
            className="primary-action"
            type="button"
            aria-label="确认候选"
            onClick={() => onConfirm(row)}
          >
            <CheckCircle2 size={15} aria-hidden="true" />
            确认
          </button>
          <button
            className="warning-action"
            type="button"
            aria-label="人工 PASS"
            onClick={() => onPass(row)}
          >
            <Ban size={15} aria-hidden="true" />
            PASS
          </button>
          <button
            className="square-action"
            type="button"
            aria-label="重置审核"
            onClick={() => onReset(row)}
          >
            <RotateCcw size={15} aria-hidden="true" />
          </button>
        </div>
        <p className="inline-hint">审核修改会自动保存到当前浏览器，接入 API 后再迁移为服务端持久化。</p>
      </section>
    </>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function toneClass(tone: Tone): string {
  return `text-${tone}`;
}

function applyReviewState(row: SmartTableRow, review?: ReviewState): ReviewableRow {
  const state = review ?? defaultReviewState(row);
  const isPass = state.decision === "pass";
  const isConfirmed = state.decision === "confirmed";

  return {
    ...row,
    reviewDecision: state.decision,
    displayStakeUnits: state.stakeUnits.toString(),
    displayReviewStatus: isPass ? "已PASS" : isConfirmed ? "已确认" : row.reviewStatus,
    reviewStatusTone: isPass ? "neutral" : isConfirmed ? "positive" : "warning",
    displayNotes: state.notes,
    displayDecisionLabel: isPass ? "PASS" : row.decisionLabel,
    decisionTone: isPass ? "neutral" : row.decisionLabel === "候选" ? "positive" : "neutral",
  };
}

function defaultReviewState(row: SmartTableRow): ReviewState {
  return {
    decision: "pending",
    stakeUnits: Number(row.stakeUnits) || 0,
    notes: row.notes,
  };
}

function countReviewRows(rows: ReviewableRow[]): Record<ReviewDecision, number> {
  return rows.reduce(
    (counts, row) => {
      counts[row.reviewDecision] += 1;
      return counts;
    },
    { pending: 0, confirmed: 0, pass: 0 },
  );
}

function buildReviewStorageKey(rows: SmartTableRow[], businessDate: string): string {
  const identity = rows
    .map((row) =>
      [
        row.id,
        row.raceId,
        row.dataVersion,
        row.featureVersion,
        row.modelVersion,
        row.strategyVersion,
      ].join(":"),
    )
    .join("|");
  return `${REVIEW_STORAGE_PREFIX}:${businessDate}:${hashString(identity)}`;
}

function loadReviewState(key: string, rows: SmartTableRow[]): ReviewStateMap {
  try {
    const rawValue = localStorage.getItem(key);
    if (!rawValue) {
      return {};
    }
    const parsed = JSON.parse(rawValue) as unknown;
    const rowIds = new Set(rows.map((row) => row.id));
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    return Object.entries(parsed as Record<string, unknown>).reduce<ReviewStateMap>(
      (state, [id, value]) => {
        if (!rowIds.has(id) || !isReviewState(value)) {
          return state;
        }
        state[id] = value;
        return state;
      },
      {},
    );
  } catch {
    return {};
  }
}

function saveReviewState(key: string, state: ReviewStateMap): void {
  try {
    if (Object.keys(state).length === 0) {
      localStorage.removeItem(key);
      return;
    }
    localStorage.setItem(key, JSON.stringify(state));
  } catch {
    // Browser storage can be disabled; the UI remains usable without persistence.
  }
}

function isReviewState(value: unknown): value is ReviewState {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as ReviewState;
  return (
    (candidate.decision === "pending" ||
      candidate.decision === "confirmed" ||
      candidate.decision === "pass") &&
    Number.isInteger(candidate.stakeUnits) &&
    candidate.stakeUnits >= 0 &&
    typeof candidate.notes === "string"
  );
}

function hashString(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(36);
}

function exportReviewRows(
  rows: ReviewableRow[],
  businessDate: string,
  riskNotice: string,
): void {
  const headers = [
    "业务日期",
    "推荐ID",
    "比赛ID",
    "场地",
    "场次",
    "开赛时间",
    "组合",
    "模型概率",
    "市场赔率",
    "隐含概率",
    "EV",
    "保守EV",
    "置信度",
    "模拟单位",
    "当前决策",
    "审核状态",
    "备注",
    "数据版本",
    "特征版本",
    "模型版本",
    "策略版本",
    "风险声明",
  ];
  const records = rows.map((row) => [
    businessDate,
    row.id,
    row.raceId,
    row.venue,
    row.raceNo,
    row.startTime,
    row.combination,
    row.modelProbability,
    row.marketOdds,
    row.impliedProbability,
    row.expectedValue,
    row.conservativeExpectedValue,
    row.confidenceLabel,
    row.displayStakeUnits,
    row.displayDecisionLabel,
    row.displayReviewStatus,
    row.displayNotes,
    row.dataVersion,
    row.featureVersion,
    row.modelVersion,
    row.strategyVersion,
    riskNotice,
  ]);
  const csv = [headers, ...records].map(formatCsvRow).join("\r\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `boatrace-review-${safeFilePart(businessDate)}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function formatCsvRow(values: string[]): string {
  return values.map(formatCsvCell).join(",");
}

function formatCsvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function safeFilePart(value: string): string {
  return value.replace(/[^\dA-Za-z-]+/g, "-").replace(/^-+|-+$/g, "") || "draft";
}

export default App;
