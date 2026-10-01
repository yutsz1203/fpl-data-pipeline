with games as (

    select
        f.player_key,
        f.season,
        f.minutes,
        f.total_points,
        f.goals_scored + f.assists as gi,
        f.expected_goal_involvements as xgi,
        f.clean_sheets,
        f.goals_conceded,
        f.expected_goals_conceded as xgc,
        f.defensive_contribution as defcon,
        f.defcon_points,
        f.saves,
        row_number() over (partition by f.player_key order by x.kickoff_time desc) as last_n,
        count(*) over (partition by f.player_key) as games_played
    from {{ ref('fct_player_match') }} as f
    left join {{ ref('dim_fixture') }} as x
        on x.fixture_key = f.fixture_key

),

windows as (

    select
        player_key,
        season,
        last_n,
        games_played,
        count(*) filter (where minutes > 0) over recent as appearances,
        sum(minutes) over recent as minutes,
        sum(total_points) over recent as total_points,
        sum(gi) over recent as gi,
        sum(xgi) over recent as xgi,
        sum(clean_sheets) over recent as clean_sheets,
        sum(goals_conceded) over recent as goals_conceded,
        sum(xgc) over recent as xgc,
        sum(defcon) over recent as defcon,
        count(*) filter (where defcon_points > 0) over recent as defcon_hits,
        sum(saves) over recent as saves
    from games
    window recent as (partition by player_key order by last_n rows between unbounded preceding and current row)

)

select
    w.player_key,
    w.season,
    w.last_n,
    w.games_played,
    s.web_name,
    s.team,
    s.position,
    s.price,
    w.minutes,
    w.total_points,
    round(w.total_points / s.price, 1) as points_per_million,
    w.xgi,
    round(w.xgi * 90 / nullif(w.minutes, 0), 2) as xgi_per_90,
    w.gi,
    w.clean_sheets,
    w.goals_conceded,
    w.xgc,
    round(w.xgc * 90 / nullif(w.minutes, 0), 2) as xgc_per_90,
    w.defcon,
    round(w.defcon * 90.0 / nullif(w.minutes, 0), 1) as defcon_per_90,
    w.defcon_hits,
    round(w.defcon_hits::numeric / nullif(w.appearances, 0), 2) as defcon_hit_rate,
    w.saves
from windows as w
left join {{ ref('player_scouting') }} as s
    on s.player_key = w.player_key
