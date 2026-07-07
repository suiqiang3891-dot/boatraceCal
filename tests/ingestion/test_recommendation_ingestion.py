from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import (
    ConfidenceLevel,
    Decision,
    PlanStage,
    Recommendation,
)
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.ingestion.recommendations import load_recommendations_csv


def _write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "recommendations.csv"
    path.write_text(content, encoding="utf-8", newline="")
    return path


def test_loads_recommendations_csv_into_normalized_records(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "recommendation_id,race_date,venue,race_no,bet_type,combination,"
                "stage,decision,confidence,probability,odds,expected_value,as_of,"
                "stake_units,data_version,feature_version,model_version,strategy_version,"
                "reason_codes",
                "rec-1,2026-06-23,5,1,trifecta_ordered,3-1-2,final,select,high,"
                "0.25,5.2,0.30,2026-06-23T03:45:00+00:00,1,data-v1,feature-v1,"
                "model-v1,strategy-v1,positive_ev|risk_ok",
                "rec-2,2026-06-23,05,1,trifecta_ordered,1-2-3,final,pass,low,"
                "0.02,,,2026-06-23T03:45:00+00:00,0,data-v1,feature-v1,"
                "model-v1,strategy-v1,low_ev",
            )
        ),
    )

    records = load_recommendations_csv(path)

    assert records == (
        Recommendation(
            recommendation_id="rec-1",
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
            combination=BetCombination.create(BetType.TRIFECTA_ORDERED, (3, 1, 2)),
            stage=PlanStage.FINAL,
            decision=Decision.SELECT,
            confidence=ConfidenceLevel.HIGH,
            probability=Decimal("0.25"),
            odds=Decimal("5.2"),
            expected_value=Decimal("0.30"),
            as_of=datetime(2026, 6, 23, 3, 45, tzinfo=timezone.utc),
            stake_units=1,
            versions=ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
            reason_codes=("positive_ev", "risk_ok"),
        ),
        Recommendation(
            recommendation_id="rec-2",
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
            combination=BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3)),
            stage=PlanStage.FINAL,
            decision=Decision.PASS,
            confidence=ConfidenceLevel.LOW,
            probability=Decimal("0.02"),
            odds=None,
            expected_value=None,
            as_of=datetime(2026, 6, 23, 3, 45, tzinfo=timezone.utc),
            stake_units=0,
            versions=ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
            reason_codes=("low_ev",),
        ),
    )


def test_rejects_duplicate_recommendation_ids(tmp_path: Path) -> None:
    header = (
        "recommendation_id,race_date,venue,race_no,bet_type,combination,"
        "stage,decision,confidence,probability,odds,expected_value,as_of,"
        "stake_units,data_version,feature_version,model_version,strategy_version,reason_codes"
    )
    row = (
        "rec-1,2026-06-23,05,1,trifecta_ordered,3-1-2,final,select,high,"
        "0.25,5.2,0.30,2026-06-23T03:45:00+00:00,1,data-v1,feature-v1,"
        "model-v1,strategy-v1,positive_ev"
    )
    path = _write_csv(tmp_path, "\n".join((header, row, row)))

    with pytest.raises(ValueError, match="duplicate recommendation id"):
        load_recommendations_csv(path)


def test_rejects_unknown_recommendation_csv_fields(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "recommendation_id,race_date,venue,race_no,bet_type,combination,"
                "stage,decision,confidence,probability,odds,expected_value,as_of,"
                "stake_units,data_version,feature_version,model_version,strategy_version,"
                "reason_codes,extra",
                "rec-1,2026-06-23,05,1,trifecta_ordered,3-1-2,final,select,high,"
                "0.25,5.2,0.30,2026-06-23T03:45:00+00:00,1,data-v1,feature-v1,"
                "model-v1,strategy-v1,positive_ev,x",
            )
        ),
    )

    with pytest.raises(ValueError, match="recommendation CSV must contain exactly"):
        load_recommendations_csv(path)
