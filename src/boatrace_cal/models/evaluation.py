"""Probability quality metrics for candidate probability outputs."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.strategies.value import StrategyCandidate


@dataclass(frozen=True, slots=True)
class ProbabilityEvaluationReport:
    """Aggregate probability metrics for one candidate set."""

    bet_type: BetType
    evaluated_race_count: int
    candidate_count: int
    average_log_loss: Decimal
    average_brier_score: Decimal
    top1_accuracy: Decimal
    expected_calibration_error: Decimal
    ece_bins: int

    def __post_init__(self) -> None:
        if type(self.bet_type) is not BetType:
            raise TypeError("bet_type must be a BetType")
        for field_name in ("evaluated_race_count", "candidate_count", "ece_bins"):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.ece_bins <= 0:
            raise ValueError("ece_bins must be positive")
        for field_name in (
            "average_log_loss",
            "average_brier_score",
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

    return ProbabilityEvaluationReport(
        bet_type=bet_type,
        evaluated_race_count=evaluated_count,
        candidate_count=len(normalized_candidates),
        average_log_loss=_average(log_losses),
        average_brier_score=_average(brier_scores),
        top1_accuracy=_average(tuple(correct for _, correct in top_outcomes)),
        expected_calibration_error=_expected_calibration_error(top_outcomes, ece_bins),
        ece_bins=ece_bins,
    )


def probability_evaluation_report_to_dict(
    report: ProbabilityEvaluationReport,
) -> dict[str, str | int]:
    """Convert probability metrics to a stable JSON-ready dictionary."""

    if type(report) is not ProbabilityEvaluationReport:
        raise TypeError("report must be a ProbabilityEvaluationReport")
    return {
        "bet_type": report.bet_type.value,
        "evaluated_race_count": report.evaluated_race_count,
        "candidate_count": report.candidate_count,
        "average_log_loss": str(report.average_log_loss),
        "average_brier_score": str(report.average_brier_score),
        "top1_accuracy": str(report.top1_accuracy),
        "expected_calibration_error": str(report.expected_calibration_error),
        "ece_bins": report.ece_bins,
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


def _expected_calibration_error(
    top_outcomes: list[tuple[Decimal, Decimal]],
    ece_bins: int,
) -> Decimal:
    total_count = Decimal(len(top_outcomes))
    ece = Decimal("0")
    for bin_index in range(ece_bins):
        bin_items = tuple(
            (confidence, correct)
            for confidence, correct in top_outcomes
            if _ece_bin_index(confidence, ece_bins) == bin_index
        )
        if not bin_items:
            continue
        bin_count = Decimal(len(bin_items))
        accuracy = _average(tuple(correct for _, correct in bin_items))
        confidence = _average(tuple(confidence for confidence, _ in bin_items))
        ece += (bin_count / total_count) * abs(accuracy - confidence)
    return ece


def _ece_bin_index(confidence: Decimal, ece_bins: int) -> int:
    index = int(confidence * Decimal(ece_bins))
    return min(index, ece_bins - 1)


def _average(values: Iterable[Decimal]) -> Decimal:
    normalized = tuple(values)
    if not normalized:
        raise ValueError("average requires at least one value")
    return sum(normalized, start=Decimal("0")) / Decimal(len(normalized))
