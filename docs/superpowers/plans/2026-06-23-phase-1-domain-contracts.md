# Phase 1 Engineering and Domain Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dependency-light Python 3.12 foundation with tested race, bet, temporal, version, recommendation, job, error, and configuration contracts.

**Architecture:** Use a `src`-layout Python package and immutable dataclasses/enums. Domain modules contain no crawler, database, model, API, or UI behavior; later phases consume these stable contracts. Runtime code uses only the standard library in Phase 1.

**Tech Stack:** Python 3.12+, `dataclasses`, `enum`, `datetime`, `zoneinfo`, `tomllib`; development tools `pytest`, Ruff, and mypy after explicit dependency approval.

---

## Execution Preconditions

1. Obtain explicit approval before adding/installing `pytest`, Ruff, or mypy.
2. Initialize Git or provide a valid repository before execution. The current directory is not a Git repository, so a dedicated worktree and commit checkpoints cannot yet run.
3. Do not add pandas, DuckDB, scikit-learn, FastAPI, React, scraping libraries, or spreadsheet libraries in this phase.
4. Use Japan Standard Time (`Asia/Tokyo`) for race business dates; store persisted timestamps as timezone-aware UTC.

## File Map

```text
pyproject.toml                              # package metadata and approved dev tooling
.gitignore                                  # generated/local artifacts
configs/default.toml                        # Phase 1 project configuration
src/boatrace_cal/__init__.py                # package version
src/boatrace_cal/domain/races.py            # venue and race identifiers
src/boatrace_cal/domain/bets.py             # five bet types and normalized combinations
src/boatrace_cal/domain/temporal.py         # aware timestamps and availability rule
src/boatrace_cal/domain/versions.py         # data/feature/model/strategy versions
src/boatrace_cal/domain/recommendations.py  # preplan/final recommendation contract
src/boatrace_cal/jobs/contracts.py          # idempotent job key and state transitions
src/boatrace_cal/errors.py                   # stable error codes
src/boatrace_cal/config.py                   # standard-library TOML loader
tests/...                                   # one focused test module per contract
docs/implementation/phase-1-verification.md # executed evidence and known gaps
```

### Task 1: Package and quality-tool skeleton

**Files:** Create `pyproject.toml`, `.gitignore`, `src/boatrace_cal/__init__.py`, `tests/test_package.py`.

- [ ] **Step 1: Add the failing smoke test**

```python
from boatrace_cal import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the test before package creation**

Run: `python -m pytest tests/test_package.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'boatrace_cal'`.

- [ ] **Step 3: Add minimal package configuration**

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "boatrace-cal"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8,<10", "ruff>=0.11,<1", "mypy>=1.15,<2"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["boatrace_cal"]
```

Set `src/boatrace_cal/__init__.py` to `__version__ = "0.1.0"`. Ignore `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `data/`, `artifacts/`, and `.superpowers/`.

- [ ] **Step 4: Install only after approval and verify**

Run: `python -m pip install -e ".[dev]"` then `python -m pytest tests/test_package.py -v`.  
Expected: one passing test.

- [ ] **Step 5: Commit with Lore trailers**

```text
Establish a reproducible foundation before domain work begins

Constraint: Runtime dependencies remain empty in Phase 1
Confidence: high
Scope-risk: narrow
Tested: Package smoke test
Not-tested: Runtime features are intentionally absent
```

### Task 2: Race identifiers

**Files:** Create `src/boatrace_cal/domain/__init__.py`, `src/boatrace_cal/domain/races.py`, `tests/domain/test_races.py`.

- [ ] **Step 1: Test valid normalization and invalid values**

```python
from datetime import date
import pytest
from boatrace_cal.domain.races import RaceId, VenueCode


def test_race_id_is_canonical() -> None:
    assert str(RaceId(date(2026, 6, 23), VenueCode("5"), 1)) == "20260623-05-01"


@pytest.mark.parametrize("value", ["0", "25", "AA"])
def test_venue_code_rejects_invalid_value(value: str) -> None:
    with pytest.raises(ValueError):
        VenueCode(value)
