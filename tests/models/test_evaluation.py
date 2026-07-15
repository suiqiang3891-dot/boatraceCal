from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import ConfidenceLevel
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.models.evaluation import evaluate_probability_candidates
from boatrace_cal.strategies.value import StrategyCandidate


def make_candidate(
    recommendation_id: str,
    race_id: RaceId,
    lanes: tuple[int, ...],
    probability: str,
) -> StrategyCandidate:
    return StrategyCandidate(
        recommendation_id=recommendation_id,
        race_id=race_id,
        combination=BetCombination(BetType.TRIFECTA_ORDERED, lanes),
        probability=Decimal(probability),
        odds=None,
        confidence=ConfidenceLevel.MEDIUM,
        as_of=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
        versions=ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
        reason_codes=("test",),
    )


def make_result(race_id: RaceId, finish_order: tuple[int, int, int]) -> RaceResultRecord:
    return RaceResultRecord(
        race_id=race_id,
        finish_order=finish_order,
        source="official-results",
        source_hash=f"hash-{race_id}",
        observed_at=datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc),
        available_at=datetime(2026, 6, 23, 8, 1, tzinfo=timezone.utc),
        parser_version="results-v1",
    )


def test_evaluate_probability_candidates_computes_log_loss_brier_and_ece() -> None:
    race_1 = RaceId(date(2026, 6, 23), VenueCode("05"), 1)
    race_2 = RaceId(date(2026, 6, 23), VenueCode("05"), 2)

    report = evaluate_probability_candidates(
        candidates=(
            make_candidate("race-1-hit", race_1, (1, 2, 3), "0.8"),
            make_candidate("race-1-miss", race_1, (1, 3, 2), "0.2"),
            make_candidate("race-2-miss", race_2, (1, 2, 3), "0.7"),
            make_candidate("race-2-hit", race_2, (2, 1, 3), "0.3"),
        ),
        results=(
            make_result(race_1, (1, 2, 3)),
            make_result(race_2, (2, 1, 3)),
        ),
        bet_type=BetType.TRIFECTA_ORDERED,
        ece_bins=2,
    )

    assert report.evaluated_race_count == 2
    assert report.candidate_count == 4
    assert report.top1_accuracy == Decimal("0.5")
    assert report.average_log_loss == Decimal("0.713558177820072874194520654")
    assert report.average_brier_score == Decimal("0.53")
    assert report.baseline_name == "uniform_candidate_set"
    assert report.average_baseline_log_loss == Decimal("0.6931471805599453094172321215")
    assert report.average_baseline_brier_score == Decimal("0.50")
    assert report.log_loss_delta_vs_baseline == Decimal("0.0204109972601275647772885325")
    assert report.brier_score_delta_vs_baseline == Decimal("0.03")
    assert report.expected_calibration_error == Decimal("0.25")
    assert report.calibration_bins == (
        {
            "bin_index": 1,
            "lower_bound": Decimal("0.5"),
            "upper_bound": Decimal("1"),
            "sample_count": 2,
            "average_confidence": Decimal("0.75"),
            "empirical_accuracy": Decimal("0.5"),
        },
    )


def test_evaluate_probability_candidates_rejects_missing_actual_combination() -> None:
    race_id = RaceId(date(2026, 6, 23), VenueCode("05"), 1)

    with pytest.raises(ValueError, match="actual combination"):
        evaluate_probability_candidates(
            candidates=(make_candidate("race-1-miss", race_id, (1, 3, 2), "1"),),
            results=(make_result(race_id, (1, 2, 3)),),
            bet_type=BetType.TRIFECTA_ORDERED,
            ece_bins=2,
        )
