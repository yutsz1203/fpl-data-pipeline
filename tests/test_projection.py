import math
from datetime import UTC, date, datetime

import pytest

from mcp_server.forecast import Forecast
from mcp_server.projection import (
    Forecaster,
    availability_for,
    expected_floor,
    fit_strengths,
    fixture_points,
)

SCORING = {
    "short_play": 1,
    "long_play": 2,
    "assists": 3,
    "bonus": 1,
    "saves": 1,
    "yellow_cards": -1,
    "goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4},
    "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
    "goals_conceded": {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
    "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
}


def player(position, **rates):
    base = {
        "position": position,
        "minutes_per_game": 90,
        "play_rate": 1,
        "sixty_rate": 1,
        "xg_share": 0,
        "xa_share": 0,
        "defcon_hit_rate": 0,
        "bonus_per_90": 0,
        "yellow_cards_per_90": 0,
        "saves_per_xgc": 0,
    }
    return base | rates


def results(rounds=4):
    games = []
    for _ in range(rounds):
        for home in range(1, 7):
            for away in range(1, 7):
                if home != away:
                    games.append(
                        {
                            "home_id": home,
                            "away_id": away,
                            "home_goals": 3 if home == 1 else 1,
                            "away_goals": 0 if home == 1 else 1,
                        }
                    )
    return games


def test_expected_floor_matches_the_poisson_sum():
    assert expected_floor(0, 2) == 0
    exact = sum(
        (k // 2) * math.exp(-1.5) * 1.5**k / math.factorial(k) for k in range(40)
    )
    assert expected_floor(1.5, 2) == pytest.approx(exact)
    assert expected_floor(1.5, 2) == pytest.approx(1.5 / 2 - (1 - math.exp(-3)) / 4)


def test_too_few_results_give_no_fallback():
    assert fit_strengths(results(1)[:19]) is None


def test_fallback_rates_the_strong_home_team_above_the_rest():
    model = fit_strengths(results())
    strong_gf, strong_ga = model.predict(1, 2, home=True)
    weak_gf, weak_ga = model.predict(2, 3, home=True)
    assert strong_gf > weak_gf
    assert strong_ga < weak_ga
    assert model.predict(2, 1, home=False) == (strong_ga, strong_gf)


def test_forecaster_prefers_the_engine_then_the_fallback():
    engine = Forecast("", fixtures={(11, 1, 2): (1.8, 0.5)})
    with_fallback = Forecaster(engine, fit_strengths(results()))
    assert with_fallback.goals(11, 1, 2, True) == (1.8, 0.5, "engine")
    assert with_fallback.goals(16, 1, 2, True)[2] == "fallback"
    assert Forecaster(engine, None).goals(16, 1, 2, True) == (None, None, None)


def test_forward_points_come_from_goals_assists_and_minutes():
    parts = fixture_points(
        player("FWD", xg_share=0.4, xa_share=0.1), 2.0, 1.0, 1.0, SCORING
    )
    assert parts["appearance"] == 2
    assert parts["goals"] == pytest.approx(0.4 * 2.0 * 4)
    assert parts["assists"] == pytest.approx(0.1 * 2.0 * 3)
    assert parts["clean_sheets"] == 0
    assert parts["goals_conceded"] == 0
    assert parts["minutes"] == 90


def test_goalkeeper_gets_clean_sheet_saves_and_conceded():
    parts = fixture_points(player("GKP", saves_per_xgc=3), 1.0, 1.2, 1.0, SCORING)
    assert parts["clean_sheets"] == pytest.approx(math.exp(-1.2) * 4)
    assert parts["saves"] == pytest.approx(expected_floor(3.6, 3))
    assert parts["goals_conceded"] == pytest.approx(-expected_floor(1.2, 2))


def test_unavailable_player_scores_nothing():
    parts = fixture_points(player("MID", xg_share=0.3), 2.0, 1.0, 0.0, SCORING)
    assert sum(parts.values()) == 0


def test_availability_uses_the_return_date_after_the_first_gameweek():
    kickoff = datetime(2026, 12, 5, 15, tzinfo=UTC)
    injured = {"availability": 0, "status": "i", "expected_return": date(2026, 11, 30)}
    assert availability_for(injured, kickoff, first_gameweek=True) == 0
    assert availability_for(injured, kickoff, first_gameweek=False) == 1
    still_out = injured | {"expected_return": date(2026, 12, 20)}
    assert availability_for(still_out, kickoff, first_gameweek=False) == 0
    doubt = {"availability": 0.5, "status": "d", "expected_return": None}
    assert availability_for(doubt, kickoff, first_gameweek=False) == 0.75
    no_date = {"availability": 0, "status": "i", "expected_return": None}
    assert availability_for(no_date, kickoff, first_gameweek=False) == 0