```

- [ ] **Step 2:** Run `python -m pytest tests/domain/test_races.py -v`; expect import failure.
- [ ] **Step 3: Implement immutable identifiers**

```python
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class VenueCode:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.zfill(2)
        if not normalized.isdigit() or not 1 <= int(normalized) <= 24:
            raise ValueError("venue code must be between 01 and 24")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RaceId:
    race_date: date
    venue: VenueCode
    race_no: int

    def __post_init__(self) -> None:
        if not 1 <= self.race_no <= 12:
            raise ValueError("race number must be between 1 and 12")

    def __str__(self) -> str:
        return f"{self.race_date:%Y%m%d}-{self.venue}-{self.race_no:02d}"
```

- [ ] **Step 4:** Run the focused test; expect all cases to pass.
- [ ] **Step 5:** Commit: `Make race identity unambiguous across all data flows` with `Tested: Race and venue unit tests` and `Scope-risk: narrow` trailers.

### Task 3: Bet types and combination normalization

**Files:** Create `src/boatrace_cal/domain/bets.py`, `tests/domain/test_bets.py`.

- [ ] **Step 1: Test ordered and unordered semantics**

```python
import pytest
from boatrace_cal.domain.bets import BetCombination, BetType


def test_ordered_combination_preserves_order() -> None:
    assert BetCombination.create(BetType.TRIFECTA_ORDERED, [3, 1, 2]).key == "3-1-2"


def test_box_combination_sorts_numbers() -> None:
    assert BetCombination.create(BetType.TRIFECTA_BOX, [3, 1, 2]).key == "1-2-3"


def test_combination_rejects_duplicate_lane() -> None:
    with pytest.raises(ValueError):
        BetCombination.create(BetType.EXACTA_ORDERED, [1, 1])
```

- [ ] **Step 2:** Run the focused test; expect import failure.
- [ ] **Step 3: Implement the five-type contract**

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class BetType(StrEnum):
    TRIFECTA_ORDERED = "trifecta_ordered"
    TRIFECTA_BOX = "trifecta_box"
    EXACTA_ORDERED = "exacta_ordered"
    EXACTA_BOX = "exacta_box"
    WIDE_BOX = "wide_box"

    @property
    def lane_count(self) -> int:
        return 3 if self in {self.TRIFECTA_ORDERED, self.TRIFECTA_BOX} else 2

    @property
    def ordered(self) -> bool:
        return self in {self.TRIFECTA_ORDERED, self.EXACTA_ORDERED}


@dataclass(frozen=True, slots=True)
class BetCombination:
    bet_type: BetType
    lanes: tuple[int, ...]

    @classmethod
    def create(cls, bet_type: BetType, lanes: Iterable[int]) -> "BetCombination":
        values = tuple(lanes)
        if len(values) != bet_type.lane_count or len(set(values)) != len(values):
            raise ValueError("combination has invalid lane count or duplicate lanes")
        if any(lane < 1 or lane > 6 for lane in values):
            raise ValueError("lanes must be between 1 and 6")
        return cls(bet_type, values if bet_type.ordered else tuple(sorted(values)))

    @property
    def key(self) -> str:
        return "-".join(str(lane) for lane in self.lanes)
```

- [ ] **Step 4:** Run `python -m pytest tests/domain/test_bets.py -v`; expect PASS.
- [ ] **Step 5:** Commit: `Preserve settlement meaning across ordered and box bets` with `Constraint: Five settlement types share one normalized contract`, `Confidence: high`, `Scope-risk: narrow`, and `Tested: Ordered and box combination unit tests` trailers.

### Task 4: Temporal and version contracts

**Files:** Create `src/boatrace_cal/domain/temporal.py`, `src/boatrace_cal/domain/versions.py`, `tests/domain/test_temporal.py`, `tests/domain/test_versions.py`.

- [ ] **Step 1:** Test rejection of naive timestamps, future availability, and blank version IDs.

