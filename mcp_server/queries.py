from psycopg import sql

SEASONS_SQL = """
select
    season,
    max(gameweek_id) filter (where is_finished and is_data_checked) as data_to_gameweek,
    count(*) filter (where is_finished and is_data_checked) as finished_gameweeks
from marts.dim_gameweek
group by season
order by season desc
"""

FIND_PLAYER_SQL = """
select season, web_name
from marts.dim_player
where player_key = %(player_key)s
"""

SEARCH_SQL = """
select
    p.player_key,
    p.web_name,
    p.full_name,
    t.team_short_name as team,
    pos.position_name as position,
    p.current_price as price,
    p.status,
    p.chance_of_playing_next_round,
    p.news,
    p.current_selected_pct as selected_pct,
    coalesce(s.minutes, 0) as minutes,
    coalesce(s.total_points, 0) as total_points
from marts.dim_player as p
inner join marts.dim_team as t
    on t.team_key = p.team_key
inner join marts.dim_position as pos
    on pos.position_key = p.position_key
left join marts.player_scouting as s
    on s.player_key = p.player_key
where p.season = %(season)s
    and (
        %(pattern)s::text is null
        or public.unaccent(p.web_name) ilike public.unaccent(%(pattern)s)
        or public.unaccent(p.full_name) ilike public.unaccent(%(pattern)s)
    )
    and (%(team)s::text is null or t.team_short_name = %(team)s)
    and (%(position)s::text is null or pos.position_name = %(position)s)
    and (%(max_price)s::numeric is null or p.current_price <= %(max_price)s)
order by s.total_points desc nulls last, p.current_price desc, p.web_name
limit %(limit)s
"""

TOP_SQL = sql.SQL("""
select
    player_key,
    web_name,
    team,
    price,
    minutes,
    total_points,
    {column} as value
from {table}
where season = %(season)s
    and position = %(position)s
    and minutes >= %(min_minutes)s
    and (%(max_price)s::numeric is null or price <= %(max_price)s)
    and (%(team)s::text is null or team = %(team)s)
    {window_filter}
order by {column} {direction} nulls last, total_points desc, web_name
limit %(limit)s
""")

FORM_GAMES_SQL = """
select
    x.gameweek_id as gameweek,
    x.kickoff_time,
    opp.team_short_name as opponent,
    f.was_home as home,
    f.starts > 0 as started,
    f.minutes,
    f.total_points as points,
    f.goals_scored as goals,
    f.assists,
    f.expected_goal_involvements as xgi,
    f.defensive_contribution as defcon,
    f.bonus,
    f.bps
from marts.fct_player_match as f
inner join marts.dim_fixture as x
    on x.fixture_key = f.fixture_key
inner join marts.dim_team as opp
    on opp.team_key = f.opponent_team_key
where f.player_key = %(player_key)s
order by x.kickoff_time desc
limit %(last_n)s
"""

FORM_TOTALS_SQL = """
select
    web_name,
    team,
    position,
    price,
    last_n as games,
    starts,
    minutes,
    total_points,
    points_per_million,
    goals_scored,
    assists,
    gi,
    xgi,
    xgi_per_90,
    clean_sheets,
    xgc_per_90,
    defcon_per_90,
    defcon_hit_rate,
    saves,
    bonus,
    bps
from marts.player_scouting_last_n
where player_key = %(player_key)s
    and last_n <= %(last_n)s
order by last_n desc
limit 1
"""

SEASON_SQL = """
select
    s.player_key,
    sc.web_name,
    sc.team,
    sc.position,
    s.season,
    s.current_price as price,
    s.appearances,
    s.starts,
    s.minutes,
    s.total_points,
    s.points_per_million,
    s.goals_scored,
    s.assists,
    s.gi,
    s.xg,
    s.xa,
    s.xgi,
    s.gi_minus_xgi,
    s.xgi_per_90,
    s.clean_sheets,
    s.goals_conceded,
    s.xgc_per_90,
    s.defcon_per_90,
    s.defcon_hit_rate,
    s.saves,
    s.bonus,
    s.bps,
    p.status,
    p.chance_of_playing_next_round,
    p.news,
    p.current_selected_pct as selected_pct,
    p.penalties_order,
    p.direct_freekicks_order,
    p.corners_and_indirect_freekicks_order
from marts.player_season_stats as s
inner join marts.player_scouting as sc
    on sc.player_key = s.player_key
inner join marts.dim_player as p
    on p.player_key = s.player_key
where s.player_key = %(player_key)s
"""

SCHEMA_SQL = """
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'marts'
    and table_name = any(%(tables)s)
order by table_name, ordinal_position
"""

FRESHNESS_SQL = """
select
    step,
    max(run_date) filter (where status = 'success') as last_success_run_date,
    max(finished_at) filter (where status = 'success') as last_success_at
from raw.pipeline_runs
group by step
order by step
"""

