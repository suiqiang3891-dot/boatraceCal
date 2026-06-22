import pytest

from boatrace_cal.domain.bets import BetCombination, BetType


@pytest.mark.parametrize(
    ("bet_type", "lane_count", "ordered"),
    [
        (BetType.TRIFECTA_ORDERED, 3, True),
        (BetType.TRIFECTA_BOX, 3, False),
        (BetType.EXACTA_ORDERED, 2, True),
        (BetType.EXACTA_BOX, 2, False),
        (BetType.WIDE_BOX, 2, False),
    ],
)
def test_bet_type_describes_settlement_shape(
    bet_type: BetType, lane_count: int, ordered: bool
) -> None:
    assert bet_type.lane_count == lane_count
    assert bet_type.ordered is ordered


def test_ordered_trifecta_preserves_lane_order() -> None:
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, [3, 1, 2])

    assert combination.lanes == (3, 1, 2)
    assert combination.key == "3-1-2"


def test_box_trifecta_normalizes_lane_order() -> None:
    combination = BetCombination.create(BetType.TRIFECTA_BOX, [3, 1, 2])

    assert combination.lanes == (1, 2, 3)
    assert combination.key == "1-2-3"


def test_direct_constructor_normalizes_box_lane_order() -> None:
    combination = BetCombination(BetType.TRIFECTA_BOX, (3, 1, 2))

    assert combination.lanes == (1, 2, 3)


@pytest.mark.parametrize("lanes", [(1, 1), (0, 1), (1, 7)])
def test_direct_constructor_rejects_invalid_lanes(lanes: tuple[int, int]) -> None:
    with pytest.raises(ValueError):
        BetCombination(BetType.EXACTA_BOX, lanes)


def test_direct_constructor_rejects_wrong_lane_count() -> None:
    with pytest.raises(ValueError):
        BetCombination(BetType.TRIFECTA_BOX, (1, 2))


def test_direct_constructor_rejects_non_bet_type() -> None:
    with pytest.raises(ValueError):
        BetCombination("exacta_box", (1, 2))  # type: ignore[arg-type]


def test_combination_rejects_duplicate_lanes() -> None:
    with pytest.raises(ValueError):
        BetCombination.create(BetType.EXACTA_ORDERED, [1, 1])


@pytest.mark.parametrize("lane", [0, 7])
def test_combination_rejects_lane_outside_race_range(lane: int) -> None:
    with pytest.raises(ValueError):
        BetCombination.create(BetType.EXACTA_BOX, [1, lane])


def test_combination_rejects_boolean_lane() -> None:
    with pytest.raises(ValueError):
        BetCombination.create(BetType.EXACTA_ORDERED, [True, 2])


@pytest.mark.parametrize(
    ("bet_type", "lanes"),
    [
        (BetType.TRIFECTA_ORDERED, [1, 2]),
        (BetType.TRIFECTA_BOX, [1, 2, 3, 4]),
        (BetType.EXACTA_ORDERED, [1]),
        (BetType.EXACTA_BOX, [1, 2, 3]),
        (BetType.WIDE_BOX, []),
    ],
)
def test_combination_rejects_wrong_lane_count(bet_type: BetType, lanes: list[int]) -> None:
    with pytest.raises(ValueError):
        BetCombination.create(bet_type, lanes)


def test_combination_safely_materializes_lane_iterator() -> None:
    lanes = iter([3, 1, 2])

    combination = BetCombination.create(BetType.TRIFECTA_BOX, lanes)

    assert combination.lanes == (1, 2, 3)
    assert list(lanes) == []


@pytest.mark.parametrize(
    ("bet_type", "expected_lanes"),
    [
        (BetType.EXACTA_ORDERED, (2, 1)),
        (BetType.EXACTA_BOX, (1, 2)),
        (BetType.WIDE_BOX, (1, 2)),
    ],
)
def test_two_lane_bets_apply_settlement_ordering(
    bet_type: BetType, expected_lanes: tuple[int, int]
) -> None:
    combination = BetCombination.create(bet_type, [2, 1])

    assert combination.lanes == expected_lanes