```python
from datetime import datetime, timezone
import pytest
from boatrace_cal.domain.temporal import AvailableRecord
from boatrace_cal.domain.versions import ArtifactVersions


def test_record_rejects_data_available_after_prediction() -> None:
    with pytest.raises(ValueError):
        AvailableRecord(datetime(2026, 1, 1, 1, tzinfo=timezone.utc)).assert_usable_at(
            datetime(2026, 1, 1, tzinfo=timezone.utc)
        )


def test_versions_reject_blank_identifier() -> None:
    with pytest.raises(ValueError):
        ArtifactVersions("data-v1", "", "model-v1", "strategy-v1")
```

- [ ] **Step 2:** Run both tests; expect import failures.
- [ ] **Step 3: Implement the exact contracts**

```python
# temporal.py
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True, slots=True)
class AvailableRecord:
    available_at: datetime
    def __post_init__(self) -> None:
        if self.available_at.tzinfo is None:
            raise ValueError("available_at must be timezone-aware")
    def assert_usable_at(self, as_of: datetime) -> None:
        if as_of.tzinfo is None or self.available_at > as_of:
            raise ValueError("record was not available at prediction time")

# versions.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ArtifactVersions:
    data: str
    feature: str
    model: str
    strategy: str
    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.data, self.feature, self.model, self.strategy)):
            raise ValueError("all artifact versions are required")
```
- [ ] **Step 4:** Run both test modules; expect PASS.
- [ ] **Step 5:** Commit: `Make prediction-time causality and artifact provenance explicit` with Lore trailers.

### Task 5: Recommendation and immutable review contract

**Files:** Create `src/boatrace_cal/domain/recommendations.py`, `tests/domain/test_recommendations.py`.

- [ ] **Step 1:** Add tests asserting probability bounds, non-negative units, aware timestamps, and rejection of `PREPLAN + SELECT`.
- [ ] **Step 2:** Run the test; expect import failure.
- [ ] **Step 3: Implement the recommendation contract**

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from .bets import BetCombination
from .races import RaceId
from .versions import ArtifactVersions

class PlanStage(StrEnum):
    PREPLAN = "preplan"
    FINAL = "final"

class Decision(StrEnum):
    SELECT = "select"
    PASS = "pass"

@dataclass(frozen=True, slots=True)
class Recommendation:
    recommendation_id: str
    race_id: RaceId
    combination: BetCombination
    stage: PlanStage
    decision: Decision
    probability: Decimal
    odds: Decimal | None
    expected_value: Decimal | None
    as_of: datetime
    stake_units: int
    versions: ArtifactVersions
    reason_codes: tuple[str, ...]
    def __post_init__(self) -> None:
        if not Decimal("0") <= self.probability <= Decimal("1"):
            raise ValueError("probability must be between 0 and 1")
        if self.stake_units < 0 or self.as_of.tzinfo is None:
            raise ValueError("stake units and as_of are invalid")
        if self.stage is PlanStage.PREPLAN and self.decision is Decision.SELECT:
            raise ValueError("preplan cannot be a final selection")
```
- [ ] **Step 4:** Run focused tests; expect PASS.
- [ ] **Step 5:** Commit: `Prevent provisional analysis from masquerading as a final decision` with Lore trailers.

### Task 6: Job and error contracts

**Files:** Create `src/boatrace_cal/jobs/__init__.py`, `src/boatrace_cal/jobs/contracts.py`, `src/boatrace_cal/errors.py`, `tests/jobs/test_contracts.py`, `tests/test_errors.py`.

- [ ] **Step 1:** Test deterministic job keys and allowed transitions `PENDING→RUNNING→SUCCEEDED`, `RUNNING→RETRY_WAIT`, `RETRY_WAIT→RUNNING`; reject `SUCCEEDED→RUNNING`.
- [ ] **Step 2:** Run tests; expect import failures.
- [ ] **Step 3: Implement explicit job and error enums**

```python
# jobs/contracts.py
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from boatrace_cal.domain.races import VenueCode

class SnapshotTarget(StrEnum):
    HISTORICAL="historical"; T30="T30"; T15="T15"; T10="T10"; T05="T05"
class JobStatus(StrEnum):
    PENDING="pending"; RUNNING="running"; RETRY_WAIT="retry_wait"; SUCCEEDED="succeeded"; FAILED="failed"; SKIPPED="skipped"
