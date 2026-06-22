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


def test_combination_rejects_duplicate_lanes() -> None:
    with pytest.raises(ValueError):
        BetCombination.create(BetType.EXACTA_ORDERED, [1, 1])


@pytest.mark.parametrize("lane", [0, 7])
def test_combination_rejects_lane_outside_race_range(lane: int) -> None:
    with pytest.raises(ValueError):
        BetCombination.create(BetType.EXACTA_BOX, [1, lane])


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
