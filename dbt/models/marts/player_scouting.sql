with latest_team as (

    select distinct on (f.player_key)
        f.player_key,
        f.team_key
    from {{ ref('fct_player_match') }} as f
    left join {{ ref('dim_fixture') }} as x
        on x.fixture_key = f.fixture_key
    order by f.player_key, x.kickoff_time desc

)

select
    s.player_key,
    s.season,
    p.web_name,
    t.team_short_name as team,
    pos.position_name as position,
    s.current_price as price,
    s.minutes,
    s.total_points,
    s.points_per_million,
    s.xgi,
    s.xgi_per_90,
    s.gi,
    s.clean_sheets,
    s.goals_conceded,
    s.xgc,
    s.xgc_per_90,
    s.defcon,
    s.defcon_per_90,
    s.defcon_hits,
    s.defcon_hit_rate,
    s.saves
from {{ ref('player_season_stats') }} as s
left join {{ ref('dim_player') }} as p
    on p.player_key = s.player_key
left join {{ ref('dim_position') }} as pos
    on pos.position_key = s.position_key
left join latest_team as lt
    on lt.player_key = s.player_key
left join {{ ref('dim_team') }} as t
    on t.team_key = lt.team_key
