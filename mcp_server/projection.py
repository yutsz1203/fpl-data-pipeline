import math
from dataclasses import dataclass, field

from mcp_server.forecast import Forecast

MIN_RESULTS = 20
PRIOR_GOALS = 4.0
FIT_ROUNDS = 25
SAVES_PER_POINT = 3
CONCEDED_PER_POINT = 2
PARTS = (
    "appearance",
    "goals",
    "assists",
    "clean_sheets",
    "saves",
    "defcon",
    "bonus",
    "goals_conceded",
    "yellow_cards",
)


@dataclass
class TeamStrengths:
    home_goals: float
    away_goals: float
    attack: dict[int, float] = field(default_factory=dict)
    defence: dict[int, float] = field(default_factory=dict)

    def predict(
        self, team_id: int, opponent_id: int, home: bool
    ) -> tuple[float, float]:
        own, other = (
            (self.home_goals, self.away_goals)
            if home
            else (self.away_goals, self.home_goals)
        )
        gf = own * self.attack.get(team_id, 1.0) * self.defence.get(opponent_id, 1.0)
        ga = other * self.attack.get(opponent_id, 1.0) * self.defence.get(team_id, 1.0)
        return round(gf, 2), round(ga, 2)


def fit_strengths(results: list[dict]) -> TeamStrengths | None:
    if len(results) < MIN_RESULTS:
        return None
    home_goals = sum(r["home_goals"] for r in results) / len(results)
    away_goals = sum(r["away_goals"] for r in results) / len(results)
    teams = {r["home_id"] for r in results} | {r["away_id"] for r in results}
    attack = dict.fromkeys(teams, 1.0)
    defence = dict.fromkeys(teams, 1.0)
    for _ in range(FIT_ROUNDS):
        scored = dict.fromkeys(teams, 0.0)
        conceded = dict.fromkeys(teams, 0.0)
        attack_base = dict.fromkeys(teams, 0.0)
        defence_base = dict.fromkeys(teams, 0.0)
        for r in results:
            h, a = r["home_id"], r["away_id"]
            scored[h] += r["home_goals"]
            scored[a] += r["away_goals"]
            conceded[h] += r["away_goals"]
            conceded[a] += r["home_goals"]
            attack_base[h] += home_goals * defence[a]
            attack_base[a] += away_goals * defence[h]
            defence_base[h] += away_goals * attack[a]
            defence_base[a] += home_goals * attack[h]
        attack = {
            t: (scored[t] + PRIOR_GOALS) / (attack_base[t] + PRIOR_GOALS) for t in teams
        }
        defence = {
            t: (conceded[t] + PRIOR_GOALS) / (defence_base[t] + PRIOR_GOALS)
            for t in teams
        }
        attack_mean = sum(attack.values()) / len(teams)
        defence_mean = sum(defence.values()) / len(teams)
        attack = {t: v / attack_mean for t, v in attack.items()}
        defence = {t: v / defence_mean for t, v in defence.items()}
    return TeamStrengths(home_goals, away_goals, attack, defence)


@dataclass
class Forecaster:
    engine: Forecast
    fallback: TeamStrengths | None

    def goals(
        self, gameweek: int, team_id: int, opponent_id: int, home: bool
    ) -> tuple[float | None, float | None, str | None]:
        found = self.engine.fixtures.get((gameweek, team_id, opponent_id))
        if found is not None:
            return found[0], found[1], "engine"
        if self.fallback is not None:
            gf, ga = self.fallback.predict(team_id, opponent_id, home)
            return gf, ga, "fallback"
        return None, None, None


def expected_floor(mean: float, divisor: int) -> float:
    if mean <= 0:
        return 0.0
    total, pmf = 0.0, math.exp(-mean)
    for k in range(1, 40):
        pmf *= mean / k
        total += (k // divisor) * pmf
    return total


def availability_for(player: dict, kickoff, first_gameweek: bool) -> float:
    chance = float(player["availability"])
    if first_gameweek or player["status"] == "a":
        return chance
    back = player["expected_return"]
    if back is not None:
        return 1.0 if kickoff.date() >= back else 0.0
    if player["status"] in ("d", "s"):
        return (chance + 1) / 2
    return chance


def fixture_points(
    player: dict, gf: float, ga: float, available: float, scoring: dict
) -> dict[str, float]:
    position = player["position"]
    minutes = available * float(player["minutes_per_game"] or 0)
    share = minutes / 90
    plays = available * float(player["play_rate"] or 0)
    sixty = available * float(player["sixty_rate"] or 0)
    parts = dict.fromkeys(PARTS, 0.0)
    parts["appearance"] = plays * scoring["short_play"] + sixty * (
        scoring["long_play"] - scoring["short_play"]
    )
    parts["goals"] = (
        float(player["xg_share"] or 0) * gf * share * scoring["goals_scored"][position]
    )
    parts["assists"] = float(player["xa_share"] or 0) * gf * share * scoring["assists"]
    parts["clean_sheets"] = math.exp(-ga) * sixty * scoring["clean_sheets"][position]
    parts["defcon"] = (
        float(player["defcon_hit_rate"] or 0)
        * plays
        * scoring["defensive_contribution"][position]
    )
    parts["bonus"] = float(player["bonus_per_90"] or 0) * share * scoring["bonus"]
    parts["yellow_cards"] = (
        float(player["yellow_cards_per_90"] or 0) * share * scoring["yellow_cards"]
    )
    parts["goals_conceded"] = (
        expected_floor(ga * share, CONCEDED_PER_POINT)
        * scoring["goals_conceded"][position]
    )
    if position == "GKP":
        parts["saves"] = (
            expected_floor(
                float(player["saves_per_xgc"] or 0) * ga * share, SAVES_PER_POINT
            )
            * scoring["saves"]
        )
    parts["minutes"] = minutes
    return parts