_ALLOWED = {JobStatus.PENDING:{JobStatus.RUNNING}, JobStatus.RUNNING:{JobStatus.SUCCEEDED,JobStatus.RETRY_WAIT,JobStatus.FAILED,JobStatus.SKIPPED}, JobStatus.RETRY_WAIT:{JobStatus.RUNNING}}
def transition(current: JobStatus, target: JobStatus) -> JobStatus:
    if target not in _ALLOWED.get(current, set()):
        raise ValueError(f"invalid job transition: {current} -> {target}")
    return target
@dataclass(frozen=True, slots=True)
class JobKey:
    source: str; venue: VenueCode; race_date: date; race_no: int | None; data_type: str; snapshot_target: SnapshotTarget

# errors.py
from enum import StrEnum
class ErrorCode(StrEnum):
    SOURCE_UNAVAILABLE="SOURCE_UNAVAILABLE"; MISSED_WINDOW="MISSED_WINDOW"; FETCH_TIMEOUT="FETCH_TIMEOUT"; RATE_LIMITED="RATE_LIMITED"; PARSE_SCHEMA_CHANGED="PARSE_SCHEMA_CHANGED"; DQ_MISSING_ENTRY="DQ_MISSING_ENTRY"; DQ_STALE_ODDS="DQ_STALE_ODDS"; DQ_INCOMPLETE_ODDS="DQ_INCOMPLETE_ODDS"; DQ_TIME_LEAK_RISK="DQ_TIME_LEAK_RISK"; MODEL_NOT_READY="MODEL_NOT_READY"; CALIBRATION_INVALID="CALIBRATION_INVALID"; STRATEGY_RISK_LIMIT="STRATEGY_RISK_LIMIT"; VERSION_CONFLICT="VERSION_CONFLICT"
```
- [ ] **Step 4:** Run focused tests; expect PASS.
- [ ] **Step 5:** Commit: `Make retries auditable without permitting invalid job resurrection` with Lore trailers.

### Task 7: Standard-library configuration

**Files:** Create `configs/default.toml`, `src/boatrace_cal/config.py`, `tests/test_config.py`.

- [ ] **Step 1:** Test default timezone `Asia/Tokyo`, pilot venue normalization, four snapshot targets, and rejection of missing config files.
- [ ] **Step 2:** Run the test; expect import failure.
- [ ] **Step 3:** Add `default.toml` with `[project] timezone="Asia/Tokyo"`, `[pilot] venue="01"`, `[snapshots] targets=["T30","T15","T10","T05"]`, and `[retention] anomaly_response_days=30`. Implement `load_config(path)` using `tomllib`, frozen nested dataclasses, `ZoneInfo`, `VenueCode`, and `SnapshotTarget`; reject a missing path and retention below one day.
- [ ] **Step 4:** Run focused tests; expect PASS.
- [ ] **Step 5:** Commit: `Keep pilot behavior configurable without introducing runtime dependencies` with Lore trailers.

### Task 8: Phase verification and documentation

**Files:** Create `docs/implementation/phase-1-verification.md`; modify `docs/README.md` to link it after execution.

- [ ] **Step 1:** Run `python -m pytest` and expect all tests PASS.
- [ ] **Step 2:** Run `python -m ruff check .` and expect `All checks passed!`.
- [ ] **Step 3:** Run `python -m mypy src` and expect `Success: no issues found`.
- [ ] **Step 4:** Record exact commands, tool versions, test counts, and any unavailable check in the verification document. Do not claim an unavailable tool passed.
- [ ] **Step 5:** Re-read every created contract and verify no crawler, model, database, API, UI, or Excel behavior leaked into Phase 1.
- [ ] **Step 6:** Commit: `Close the foundation phase with reproducible evidence` with `Tested:` and `Not-tested:` Lore trailers listing the exact verification scope.

## Completion Gate

Phase 1 is complete only when all focused tests, full pytest, Ruff, and mypy pass; created files have been re-read; the verification document contains observed evidence; no known errors remain; and Git history contains the Lore commits. If Git or approved development dependencies remain unavailable, the phase is blocked rather than complete.
