import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CloudDownload,
  CloudUpload,
  Download,
  FileCheck2,
  Minus,
  Plus,
  RotateCcw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
} from "lucide-react";
import { useMemo, useState, type ChangeEvent } from "react";
import sampleReport from "../../examples/sample_backtest/report.json";
import { EquityChart } from "./EquityChart";
import {
  buildDashboardModel,
  type BacktestReport,
  type SmartTableRow,
  type Tone,
} from "./reportMetrics";
import { createSingleSheetXlsx, type WorkbookRow } from "./xlsxExport";
import "./styles.css";

type FilterKey = "all" | "select" | "wait" | "pass" | "confirmed";
type SortKey = "race-asc" | "probability-desc" | "expected-value-desc";

const filters: Array<{ key: FilterKey; label: string }> = [
  { key: "all", label: "全部" },
  { key: "select", label: "候选" },
  { key: "wait", label: "WAIT" },
  { key: "pass", label: "PASS" },
  { key: "confirmed", label: "已确认" },
];

const sortOptions: Array<{ key: SortKey; label: string }> = [
  { key: "race-asc", label: "场次顺序" },
  { key: "probability-desc", label: "模型概率优先" },
  { key: "expected-value-desc", label: "EV 优先" },
];

const ALL_OPTION = "all";

const REVIEW_STORAGE_PREFIX = "boatraceCal.reviewState";
const REVIEW_EXPORT_USER = "browser-analyst";

type ReviewDecision = "pending" | "confirmed" | "pass";

type ReviewState = {
  decision: ReviewDecision;
  stakeUnits: number;
  notes: string;
};

type ReviewStateMap = Record<string, ReviewState>;

type ReviewJsonRecord = {
  recommendation_id: string;
  race_id: string;
  decision: ReviewDecision;
  stake_units: number;
  notes: string;
  reviewed_at: string;
  reviewed_by: string;
};

type ReviewJsonPayload = {
  schema_version: "recommendation-review-import-v1";
  reviews: ReviewJsonRecord[];
};

type ReviewableRow = SmartTableRow & {
  reviewDecision: ReviewDecision;
  displayStakeUnits: string;
  displayReviewStatus: string;
  reviewStatusTone: Tone;
  displayNotes: string;
  displayDecisionLabel: string;
  decisionTone: Tone;
};

