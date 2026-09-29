with matches as (

    select
        f.player_match_key,
        f.season,
        f.player_key,
        f.team_key,
        f.position_key,
        f.gameweek_key,
        x.kickoff_time,
        f.total_points,
        f.minutes,
        f.starts,
        f.expected_goal_involvements,
        f.defensive_contribution,
        f.defcon_points
    from {{ ref('fct_player_match') }} as f
    left join {{ ref('dim_fixture') }} as x
        on x.fixture_key = f.fixture_key

)

select
    player_match_key,
    season,
    player_key,
    team_key,
    position_key,
    gameweek_key,
    kickoff_time,
    total_points,
    minutes,
    count(*) over last_5 as matches_in_form,
    sum(starts) over last_5 as starts_last_5,
    sum(minutes) over last_5 as minutes_last_5,
    round(avg(total_points) over last_5, 1) as form,
    sum(expected_goal_involvements) over last_5 as xgi_last_5,
    round(sum(expected_goal_involvements) over last_5 * 90 / nullif(sum(minutes) over last_5, 0), 2) as xgi_per_90_last_5,
    sum(defensive_contribution) over last_5 as defcon_last_5,
    round(sum(defensive_contribution) over last_5 * 90.0 / nullif(sum(minutes) over last_5, 0), 1) as defcon_per_90_last_5,
    count(*) filter (where defcon_points > 0) over last_5 as defcon_hits_last_5
from matches
window last_5 as (partition by player_key order by kickoff_time rows between 4 preceding and current row)