GAMEWEEK_RANGE_SQL = """
select
    min(gameweek_id) filter (where deadline_time > now()) as next_gameweek,
    max(gameweek_id) as last_gameweek
from marts.dim_gameweek
where season = %(season)s
"""

TEAMS_SQL = """
select team_id, team_short_name as team
from marts.dim_team
where season = %(season)s
order by team_short_name
"""

OUTLOOK_SQL = """
select
    f.gameweek_id as gameweek,
    f.kickoff_time,
    t.team_id,
    o.team_id as opponent_id,
    o.team_short_name as opponent,
    side.home,
    side.difficulty
from marts.dim_fixture as f
cross join lateral (
    values
        (f.home_team_name, f.away_team_name, true, f.difficulty_for_home_team),
        (f.away_team_name, f.home_team_name, false, f.difficulty_for_away_team)
) as side (team_name, opponent_name, home, difficulty)
inner join marts.dim_team as t
    on t.season = f.season and t.team_name = side.team_name
inner join marts.dim_team as o
    on o.season = f.season and o.team_name = side.opponent_name
where f.season = %(season)s
    and f.gameweek_id between %(from_gameweek)s and %(to_gameweek)s
order by f.kickoff_time
"""

SPLITS_SQL = """
select
    side.split,
    count(*) filter (where f.minutes > 0) as appearances,
    sum(f.minutes) as minutes,
    sum(f.total_points) as total_points,
    round(sum(f.total_points)::numeric / nullif(count(*) filter (where f.minutes > 0), 0), 2) as points_per_appearance,
    sum(f.goals_scored) as goals_scored,
    sum(f.assists) as assists,
    sum(f.expected_goal_involvements) as xgi,
    sum(f.clean_sheets) as clean_sheets,
    sum(f.bonus) as bonus
from marts.fct_player_match as f
inner join marts.dim_fixture as x
    on x.fixture_key = f.fixture_key
cross join lateral (
    select case when f.was_home then x.difficulty_for_home_team else x.difficulty_for_away_team end as difficulty
) as d
cross join lateral (
    values
        (1, case when f.was_home then 'home' else 'away' end),
        (2, case
            when d.difficulty <= 2 then 'easy fixtures (difficulty 1-2)'
            when d.difficulty = 3 then 'medium fixtures (difficulty 3)'
            else 'hard fixtures (difficulty 4-5)'
        end)
) as side (kind, split)
where f.player_key = %(player_key)s
group by side.kind, side.split
order by side.kind, side.split desc
"""

AVAILABILITY_SQL = """
select
    p.player_key,
    p.web_name,
    t.team_short_name as team,
    pos.position_name as position,
    p.current_price as price,
    p.status,
    p.chance_of_playing_next_round,
    p.news,
    p.news_added,
    p.current_selected_pct as selected_pct,
    i.injury_type,
    i.expected_return
from marts.dim_player as p
inner join marts.dim_team as t
    on t.team_key = p.team_key
inner join marts.dim_position as pos
    on pos.position_key = p.position_key
left join marts.player_injury as i
    on i.player_key = p.player_key
where p.season = %(season)s
    and p.status = any(%(statuses)s)
    and (%(team)s::text is null or t.team_short_name = %(team)s)
order by p.current_selected_pct desc, p.web_name
limit %(limit)s
"""

STATUS_SQL = """
select
    p.player_key,
    p.web_name,
    t.team_short_name as team,
    pos.position_name as position,
    p.season,
    p.current_price as price,
    p.status,
    p.chance_of_playing_next_round,
    p.news,
    p.news_added,
    i.injury_type,
    i.expected_return,
    p.current_selected_pct as selected_pct,
    p.transfers_in_gameweek,
    p.transfers_out_gameweek,
    p.transfers_in_gameweek - p.transfers_out_gameweek as net_transfers_gameweek,
    p.price_change_gameweek,
    p.price_change_season,
    p.penalties_order,
    p.direct_freekicks_order,
    p.corners_and_indirect_freekicks_order,
    j.expected_minutes,
    j.start_rate,
    j.recent_games
from marts.dim_player as p
inner join marts.dim_team as t
    on t.team_key = p.team_key
inner join marts.dim_position as pos
    on pos.position_key = p.position_key
left join marts.player_injury as i
    on i.player_key = p.player_key
left join marts.player_projection as j
    on j.player_key = p.player_key
where p.player_key = %(player_key)s
"""

STATUS_HISTORY_SQL = """
select
    run_date,
    status,
    chance_of_playing_next_round,
    news,
    price,
    price_change,
    selected_pct
from marts.fct_player_daily
where player_key = %(player_key)s
    and (price_change <> 0 or availability_changed)
order by run_date desc
limit %(limit)s
"""

OWNERSHIP_WEEK_AGO_SQL = """
select selected_pct
from marts.fct_player_daily
where player_key = %(player_key)s
    and run_date <= current_date - 7
order by run_date desc
limit 1
"""

