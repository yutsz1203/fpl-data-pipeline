with matches as (

    select
        m.*,
        case when m.was_home then f.home_team_id else f.away_team_id end as team_id,
        p.position_id,
        g.ranked_count
    from {{ ref('stg_player_matches') }} as m
    left join {{ ref('stg_fixtures') }} as f
        on f.season = m.season and f.fixture_id = m.fixture_id
    left join {{ ref('stg_players') }} as p
        on p.season = m.season and m.player_id = p.player_id
    left join {{ ref('stg_gameweeks') }} as g
        on g.season = m.season and m.gameweek_id = g.gameweek_id

)

select
    {{ dbt_utils.generate_surrogate_key(['season', 'player_id', 'fixture_id']) }} as player_match_key,
    season,
    {{ dbt_utils.generate_surrogate_key(['season', 'player_id']) }} as player_key,
    {{ dbt_utils.generate_surrogate_key(['season', 'team_id']) }} as team_key,
    {{ dbt_utils.generate_surrogate_key(['season', 'opponent_team_id']) }} as opponent_team_key,
    {{ dbt_utils.generate_surrogate_key(['season', 'position_id']) }} as position_key,
    {{ dbt_utils.generate_surrogate_key(['season', 'gameweek_id']) }} as gameweek_key,
    {{ dbt_utils.generate_surrogate_key(['season', 'fixture_id']) }} as fixture_key,
    was_home,
    total_points,
    minutes,
    starts,
    goals_scored,
    assists,
    clean_sheets,
    goals_conceded,
    own_goals,
    penalties_saved,
    penalties_missed,
    yellow_cards,
    red_cards,
    saves,
    bonus,
    bps,
    clearances_blocks_interceptions,
    recoveries,
    tackles,
    defensive_contribution,
    influence,
    creativity,
    threat,
    ict_index,
    expected_goals,
    expected_assists,
    expected_goal_involvements,
    expected_goals_conceded,
    price,
    selected,
    round(100.0 * selected / nullif(ranked_count, 0), 1)::numeric(4,1) as selected_pct,
    transfers_in,
    transfers_out
from matches