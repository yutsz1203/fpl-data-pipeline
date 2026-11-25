import pytest

from mcp_server.squad import chips_left, free_transfers, purchase_prices, selling_price

CHIPS = [
    {"name": "wildcard", "start_event": 2, "stop_event": 19},
    {"name": "wildcard", "start_event": 20, "stop_event": 38},
    {"name": "bboost", "start_event": 1, "stop_event": 19},
    {"name": "bboost", "start_event": 20, "stop_event": 38},
]


def week(event, transfers=0, cost=0):
    return {"event": event, "event_transfers": transfers, "event_transfers_cost": cost}


@pytest.mark.parametrize(
    ("purchase", "now", "expected"),
    [
        (7.5, 7.8, 7.6),
        (7.5, 7.6, 7.5),
        (7.5, 7.7, 7.6),
        (7.5, 7.2, 7.2),
        (4.5, 4.5, 4.5),
    ],
)
def test_selling_price_keeps_half_the_rise_rounded_down(purchase, now, expected):
    assert selling_price(purchase, now, 0.5) == expected


def test_purchase_price_is_the_latest_buy_and_skips_free_hit_weeks():
    transfers = [
        {"event": 3, "time": "2026-09-01", "element_in": 7, "element_in_cost": 60},
        {"event": 6, "time": "2026-10-01", "element_in": 7, "element_in_cost": 64},
        {"event": 8, "time": "2026-10-20", "element_in": 7, "element_in_cost": 70},
    ]
    assert purchase_prices(transfers, {8}) == {7: 6.4}


def test_free_transfers_bank_up_to_the_cap():
    history = [week(gw) for gw in range(1, 11)]
    assert free_transfers(history, {}, 0, 5) == 5
    assert free_transfers(history[:3], {}, 0, 5) == 3


def test_free_transfers_reset_after_a_hit():
    history = [week(1), week(2), week(3, transfers=4, cost=8)]
    assert free_transfers(history, {}, 0, 5) == 1


def test_free_transfers_unchanged_by_a_wildcard_or_free_hit():
    history = [week(1), week(2), week(3, transfers=9), week(4, transfers=6)]
    assert free_transfers(history, {3: "wildcard", 4: "freehit"}, 0, 5) == 2


def test_free_transfers_minus_pending_transfers():
    history = [week(1), week(2), week(3)]
    assert free_transfers(history, {}, 2, 5) == 1
    assert free_transfers(history, {}, 4, 5) == 0
    assert free_transfers([], {}, 0, 5) is None


def test_chips_left_drops_played_and_expired_chips():
    left = chips_left(CHIPS, {1: "bboost"}, 11)
    assert [(c["chip"], c["from_gameweek"], c["playable_now"]) for c in left] == [
        ("wildcard", 2, True),
        ("wildcard", 20, False),
        ("bboost", 20, False),
    ]
    late = chips_left(CHIPS, {1: "bboost"}, 20)
    assert [(c["chip"], c["from_gameweek"]) for c in late] == [
        ("wildcard", 20),
        ("bboost", 20),
    ]
