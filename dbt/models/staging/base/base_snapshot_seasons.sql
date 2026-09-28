{{ config(materialized='table') }}

-- One row per master snapshot: the FPL season it belongs to.
with first_deadlines as (

    select
        run_date,
        extract(year from (payload -> 'events' -> 0 ->> 'deadline_time')::timestamptz)::int as start_year
    from {{ source('raw', 'master') }}

)

select
    run_date,
    start_year || '/' || right((start_year + 1)::text, 2) as season
from first_deadlines