"""Portfolio-style risk budget gates for fixed-unit recommendations."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from boatrace_cal.domain.recommendations import Decision, Recommendation


@dataclass(frozen=True, slots=True)
class RiskBudgetConfig:
    """Selection caps applied after per-candidate value gates."""

    max_selects_per_race: int | None = None
    max_daily_stake_units: int | None = None

    def __post_init__(self) -> None:
        _validate_optional_limit(self.max_selects_per_race, "max_selects_per_race")
        _validate_optional_limit(self.max_daily_stake_units, "max_daily_stake_units")


def apply_risk_budget(
    recommendations: Iterable[Recommendation],
    config: RiskBudgetConfig | None = None,
) -> tuple[Recommendation, ...]:
    """Demote lower-ranked selections that exceed race or daily fixed-unit caps."""

    normalized = _normalize_recommendations(recommendations)
    budget = RiskBudgetConfig() if config is None else config
    if type(budget) is not RiskBudgetConfig:
        raise TypeError("config must be a RiskBudgetConfig")

    kept_after_race = _selected_ids_within_race_caps(normalized, budget)
    demoted_for_race = {
        record.recommendation_id
        for record in normalized
        if _is_select(record) and record.recommendation_id not in kept_after_race
    }
    race_budgeted = tuple(
        _demote(record, "race_risk_limit")
        if record.recommendation_id in demoted_for_race
        else record
        for record in normalized
    )

    kept_after_daily = _selected_ids_within_daily_cap(race_budgeted, budget)
    return tuple(
        _demote(record, "daily_risk_limit")
        if _is_select(record) and record.recommendation_id not in kept_after_daily
        else record
        for record in race_budgeted
    )


def _selected_ids_within_race_caps(
    recommendations: tuple[Recommendation, ...],
    config: RiskBudgetConfig,
) -> frozenset[str]:
    if config.max_selects_per_race is None:
        return frozenset(
            record.recommendation_id for record in recommendations if _is_select(record)
        )

    selected_ids: set[str] = set()
    race_groups: dict[object, list[Recommendation]] = {}
    for record in recommendations:
        if _is_select(record):
            race_groups.setdefault(record.race_id, []).append(record)

    for group in race_groups.values():
        selected_ids.update(
            record.recommendation_id
            for record in sorted(group, key=_selection_rank)[: config.max_selects_per_race]
        )
    return frozenset(selected_ids)


def _selected_ids_within_daily_cap(
    recommendations: tuple[Recommendation, ...],
    config: RiskBudgetConfig,
) -> frozenset[str]:
    selects = tuple(record for record in recommendations if _is_select(record))
    if config.max_daily_stake_units is None:
        return frozenset(record.recommendation_id for record in selects)

    selected_ids: set[str] = set()
    date_groups: dict[object, list[Recommendation]] = {}
    for record in selects:
        date_groups.setdefault(record.race_id.race_date, []).append(record)

    for group in date_groups.values():
        selected_ids.update(
            record.recommendation_id
            for record in sorted(group, key=_selection_rank)[: config.max_daily_stake_units]
        )
    return frozenset(selected_ids)


def _demote(recommendation: Recommendation, reason_code: str) -> Recommendation:
    return Recommendation(
        recommendation_id=recommendation.recommendation_id,
        race_id=recommendation.race_id,
        combination=recommendation.combination,
        stage=recommendation.stage,
        decision=Decision.PASS,
        confidence=recommendation.confidence,
        probability=recommendation.probability,
        odds=recommendation.odds,
        expected_value=recommendation.expected_value,
        as_of=recommendation.as_of,
        stake_units=0,
        versions=recommendation.versions,
        reason_codes=_replace_risk_reason(recommendation.reason_codes, reason_code),
    )


def _replace_risk_reason(
    reason_codes: tuple[str, ...],
    replacement: str,
) -> tuple[str, ...]:
    without_risk_ok = tuple(reason for reason in reason_codes if reason != "risk_ok")
    if replacement in without_risk_ok:
        return without_risk_ok
    return without_risk_ok + (replacement,)


def _selection_rank(record: Recommendation) -> tuple[Decimal, Decimal, str]:
    ev = record.expected_value if record.expected_value is not None else Decimal("-Infinity")
    return (-ev, -record.probability, record.recommendation_id)


def _is_select(record: Recommendation) -> bool:
    return record.decision is Decision.SELECT


def _normalize_recommendations(
    recommendations: Iterable[Recommendation],
) -> tuple[Recommendation, ...]:
    normalized = tuple(recommendations)
    if any(type(record) is not Recommendation for record in normalized):
        raise TypeError("recommendations must contain only Recommendation instances")
    return normalized


def _validate_optional_limit(value: int | None, field_name: str) -> None:
    if value is None:
        return
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
