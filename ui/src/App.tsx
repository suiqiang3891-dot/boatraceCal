import { Activity, AlertTriangle, BarChart3, ShieldCheck } from "lucide-react";
import sampleReport from "../../examples/sample_backtest/report.json";
import { EquityChart } from "./EquityChart";
import { buildDashboardModel, type BacktestReport, type Tone } from "./reportMetrics";
import "./styles.css";

const model = buildDashboardModel(sampleReport as BacktestReport);

function App() {
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">paper backtest</p>
          <h1>BOAT RACE 回测工作台</h1>
        </div>
        <div className="status-pill" aria-label="报告状态">
          <ShieldCheck size={18} aria-hidden="true" />
          {model.statusLabel}
        </div>
      </header>

      <section className="risk-banner" aria-label="风险声明">
        <AlertTriangle size={20} aria-hidden="true" />
        <span>{model.riskNotice}</span>
      </section>

      <section className="metrics-grid" aria-label="核心指标">
        {model.summaryCards.map((card) => (
          <article className={`metric-card tone-${card.tone}`} key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </article>
        ))}
      </section>

      <section className="dashboard-grid">
        <section className="panel chart-panel" aria-labelledby="equity-title">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">equity</p>
              <h2 id="equity-title">资金曲线</h2>
            </div>
            <Activity size={20} aria-hidden="true" />
          </div>
          <EquityChart points={model.equityPoints} />
        </section>

        <section className="panel" aria-labelledby="slice-title">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">segments</p>
              <h2 id="slice-title">切片表现</h2>
            </div>
            <BarChart3 size={20} aria-hidden="true" />
          </div>
          <div className="table-wrap">
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

      <section className="panel" aria-labelledby="settlement-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">settlements</p>
            <h2 id="settlement-title">结算明细</h2>
          </div>
        </div>
        <div className="settlement-list">
          {model.settlementRows.map((row) => (
            <article className="settlement-row" key={row.id}>
              <div>
                <strong>{row.raceId}</strong>
                <span>{row.combination}</span>
              </div>
              <div>
                <span>{row.status}</span>
                <span>{row.stake} → {row.returned}</span>
              </div>
              <strong className={toneClass(row.tone)}>{row.netProfit}</strong>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

function toneClass(tone: Tone): string {
  return `text-${tone}`;
}

export default App;
