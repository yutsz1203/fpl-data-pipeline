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
    s.team,
    s.position,
    p.current_price as price
from marts.dim_player as p
left join marts.player_scouting as s
    on s.player_key = p.player_key
where p.season = %(season)s
    and (
        public.unaccent(p.web_name) ilike public.unaccent(%(pattern)s)
        or public.unaccent(p.full_name) ilike public.unaccent(%(pattern)s)
    )
order by s.total_points desc nulls last, p.web_name
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
    f.defensive_contribution as defcon
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
    saves
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
    s.saves
from marts.player_season_stats as s
inner join marts.player_scouting as sc
    on sc.player_key = s.player_key
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
