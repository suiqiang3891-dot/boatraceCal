from boatrace_cal.errors import ErrorCode


EXPECTED_ERROR_CODES = {
    "SOURCE_UNAVAILABLE",
    "MISSED_WINDOW",
    "FETCH_TIMEOUT",
    "RATE_LIMITED",
    "PARSE_SCHEMA_CHANGED",
    "DQ_MISSING_ENTRY",
    "DQ_STALE_ODDS",
    "DQ_INCOMPLETE_ODDS",
    "DQ_TIME_LEAK_RISK",
    "MODEL_NOT_READY",
    "CALIBRATION_INVALID",
    "STRATEGY_RISK_LIMIT",
    "VERSION_CONFLICT",
}


def test_error_codes_match_the_stable_contract() -> None:
    assert {code.value for code in ErrorCode} == EXPECTED_ERROR_CODES


def test_error_code_values_are_unique() -> None:
    assert len({code.value for code in ErrorCode}) == len(ErrorCode)
