with events as (

    select
        e.event_id,
        e.season,
        f.fixture_id,
        f.gameweek_id,
        coalesce(f.kickoff_time, e.event_date) as kickoff_time,
        e.home_bzzoiro_team_id,
        e.away_bzzoiro_team_id,
        h.team_short_name as home_team,
        a.team_short_name as away_team
    from {{ ref('stg_bzzoiro_events') }} as e
    inner join {{ ref('stg_bzzoiro_teams') }} as hm
        on hm.bzzoiro_team_id = e.home_bzzoiro_team_id
    inner join {{ ref('stg_bzzoiro_teams') }} as am
        on am.bzzoiro_team_id = e.away_bzzoiro_team_id
    inner join {{ ref('stg_teams') }} as h
        on h.season = e.season and h.team_code = hm.team_code
    inner join {{ ref('stg_teams') }} as a
        on a.season = e.season and a.team_code = am.team_code
    inner join {{ ref('stg_fixtures') }} as f
        on f.season = e.season
        and f.home_team_id = h.team_id
        and f.away_team_id = a.team_id

)

select
    {{ dbt_utils.generate_surrogate_key(['l.event_id', 'l.side', 'l.is_starter', 'l.list_order']) }} as lineup_key,
    {{ dbt_utils.generate_surrogate_key(['e.season', 'e.fixture_id']) }} as fixture_key,
    m.player_key,
    e.season,
    e.gameweek_id as gameweek,
    e.kickoff_time,
    case when l.side = 'home' then e.home_team else e.away_team end as team,
    case when l.side = 'home' then e.away_team else e.home_team end as opponent,
    l.side = 'home' as home,
    l.lineup_status,
    l.lineup_updated_at,
    l.formation,
    l.confidence,
    l.is_starter,
    case l.position_code
        when 'G' then 'GKP'
        when 'D' then 'DEF'
        when 'M' then 'MID'
        when 'F' then 'FWD'
    end as line,
    l.list_order as line_order,
    l.player_name,
    l.is_captain,
    l.start_score
from {{ ref('stg_bzzoiro_lineup_players') }} as l
inner join events as e
    on e.event_id = l.event_id
left join {{ ref('bzzoiro_player_map') }} as m
    on m.bzzoiro_player_id = l.bzzoiro_player_id
