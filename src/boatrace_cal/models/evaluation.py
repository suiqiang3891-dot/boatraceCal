"""Probability quality metrics for candidate probability outputs."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import TypedDict

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.strategies.value import StrategyCandidate


_UNIFORM_BASELINE_NAME = "uniform_candidate_set"


class CalibrationBinPayload(TypedDict):
    """JSON-ready calibration bin with Decimal values before string serialization."""

    bin_index: int
    lower_bound: Decimal
    upper_bound: Decimal
    sample_count: int
    average_confidence: Decimal
    empirical_accuracy: Decimal


@dataclass(frozen=True, slots=True)
class ProbabilityEvaluationReport:
    """Aggregate probability metrics for one candidate set."""

    bet_type: BetType
    evaluated_race_count: int
    candidate_count: int
    average_log_loss: Decimal
    average_brier_score: Decimal
    baseline_name: str
    average_baseline_log_loss: Decimal
    average_baseline_brier_score: Decimal
    log_loss_delta_vs_baseline: Decimal
    brier_score_delta_vs_baseline: Decimal
    top1_accuracy: Decimal
    expected_calibration_error: Decimal
    ece_bins: int
    calibration_bins: tuple[CalibrationBinPayload, ...]

    def __post_init__(self) -> None:
        if type(self.bet_type) is not BetType:
            raise TypeError("bet_type must be a BetType")
        for field_name in ("evaluated_race_count", "candidate_count", "ece_bins"):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.ece_bins <= 0:
            raise ValueError("ece_bins must be positive")
        if type(self.baseline_name) is not str or not self.baseline_name:
            raise TypeError("baseline_name must be a non-empty string")
        if type(self.calibration_bins) is not tuple:
            raise TypeError("calibration_bins must be a tuple")
        for field_name in (
            "average_log_loss",
            "average_brier_score",
            "average_baseline_log_loss",
            "average_baseline_brier_score",
            "log_loss_delta_vs_baseline",
            "brier_score_delta_vs_baseline",
            "top1_accuracy",
            "expected_calibration_error",
        ):
            value = getattr(self, field_name)
            if type(value) is not Decimal or not value.is_finite():
                raise TypeError(f"{field_name} must be a finite Decimal")


def evaluate_probability_candidates(
    *,
    candidates: Iterable[StrategyCandidate],
    results: Iterable[RaceResultRecord],
    bet_type: BetType,
    ece_bins: int = 10,
) -> ProbabilityEvaluationReport:
    """Evaluate candidate probabilities against official race results."""

    if type(bet_type) is not BetType:
        raise TypeError("bet_type must be a BetType")
    if type(ece_bins) is not int or ece_bins <= 0:
        raise ValueError("ece_bins must be a positive integer")

    normalized_candidates = _normalize_candidates(candidates, bet_type)
    normalized_results = _normalize_results(results)
    grouped_candidates = _group_candidates(normalized_candidates)

    log_losses: list[Decimal] = []
    brier_scores: list[Decimal] = []
    baseline_log_losses: list[Decimal] = []
    baseline_brier_scores: list[Decimal] = []
    top_outcomes: list[tuple[Decimal, Decimal]] = []
    for result in normalized_results:
        group = grouped_candidates.get(result.race_id)
        if not group:
            continue
        actual = _actual_combination(result, bet_type)
        actual_candidate = next(
            (candidate for candidate in group if candidate.combination == actual),
            None,
        )
        if actual_candidate is None:
            raise ValueError(f"actual combination missing from candidates: {result.race_id}")
        if actual_candidate.probability <= Decimal("0"):
            raise ValueError("actual combination probability must be positive for log loss")

        log_losses.append(-actual_candidate.probability.ln())
        brier_scores.append(_brier_score(group, actual))
        baseline_probability = Decimal("1") / Decimal(len(group))
        baseline_log_losses.append(-baseline_probability.ln())
        baseline_brier_scores.append(
            _brier_score_for_probability(
                candidate_count=len(group),
                actual_probability=baseline_probability,
            )
        )
        top_candidate = max(
            group,
            key=lambda candidate: (candidate.probability, candidate.recommendation_id),
        )
        top_outcomes.append(
            (
                top_candidate.probability,
                Decimal("1") if top_candidate.combination == actual else Decimal("0"),
            )
        )

    evaluated_count = len(log_losses)
    if evaluated_count == 0:
        raise ValueError("probability report requires at least one evaluated race")

    calibration_bins = _calibration_bins(top_outcomes, ece_bins)
    average_log_loss = _average(log_losses)
    average_brier_score = _average(brier_scores)
    average_baseline_log_loss = _average(baseline_log_losses)
    average_baseline_brier_score = _average(baseline_brier_scores)
    return ProbabilityEvaluationReport(
        bet_type=bet_type,
        evaluated_race_count=evaluated_count,
        candidate_count=len(normalized_candidates),
        average_log_loss=average_log_loss,
        average_brier_score=average_brier_score,
        baseline_name=_UNIFORM_BASELINE_NAME,
        average_baseline_log_loss=average_baseline_log_loss,
        average_baseline_brier_score=average_baseline_brier_score,
        log_loss_delta_vs_baseline=average_log_loss - average_baseline_log_loss,
        brier_score_delta_vs_baseline=average_brier_score - average_baseline_brier_score,
        top1_accuracy=_average(tuple(correct for _, correct in top_outcomes)),
        expected_calibration_error=_expected_calibration_error(
            calibration_bins,
            evaluated_count,
        ),
        ece_bins=ece_bins,
        calibration_bins=calibration_bins,
    )


def probability_evaluation_report_to_dict(
    report: ProbabilityEvaluationReport,
) -> dict[str, object]:
    """Convert probability metrics to a stable JSON-ready dictionary."""

    if type(report) is not ProbabilityEvaluationReport:
        raise TypeError("report must be a ProbabilityEvaluationReport")
    return {
        "schema_version": "probability-evaluation-report-v1",
        "bet_type": report.bet_type.value,
        "evaluated_race_count": report.evaluated_race_count,
        "candidate_count": report.candidate_count,
        "average_log_loss": str(report.average_log_loss),
        "average_brier_score": str(report.average_brier_score),
        "baseline_comparison": {
            "baseline_name": report.baseline_name,
            "average_log_loss": str(report.average_baseline_log_loss),
            "average_brier_score": str(report.average_baseline_brier_score),
            "log_loss_delta": str(report.log_loss_delta_vs_baseline),
            "brier_score_delta": str(report.brier_score_delta_vs_baseline),
        },
        "top1_accuracy": str(report.top1_accuracy),
        "expected_calibration_error": str(report.expected_calibration_error),
        "ece_bins": report.ece_bins,
        "calibration_bins": [
            _calibration_bin_to_dict(item) for item in report.calibration_bins
        ],
    }


def _normalize_candidates(
    candidates: Iterable[StrategyCandidate],
    bet_type: BetType,
) -> tuple[StrategyCandidate, ...]:
    normalized = tuple(candidates)
    if any(type(candidate) is not StrategyCandidate for candidate in normalized):
        raise TypeError("candidates must contain only StrategyCandidate instances")
    return tuple(candidate for candidate in normalized if candidate.combination.bet_type is bet_type)


def _normalize_results(results: Iterable[RaceResultRecord]) -> tuple[RaceResultRecord, ...]:
    normalized = tuple(results)
    if any(type(result) is not RaceResultRecord for result in normalized):
        raise TypeError("results must contain only RaceResultRecord instances")
    return normalized


def _group_candidates(
    candidates: tuple[StrategyCandidate, ...],
) -> dict[object, tuple[StrategyCandidate, ...]]:
    groups: dict[object, list[StrategyCandidate]] = {}
    for candidate in candidates:
        groups.setdefault(candidate.race_id, []).append(candidate)
    return {race_id: tuple(group) for race_id, group in groups.items()}


def _actual_combination(
    result: RaceResultRecord,
    bet_type: BetType,
) -> BetCombination:
    return BetCombination.create(bet_type, result.finish_order[: bet_type.lane_count])


def _brier_score(
    candidates: tuple[StrategyCandidate, ...],
    actual: BetCombination,
) -> Decimal:
    return sum(
        (
            (
                candidate.probability
                - (Decimal("1") if candidate.combination == actual else Decimal("0"))
            )
            ** 2
            for candidate in candidates
        ),
        start=Decimal("0"),
    )


def _brier_score_for_probability(
    *,
    candidate_count: int,
    actual_probability: Decimal,
) -> Decimal:
    miss_probability = actual_probability
    return (actual_probability - Decimal("1")) ** 2 + (
        Decimal(candidate_count - 1) * (miss_probability**2)
    )


def _calibration_bins(
    top_outcomes: list[tuple[Decimal, Decimal]],
    ece_bins: int,
) -> tuple[CalibrationBinPayload, ...]:
    bins: list[CalibrationBinPayload] = []
    for bin_index in range(ece_bins):
        bin_items = tuple(
            (confidence, correct)
            for confidence, correct in top_outcomes
            if _ece_bin_index(confidence, ece_bins) == bin_index
        )
        if not bin_items:
            continue
        bin_count = len(bin_items)
        accuracy = _average(tuple(correct for _, correct in bin_items))
        confidence = _average(tuple(confidence for confidence, _ in bin_items))
        bins.append(
            {
                "bin_index": bin_index,
                "lower_bound": Decimal(bin_index) / Decimal(ece_bins),
                "upper_bound": Decimal(bin_index + 1) / Decimal(ece_bins),
                "sample_count": bin_count,
                "average_confidence": confidence,
                "empirical_accuracy": accuracy,
            }
        )
    return tuple(bins)


def _expected_calibration_error(
    calibration_bins: tuple[CalibrationBinPayload, ...],
    evaluated_count: int,
) -> Decimal:
    total_count = Decimal(evaluated_count)
    ece = Decimal("0")
    for bin_payload in calibration_bins:
        bin_count = Decimal(bin_payload["sample_count"])
        accuracy = bin_payload["empirical_accuracy"]
        confidence = bin_payload["average_confidence"]
        ece += (bin_count / total_count) * abs(accuracy - confidence)
    return ece


def _calibration_bin_to_dict(item: CalibrationBinPayload) -> dict[str, str | int]:
    return {
        "bin_index": item["bin_index"],
        "lower_bound": str(item["lower_bound"]),
        "upper_bound": str(item["upper_bound"]),
        "sample_count": item["sample_count"],
        "average_confidence": str(item["average_confidence"]),
        "empirical_accuracy": str(item["empirical_accuracy"]),
    }


def _ece_bin_index(confidence: Decimal, ece_bins: int) -> int:
    index = int(confidence * Decimal(ece_bins))
    return min(index, ece_bins - 1)


def _average(values: Iterable[Decimal]) -> Decimal:
    normalized = tuple(values)
    if not normalized:
        raise ValueError("average requires at least one value")
    return sum(normalized, start=Decimal("0")) / Decimal(len(normalized))