MARKET_SQL = sql.SQL("""
select
    p.player_key,
    p.web_name,
    t.team_short_name as team,
    pos.position_name as position,
    p.current_price as price,
    p.status,
    p.current_selected_pct as selected_pct,
    p.transfers_in_gameweek,
    p.transfers_out_gameweek,
    p.transfers_in_gameweek - p.transfers_out_gameweek as net_transfers_gameweek,
    p.price_change_gameweek,
    p.price_change_season
from marts.dim_player as p
inner join marts.dim_team as t
    on t.team_key = p.team_key
inner join marts.dim_position as pos
    on pos.position_key = p.position_key
where p.season = %(season)s
    and p.status <> 'u'
    and (%(position)s::text is null or pos.position_name = %(position)s)
    and (%(team)s::text is null or t.team_short_name = %(team)s)
    and (%(max_price)s::numeric is null or p.current_price <= %(max_price)s)
order by {order}, p.current_selected_pct desc, p.web_name
limit %(limit)s
""")

PROJECTION_SQL = """
select
    p.player_key,
    p.web_name,
    t.team_short_name as team,
    t.team_id,
    pos.position_name as position,
    p.current_price as price,
    p.status,
    p.chance_of_playing_next_round,
    i.expected_return,
    l.is_starter as predicted_starter,
    j.availability,
    j.recent_games,
    j.start_rate,
    j.minutes_per_game,
    j.play_rate,
    j.sixty_rate,
    j.xg_share,
    j.xa_share,
    j.bonus_per_90,
    j.yellow_cards_per_90,
    j.saves_per_xgc,
    j.defcon_hit_rate
from marts.player_projection as j
inner join marts.dim_player as p
    on p.player_key = j.player_key
inner join marts.dim_team as t
    on t.team_key = p.team_key
inner join marts.dim_position as pos
    on pos.position_key = p.position_key
left join marts.player_injury as i
    on i.player_key = p.player_key
left join marts.next_predicted_lineup as l
    on l.player_key = p.player_key
where p.season = %(season)s
    and p.status <> 'u'
    and (%(position)s::text is null or pos.position_name = %(position)s)
    and (%(team)s::text is null or t.team_short_name = %(team)s)
    and (%(max_price)s::numeric is null or p.current_price <= %(max_price)s)
    and (%(player_keys)s::text[] is null or p.player_key = any(%(player_keys)s))
"""

RESULTS_SQL = """
select
    h.team_id as home_id,
    a.team_id as away_id,
    f.home_team_score as home_goals,
    f.away_team_score as away_goals
from marts.dim_fixture as f
inner join marts.dim_team as h
    on h.season = f.season and h.team_name = f.home_team_name
inner join marts.dim_team as a
    on a.season = f.season and a.team_name = f.away_team_name
where f.season = %(season)s
    and f.is_finished
    and f.home_team_score is not null
"""

UNSCHEDULED_SQL = """
select count(*) as fixtures
from marts.dim_fixture
where season = %(season)s
    and gameweek_id is null
"""

SQUAD_SQL = """
select
    p.player_id,
    p.player_key,
    p.web_name,
    t.team_short_name as team,
    pos.position_name as position,
    p.current_price as price,
    p.price_change_season,
    p.status,
    p.chance_of_playing_next_round,
    p.news
from marts.dim_player as p
inner join marts.dim_team as t
    on t.team_key = p.team_key
inner join marts.dim_position as pos
    on pos.position_key = p.position_key
where p.season = %(season)s
    and p.player_id = any(%(player_ids)s)
"""

LINEUPS_SQL = """
select
    l.gameweek,
    l.kickoff_time,
    l.opponent,
    l.home,
    l.lineup_status,
    l.formation,
    l.confidence,
    l.is_starter,
    l.line,
    l.player_name,
    l.player_key,
    l.start_score
from marts.fct_lineup as l
where l.season = %(season)s
    and l.team = %(team)s
    and l.fixture_key = any(%(fixture_keys)s)
order by l.kickoff_time desc, l.is_starter desc, l.line_order, l.player_name
"""

LINEUP_FIXTURES_SQL = """
(
    select distinct fixture_key, kickoff_time, lineup_status
    from marts.fct_lineup
    where season = %(season)s and team = %(team)s and lineup_status = 'predicted'
    order by kickoff_time
    limit 1
)
union all
(
    select distinct fixture_key, kickoff_time, lineup_status
    from marts.fct_lineup
    where season = %(season)s and team = %(team)s and lineup_status = 'confirmed'
    order by kickoff_time desc
    limit %(last_n)s
)
"""

LINEUPS_UPDATED_SQL = """
select max(finished_at) as updated_at
from raw.pipeline_runs
where step = 'load_bzzoiro' and status = 'success'
"""


NEXT_LINEUP_SQL = """
select gameweek, is_starter, confidence, start_score
from marts.next_predicted_lineup
where player_key = %(player_key)s
"""

GAME_RULES_SQL = """
select season, run_date, scoring, settings, chips, positions
from marts.game_rules
where season = %(season)s
"""
