# UI smart table redesign plan

## Goal

Move the first UI from a backtest dashboard toward the approved "smart table" direction while keeping the implementation traceable to generated report data.

The first usable version should make the main screen a dense operational table for reviewed recommendations, with compact status, risk, and backtest context around it.

## Current Gap

- The current UI is dashboard-first: summary cards, equity curve, slice table, settlement list.
- The target UI is table-first: top status bar, grouped candidate table, row-level analysis detail, and review state controls.
- Current `report.json` does not expose recommendation probability, odds, expected value, confidence, stage, decision, version, or reason-code fields. These fields exist in `examples/sample_backtest/recommendations.csv`.

## Scope

1. Extend settled backtest rows with the selected recommendation snapshot needed by the UI.
2. Serialize the snapshot in `backtest_report_to_dict`.
3. Regenerate/update the bundled sample `examples/sample_backtest/report.json`.
4. Replace the first UI composition with a smart-table workbench:
   - top status bar with business date/status/freshness/counts/budget/risk/export placeholder/confirmation placeholder;
   - compact backtest summary metrics;
   - primary smart table with target columns;
   - selected-row detail panel with model/market comparison, reason codes, versions, and settlement result;
   - visible risk statement.
5. Keep the equity curve available as context, but not as the main visual.

## Out Of Scope For This Iteration

- Real FastAPI endpoints and persistent review records.
- Editable notes, unit adjustment persistence, Excel export generation, or tomorrow-list confirmation.
- Live pre-race odds refresh and diff highlighting.
- Batch review actions beyond static disabled/placeholder controls.
- New dependencies.

## Data Contract

Add a `recommendation` object to each serialized settlement row:

```json
{
  "recommendation_id": "sample-rec-hit",
  "race_id": "20250102-01-01",
  "stake_units": 1,
  "recommendation": {
    "stage": "final",
    "decision": "select",
    "confidence": "high",
    "probability": "0.25",
    "odds": "5.2",
    "expected_value": "0.30",
    "as_of": "2025-01-02T10:00:00+00:00",
    "versions": {
      "data": "sample-data-v1",
      "feature": "sample-feature-v1",
      "model": "sample-model-v1",
      "strategy": "sample-strategy-v1"
    },
    "reason_codes": ["positive_ev", "sample"]
  }
}
```

The browser can derive implied probability from `odds` and conservative EV from probability/odds with a simple display-only haircut. Missing odds/EV must render as "等待赛前数据".

## Test Plan

Python:
- Add a settlement test proving selected recommendation snapshots are retained and pass decisions remain excluded from settled rows.
- Add a serialization/report test proving recommendation probability, odds, expected value, confidence, versions, and reason codes are present in JSON.
- Keep the sample report generation test comparing the fixture to regenerated output.

Frontend:
- Add model tests for smart-table rows:
  - venue/race/time/combination derived from `race_id` and settlement combination;
  - model probability, odds, implied probability, EV, conservative EV, confidence, decision, review status, and notes rendered from the report;
  - missing market fields display "等待赛前数据".
- Add app render tests for the smart-table heading, top status values, table columns, first row details, and risk statement.

Verification:
- `python -m pytest`
- `python -m ruff check .`
- `python -m mypy src`
- `npm run test` in `ui`
- `npm run build` in `ui`
- browser screenshot smoke check for desktop and mobile if time permits
- `codegraph index`

## Implementation Order

1. Write failing Python tests for recommendation snapshot retention and report serialization.
2. Implement backend settlement/serialization changes.
3. Regenerate the sample backtest report fixture.
4. Write failing frontend tests for smart-table model and render.
5. Implement the smart-table model and UI.
6. Run verification and fix regressions.
7. Request spec and code review subagents before committing.

## Risks

- Adding recommendation snapshots to settlement rows changes the report JSON contract. This is additive, but consumers should tolerate the new object.
- The current backtest report still represents historical selected bets, not live pre-race review candidates. Labels must be clear and avoid implying real-time wagering readiness.
- Conservative EV in the first UI may be display-derived until the strategy layer owns it explicitly.
