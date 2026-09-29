with season_totals as (

    select
        player_key,
        season,
        position_key,
        count(*) filter (where minutes > 0) as appearances,
        sum(starts) as starts,
        sum(minutes) as minutes,
        sum(total_points) as total_points,
        sum(goals_scored) as goals_scored,
        sum(assists) as assists,
        sum(expected_goals) as xg,
        sum(expected_assists) as xa,
        sum(expected_goal_involvements) as xgi,
        sum(defensive_contribution) as defcon,
        count(*) filter (where defcon_points > 0) as defcon_hits,
        sum(clean_sheets) as clean_sheets,
        sum(goals_conceded) as goals_conceded,
        sum(expected_goals_conceded) as xgc,
        sum(saves) as saves
    from {{ ref('fct_player_match') }}
    group by player_key, season, position_key

)

select
    s.player_key,
    s.season,
    s.position_key,
    s.appearances,
    s.starts,
    s.minutes,
    s.total_points,
    p.current_price,
    round(s.total_points / p.current_price, 1) as points_per_million,
    s.goals_scored,
    s.assists,
    s.goals_scored + s.assists as gi,
    s.xg,
    s.xa,
    s.xgi,
    s.goals_scored + s.assists - s.xgi as gi_minus_xgi,
    round(s.xgi * 90 / nullif(s.minutes, 0), 2) as xgi_per_90,
    s.defcon,
    round(s.defcon * 90.0 / nullif(s.minutes, 0), 1) as defcon_per_90,
    s.defcon_hits,
    round(s.defcon_hits::numeric / nullif(s.appearances, 0), 2) as defcon_hit_rate,
    s.clean_sheets,
    s.goals_conceded,
    s.xgc,
    round(s.xgc * 90 / nullif(s.minutes, 0), 2) as xgc_per_90,
    s.saves
from season_totals as s
left join {{ ref('dim_player') }} as p
    on p.player_key = s.player_key