function App({
  report = sampleReport as BacktestReport,
  apiBaseUrl = defaultApiBaseUrl(),
}: {
  report?: BacktestReport;
  apiBaseUrl?: string;
}) {
  const [activeReport, setActiveReport] = useState(report);
  const [reportLoadError, setReportLoadError] = useState("");
  const [apiSyncStatus, setApiSyncStatus] = useState("");
  const [apiSyncError, setApiSyncError] = useState("");
  const [isApiSyncing, setIsApiSyncing] = useState(false);
  const [isApiLoading, setIsApiLoading] = useState(false);
  const model = useMemo(() => buildDashboardModel(activeReport), [activeReport]);
  const reviewStorageKey = useMemo(
    () => buildReviewStorageKey(model.smartTableRows, model.statusBar.businessDate),
    [model.smartTableRows, model.statusBar.businessDate],
  );
  const [reviewState, setReviewState] = useState<ReviewStateMap>(() =>
    loadReviewState(reviewStorageKey, model.smartTableRows),
  );
  const [filter, setFilter] = useState<FilterKey>("all");
  const [businessDateFilter, setBusinessDateFilter] = useState(ALL_OPTION);
  const [venueFilter, setVenueFilter] = useState(ALL_OPTION);
  const [sortKey, setSortKey] = useState<SortKey>("race-asc");
  const reviewRows = useMemo(
    () => model.smartTableRows.map((row) => applyReviewState(row, reviewState[row.id])),
    [model.smartTableRows, reviewState],
  );
  const businessDateOptions = useMemo(
    () => uniqueSorted(reviewRows.map((row) => businessDateFromRaceId(row.raceId))),
    [reviewRows],
  );
  const venueOptions = useMemo(
    () => uniqueSorted(reviewRows.map((row) => row.venue)),
    [reviewRows],
  );
  const filteredRows = useMemo(
    () =>
      reviewRows
        .filter((row) => rowMatchesFilter(row, filter))
        .filter((row) => rowMatchesBusinessDate(row, businessDateFilter))
        .filter((row) => rowMatchesVenue(row, venueFilter))
        .sort(compareRows(sortKey)),
    [businessDateFilter, filter, reviewRows, sortKey, venueFilter],
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
  const confirmedRows = useMemo(
    () =>
      reviewRows.filter(
        (row) => row.reviewDecision === "confirmed" && Number(row.displayStakeUnits) > 0,
      ),
    [reviewRows],
  );

  const handleReportImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    try {
      const importedReport = JSON.parse(await readFileText(file)) as BacktestReport;
      const nextModel = buildDashboardModel(importedReport);
      const nextStorageKey = buildReviewStorageKey(
        nextModel.smartTableRows,
        nextModel.statusBar.businessDate,
      );
      setActiveReport(importedReport);
      setFilter("all");
      setBusinessDateFilter(ALL_OPTION);
      setVenueFilter(ALL_OPTION);
      setSortKey("race-asc");
      setSelectedRowId(nextModel.smartTableRows[0]?.id ?? "");
      setReviewState(loadReviewState(nextStorageKey, nextModel.smartTableRows));
      setReportLoadError("");
    } catch {
      setReportLoadError("报告 JSON 解析失败，已保留当前报告。");
    } finally {
      input.value = "";
    }
  };

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

  const handleExportReviewJson = () => {
    exportReviewJson(reviewRows, model.statusBar.businessDate);
  };

  const handleLoadReviews = async () => {
    const normalizedApiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
    if (!normalizedApiBaseUrl) {
      return;
    }
    setIsApiLoading(true);
    setApiSyncStatus("");
    setApiSyncError("");
    try {
      const response = await fetch(`${normalizedApiBaseUrl}/reviews`, {
        method: "GET",
      });
      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }
      const payload = await response.json();
      const loadedState = reviewStateFromJsonPayload(payload, model.smartTableRows);
      setReviewState((current) => {
        const next = { ...current, ...loadedState };
        saveReviewState(reviewStorageKey, next);
        return next;
      });
      setApiSyncStatus(`API loaded ${Object.keys(loadedState).length} reviews`);
    } catch {
      setApiSyncError("API load failed");
    } finally {
      setIsApiLoading(false);
    }
  };

  const handleSyncReviews = async () => {
    const normalizedApiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
    if (!normalizedApiBaseUrl) {
      return;
    }
    setIsApiSyncing(true);
    setApiSyncStatus("");
    setApiSyncError("");
    try {
      const response = await fetch(`${normalizedApiBaseUrl}/reviews/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildReviewJsonPayload(reviewRows)),
      });
      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }
      const payload = (await response.json()) as { stored_count?: unknown };
      const storedCount =
        typeof payload.stored_count === "number" ? payload.stored_count : reviewRows.length;
      setApiSyncStatus(`API saved ${storedCount} reviews`);
    } catch {
      setApiSyncError("API sync failed");
    } finally {
      setIsApiSyncing(false);
    }
  };

  const handleConfirmTomorrowList = () => {
    exportConfirmedRows(confirmedRows, model.statusBar.businessDate, model.riskNotice);
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
          <StatusItem label="报告版本" value={model.reportSchemaVersion} />
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
          <label className="icon-button file-import-button" title="导入回测报告 JSON">
            <Upload size={17} aria-hidden="true" />
            <input
              className="file-input"
              type="file"
              accept="application/json,.json"
              aria-label="导入回测报告 JSON"
              onChange={handleReportImport}
            />
          </label>
          <button
            className="icon-button"
            type="button"
            aria-label="导出 Excel"
            title="导出 XLSX"
            disabled={reviewRows.length === 0}
            onClick={handleExport}
          >
            <Download size={17} aria-hidden="true" />
          </button>
          <button
            className="icon-button"
            type="button"
            aria-label="导出审核 JSON"
            title="导出后端审核 JSON"
            disabled={reviewRows.length === 0}
            onClick={handleExportReviewJson}
          >
            <Save size={17} aria-hidden="true" />
          </button>
          {normalizeApiBaseUrl(apiBaseUrl) ? (
            <>
              <button
                className="icon-button"
                type="button"
                aria-label="从本地 API 加载审核"
                title="从本地 API 加载审核"
                disabled={reviewRows.length === 0 || isApiLoading}
                onClick={handleLoadReviews}
              >
                <CloudDownload size={17} aria-hidden="true" />
              </button>
              <button
                className="icon-button"
                type="button"
                aria-label="同步审核到本地 API"
                title="同步审核到本地 API"
                disabled={reviewRows.length === 0 || isApiSyncing}
                onClick={handleSyncReviews}
              >
                <CloudUpload size={17} aria-hidden="true" />
              </button>
            </>
          ) : null}
          <button
            className="icon-button"
            type="button"
            aria-label="确认明日清单"
            title="导出已确认候选清单"
            disabled={confirmedRows.length === 0}
            onClick={handleConfirmTomorrowList}
          >
            <FileCheck2 size={17} aria-hidden="true" />
          </button>
        </div>
      </header>

      <section className="risk-strip" aria-label="风险声明">
        <ShieldCheck size={16} aria-hidden="true" />
        <span>{model.riskNotice}</span>
      </section>

      {reportLoadError ? (
        <section className="error-strip" role="alert">
          {reportLoadError}
        </section>
      ) : null}

      {apiSyncStatus ? (
        <section className="success-strip" role="status">
          {apiSyncStatus}
        </section>
      ) : null}

      {apiSyncError ? (
        <section className="error-strip" role="alert">
          {apiSyncError}
        </section>
      ) : null}

      <section className="summary-strip" aria-label="核心指标">
        {model.summaryCards.map((card) => (
          <article className={`summary-chip tone-${card.tone}`} key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </article>
        ))}
      </section>

      {model.confidenceIntervals.length > 0 ? (
        <section className="confidence-strip" aria-label="置信区间">
          {model.confidenceIntervals.map((item) => (
            <article className={`confidence-chip tone-${item.tone}`} key={item.label}>
              <span>{item.label}</span>
              <strong>{item.interval}</strong>
              <small>点估计 {item.pointEstimate}</small>
            </article>
          ))}
        </section>
      ) : null}

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
        <div className="table-controls" aria-label="表格筛选与排序">
          <label className="select-control">
            <span>日期</span>
            <select
              aria-label="日期筛选"
              value={businessDateFilter}
              onChange={(event) => setBusinessDateFilter(event.target.value)}
            >
              <option value={ALL_OPTION}>全部日期</option>
              {businessDateOptions.map((businessDate) => (
                <option value={businessDate} key={businessDate}>
                  {businessDate}
                </option>
              ))}
            </select>
          </label>
          <label className="select-control">
            <span>场地</span>
            <select
              aria-label="场地筛选"
              value={venueFilter}
              onChange={(event) => setVenueFilter(event.target.value)}
            >
              <option value={ALL_OPTION}>全部场地</option>
              {venueOptions.map((venue) => (
                <option value={venue} key={venue}>
                  {venue}
                </option>
              ))}
            </select>
          </label>
          <label className="select-control">
            <span>排序</span>
            <select
              aria-label="排序方式"
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value as SortKey)}
            >
              {sortOptions.map((option) => (
                <option value={option.key} key={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
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

function rowMatchesBusinessDate(row: ReviewableRow, businessDateFilter: string): boolean {
  return (
    businessDateFilter === ALL_OPTION ||
    businessDateFromRaceId(row.raceId) === businessDateFilter
  );
}

function rowMatchesVenue(row: ReviewableRow, venueFilter: string): boolean {
  return venueFilter === ALL_OPTION || row.venue === venueFilter;
}

function compareRows(sortKey: SortKey): (left: ReviewableRow, right: ReviewableRow) => number {
  return (left, right) => {
    if (sortKey === "probability-desc") {
      return (
        compareNumberDesc(
          displayPercentToNumber(left.modelProbability),
          displayPercentToNumber(right.modelProbability),
        ) ||
        left.raceId.localeCompare(right.raceId)
      );
    }
    if (sortKey === "expected-value-desc") {
      return (
        compareNumberDesc(
          displayPercentToNumber(left.expectedValue),
          displayPercentToNumber(right.expectedValue),
        ) ||
        left.raceId.localeCompare(right.raceId)
      );
    }
    return (
      left.raceId.localeCompare(right.raceId) ||
      left.combination.localeCompare(right.combination)
    );
  };
}

function compareNumberDesc(left: number | null, right: number | null): number {
  const normalizedLeft = left ?? Number.NEGATIVE_INFINITY;
  const normalizedRight = right ?? Number.NEGATIVE_INFINITY;
  return normalizedRight - normalizedLeft;
}

function displayPercentToNumber(value: string): number | null {
  if (!value.endsWith("%")) {
    return null;
  }
  const parsed = Number(value.replace("%", ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values)).sort((left, right) => left.localeCompare(right));
}

function businessDateFromRaceId(raceId: string): string {
  const compactDate = raceId.split("-")[0] ?? "";
  return compactDate.replace(/^(\d{4})(\d{2})(\d{2})$/, "$1-$2-$3");
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

function reviewStateFromJsonPayload(payload: unknown, rows: SmartTableRow[]): ReviewStateMap {
  if (!payload || typeof payload !== "object") {
    return {};
  }
  const reviews = (payload as { reviews?: unknown }).reviews;
  if (!Array.isArray(reviews)) {
    return {};
  }
  const rowIds = new Set(rows.map((row) => row.id));
  return reviews.reduce<ReviewStateMap>((state, review) => {
    if (!review || typeof review !== "object") {
      return state;
    }
    const candidate = review as Record<string, unknown>;
    const id = candidate.recommendation_id;
    const decision = candidate.decision;
    const stakeUnits = candidate.stake_units;
    const notes = candidate.notes;
    if (
      typeof id !== "string" ||
      !rowIds.has(id) ||
      (decision !== "pending" && decision !== "confirmed" && decision !== "pass") ||
      typeof stakeUnits !== "number" ||
      !Number.isInteger(stakeUnits) ||
      stakeUnits < 0 ||
      typeof notes !== "string"
    ) {
      return state;
    }
    state[id] = {
      decision,
      stakeUnits,
      notes,
    };
    return state;
  }, {});
}

function hashString(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(36);
}

function defaultApiBaseUrl(): string {
  return import.meta.env.VITE_BOATRACE_API_BASE_URL?.trim() ?? "";
}

function normalizeApiBaseUrl(apiBaseUrl: string): string {
  return apiBaseUrl.trim().replace(/\/+$/, "");
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
  const workbookRows: WorkbookRow[] = [headers, ...records];
  triggerXlsxDownload(
    createSingleSheetXlsx("review_table", workbookRows),
    `boatrace-review-${safeFilePart(businessDate)}.xlsx`,
  );
}

function exportReviewJson(rows: ReviewableRow[], businessDate: string): void {
  const payload = `${JSON.stringify(buildReviewJsonPayload(rows), null, 2)}\n`;
  triggerJsonDownload(payload, `boatrace-reviews-${safeFilePart(businessDate)}.json`);
}

function buildReviewJsonPayload(rows: ReviewableRow[]): ReviewJsonPayload {
  const reviewedAt = new Date().toISOString();
  return {
    schema_version: "recommendation-review-import-v1",
    reviews: rows.map((row) => ({
      recommendation_id: row.id,
      race_id: row.raceId,
      decision: row.reviewDecision,
      stake_units: row.reviewDecision === "pass" ? 0 : Number(row.displayStakeUnits) || 0,
      notes: row.displayNotes,
      reviewed_at: reviewedAt,
      reviewed_by: REVIEW_EXPORT_USER,
    })),
  };
}

function exportConfirmedRows(
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
    "组合",
    "模拟单位",
    "审核状态",
    "备注",
    "模型概率",
    "市场赔率",
    "EV",
    "风险声明",
  ];
  const records = rows.map((row) => [
    businessDate,
    row.id,
    row.raceId,
    row.venue,
    row.raceNo,
    row.combination,
    row.displayStakeUnits,
    row.displayReviewStatus,
    row.displayNotes,
    row.modelProbability,
    row.marketOdds,
    row.expectedValue,
    riskNotice,
  ]);
  const workbookRows: WorkbookRow[] = [headers, ...records];
  triggerXlsxDownload(
    createSingleSheetXlsx("confirmed_reviews", workbookRows),
    `boatrace-confirmed-${safeFilePart(businessDate)}.xlsx`,
  );
}

function triggerXlsxDownload(workbook: Uint8Array, filename: string): void {
  const workbookBuffer = new ArrayBuffer(workbook.byteLength);
  new Uint8Array(workbookBuffer).set(workbook);
  const blob = new Blob([workbookBuffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  triggerBlobDownload(blob, filename);
}

function triggerJsonDownload(json: string, filename: string): void {
  const blob = new Blob([json], { type: "application/json;charset=utf-8" });
  triggerBlobDownload(blob, filename);
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function safeFilePart(value: string): string {
  return value.replace(/[^\dA-Za-z-]+/g, "-").replace(/^-+|-+$/g, "") || "draft";
}

function readFileText(file: File): Promise<string> {
  if (typeof file.text === "function") {
    return file.text();
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(reader.error ?? new Error("failed to read report file"));
    reader.readAsText(file);
  });
}

export default App;
