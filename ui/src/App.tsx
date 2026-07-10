import {
  AlertTriangle,
  Download,
  FileCheck2,
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

type FilterKey = "all" | "select" | "wait" | "pass" | "reject";

const filters: Array<{ key: FilterKey; label: string }> = [
  { key: "all", label: "全部" },
  { key: "select", label: "候选" },
  { key: "wait", label: "WAIT" },
  { key: "pass", label: "PASS" },
  { key: "reject", label: "拒绝" },
];

function App({ report = sampleReport as BacktestReport }: { report?: BacktestReport }) {
  const model = useMemo(() => buildDashboardModel(report), [report]);
  const [filter, setFilter] = useState<FilterKey>("all");
  const filteredRows = useMemo(
    () => model.smartTableRows.filter((row) => rowMatchesFilter(row, filter)),
    [filter, model.smartTableRows],
  );
  const [selectedRowId, setSelectedRowId] = useState(model.smartTableRows[0]?.id ?? "");
  const selectedRow = useMemo(
    () =>
      filteredRows.find((row) => row.id === selectedRowId) ??
      filteredRows[0] ??
      model.smartTableRows[0],
    [filteredRows, model.smartTableRows, selectedRowId],
  );

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
          <button className="icon-button" type="button" aria-label="导出 Excel" disabled>
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
          {selectedRow ? <DetailPanel row={selectedRow} /> : <EmptyDetailPanel />}
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

function rowMatchesFilter(row: SmartTableRow, filter: FilterKey): boolean {
  if (filter === "all") {
    return true;
  }
  if (filter === "select") {
    return row.decisionLabel === "候选";
  }
  if (filter === "wait") {
    return row.startTime === "等待赛前数据" || row.marketOdds === "等待赛前数据";
  }
  if (filter === "pass") {
    return row.decisionLabel === "PASS";
  }
  return row.decisionLabel === "拒绝";
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
  rows: SmartTableRow[];
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
              <td className="number-cell">{row.stakeUnits}</td>
              <td>
                <span className="status-tag tag-positive">{row.decisionLabel}</span>
              </td>
              <td>
                <span className="status-tag tag-warning">{row.reviewStatus}</span>
              </td>
              <td className="notes-cell">{row.notes}</td>
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

function DetailPanel({ row }: { row: SmartTableRow }) {
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
      <div className="detail-actions" aria-label="审核操作">
        <button type="button" disabled>
          模拟单位 {row.stakeUnits}
        </button>
        <button type="button" disabled>
          PASS
        </button>
        <button type="button" disabled>
          备注
        </button>
      </div>
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

export default App;
