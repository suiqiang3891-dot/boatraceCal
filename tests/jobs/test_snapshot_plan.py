from datetime import date, datetime, timedelta, timezone
import json

import pytest

from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import SnapshotTarget
from boatrace_cal.jobs.snapshot_plan import (
    RaceStart,
    SnapshotDecisionMode,
    build_prerace_snapshot_plan,
    load_race_starts_csv,
    select_due_snapshot_jobs,
    snapshot_plan_to_dict,
)


def test_snapshot_plan_builds_four_timed_jobs_with_decision_guards() -> None:
    race_start = RaceStart(
        race_date=date(2026, 6, 23),
        venue=VenueCode("5"),
        race_no=1,
        starts_at=datetime(2026, 6, 23, 4, 30, tzinfo=timezone.utc),
    )

    plan = build_prerace_snapshot_plan([race_start], source="official", data_type="odds")

    assert [item.snapshot_target for item in plan] == [
        SnapshotTarget.T30,
        SnapshotTarget.T15,
        SnapshotTarget.T10,
        SnapshotTarget.T05,
    ]
    assert [item.scheduled_at for item in plan] == [
        race_start.starts_at - timedelta(minutes=30),
        race_start.starts_at - timedelta(minutes=15),
        race_start.starts_at - timedelta(minutes=10),
        race_start.starts_at - timedelta(minutes=5),
    ]
    assert [item.decision_mode for item in plan] == [
        SnapshotDecisionMode.REFRESH,
        SnapshotDecisionMode.REFRESH,
        SnapshotDecisionMode.FREEZE_FINAL_DECISION,
        SnapshotDecisionMode.CHANGE_ALERT_ONLY,
    ]
    assert [item.job_key.key for item in plan] == [
        "official|05|2026-06-23|1|odds|T30",
        "official|05|2026-06-23|1|odds|T15",
        "official|05|2026-06-23|1|odds|T10",
        "official|05|2026-06-23|1|odds|T05",
    ]


def test_snapshot_plan_payload_is_stable_and_auditable() -> None:
    race_start = RaceStart(
        race_date=date(2026, 6, 23),
        venue=VenueCode("05"),
        race_no=2,
        starts_at=datetime(2026, 6, 23, 5, 0, tzinfo=timezone.utc),
    )

    payload = snapshot_plan_to_dict(
        build_prerace_snapshot_plan([race_start], source="official")
    )

    assert json.dumps(payload, sort_keys=True)
    assert payload["schema_version"] == "snapshot-job-plan-v1"
    assert payload["job_count"] == 4
    assert payload["jobs"][2] == {
        "job_key": "official|05|2026-06-23|2|odds|T10",
        "source": "official",
        "venue": "05",
        "race_date": "2026-06-23",
        "race_no": 2,
        "data_type": "odds",
        "snapshot_target": "T10",
        "scheduled_at": "2026-06-23T04:50:00+00:00",
        "starts_at": "2026-06-23T05:00:00+00:00",
        "minutes_before_start": 10,
        "decision_mode": "freeze_final_decision",
    }
    assert payload["jobs"][3]["decision_mode"] == "change_alert_only"


def test_snapshot_plan_sorts_races_before_targets() -> None:
    later_race = RaceStart(
        race_date=date(2026, 6, 23),
        venue=VenueCode("05"),
        race_no=2,
        starts_at=datetime(2026, 6, 23, 5, 0, tzinfo=timezone.utc),
    )
    earlier_race = RaceStart(
        race_date=date(2026, 6, 23),
        venue=VenueCode("05"),
        race_no=1,
        starts_at=datetime(2026, 6, 23, 4, 30, tzinfo=timezone.utc),
    )

    plan = build_prerace_snapshot_plan([later_race, earlier_race], source="official")

    assert [item.job_key.key for item in plan[:2]] == [
        "official|05|2026-06-23|1|odds|T30",
        "official|05|2026-06-23|1|odds|T15",
    ]
    assert plan[4].job_key.key == "official|05|2026-06-23|2|odds|T30"


def test_select_due_snapshot_jobs_uses_explicit_execution_window() -> None:
    race_start = RaceStart(
        race_date=date(2026, 6, 23),
        venue=VenueCode("05"),
        race_no=1,
        starts_at=datetime(2026, 6, 23, 4, 30, tzinfo=timezone.utc),
    )
    plan_payload = snapshot_plan_to_dict(
        build_prerace_snapshot_plan([race_start], source="official")
    )

    due_payload = select_due_snapshot_jobs(
        plan_payload,
        now=datetime(2026, 6, 23, 4, 14, tzinfo=timezone.utc),
        lookahead=timedelta(minutes=1),
        past_tolerance=timedelta(minutes=0),
    )

    assert due_payload["schema_version"] == "snapshot-job-due-v1"
    assert due_payload["source_schema_version"] == "snapshot-job-plan-v1"
    assert due_payload["window_start"] == "2026-06-23T04:14:00+00:00"
    assert due_payload["window_end"] == "2026-06-23T04:15:00+00:00"
    assert due_payload["job_count"] == 1
    assert due_payload["jobs"][0]["job_key"] == "official|05|2026-06-23|1|odds|T15"


def test_race_start_requires_timezone_aware_start_time() -> None:
    with pytest.raises(ValueError, match="starts_at must be timezone-aware"):
        RaceStart(
            race_date=date(2026, 6, 23),
            venue=VenueCode("05"),
            race_no=1,
            starts_at=datetime(2026, 6, 23, 4, 30),
        )


def test_load_race_starts_csv_rejects_unknown_columns(tmp_path) -> None:
    csv_path = tmp_path / "race-starts.csv"
    csv_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,starts_at,extra",
                "2026-06-23,05,1,2026-06-23T04:30:00+00:00,unexpected",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="race starts CSV columns"):
        load_race_starts_csv(csv_path)
