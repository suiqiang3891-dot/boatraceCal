# Sample Backtest Dataset

This directory contains a tiny deterministic dataset for CLI, API, and UI smoke tests.
It is synthetic sample data, not betting advice and not evidence of future performance.

Generate the sample report:

```powershell
boatrace-cal backtest-report `
  --recommendations examples\sample_backtest\recommendations.csv `
  --results examples\sample_backtest\results.csv `
  --payouts examples\sample_backtest\payouts.csv `
  --expected-date 2025-01-02 `
  --venue 01 `
  --race-nos 1-2 `
  --bet-type trifecta_ordered `
  --output artifacts\sample-backtest-report.json
```

From a source checkout without an installed console script, prefix the same arguments with:

```powershell
$env:PYTHONPATH="src"
python -m boatrace_cal backtest-report `
```
