with events as (

    select
        event_id,
        (payload ->> 'season_id')::int as bzzoiro_season_id,
        (payload ->> 'home_team_id')::int as home_bzzoiro_team_id,
        (payload ->> 'away_team_id')::int as away_bzzoiro_team_id,
        (payload ->> 'event_date')::timestamptz as event_date,
        payload ->> 'status' as status,
        (payload ->> 'round_number')::int as round_number
    from {{ source('raw', 'bzzoiro_events') }}

),

season_starts as (

    select
        bzzoiro_season_id,
        extract(year from min(event_date))::int as start_year
    from events
    group by bzzoiro_season_id

)

select
    e.event_id,
    s.start_year || '/' || right((s.start_year + 1)::text, 2) as season,
    e.home_bzzoiro_team_id,
    e.away_bzzoiro_team_id,
    e.event_date,
    e.status,
    e.round_number
from events as e
inner join season_starts as s
    on s.bzzoiro_season_id = e.bzzoiro_season_id
